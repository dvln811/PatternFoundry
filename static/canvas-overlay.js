// canvas-overlay.js — Drawing overlay for lightweight-charts

class CanvasOverlay {
    constructor(chart, series, chartEl) {
        this.chart = chart;
        this.series = series;
        this.chartEl = chartEl;
        this.canvas = null;
        this.ctx = null;
        this.drawings = [];
        this.activeTool = null;
        this.activeColor = '#f0c040';
        this.activeLineStyle = 'solid';
        this.activeLineWidth = 1;
        this._drawState = null;
        this._dragState = null;
        this._hoveredDrawing = null;
        this._hoveredHandle = null;
        this._handlers = {};
        this._rafId = null;
        this.onDrawingComplete = null;
        this._propEditor = null;
        this._setup();
    }

    _setup() {
        this.canvas = document.createElement('canvas');
        this.canvas.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:5;';
        this.chartEl.style.position = 'relative';
        this.chartEl.appendChild(this.canvas);
        this._overlay = document.createElement('div');
        this._overlay.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;z-index:6;pointer-events:none;';
        this.chartEl.appendChild(this._overlay);
        this._updateSize();
        this._bindEvents();
        const refresh = () => this._scheduleRedraw();
        this.chart.timeScale().subscribeVisibleTimeRangeChange(refresh);
        this.chart.timeScale().subscribeVisibleLogicalRangeChange(refresh);
        this.chart.subscribeCrosshairMove(refresh);
        new ResizeObserver(() => { this._updateSize(); this._scheduleRedraw(); }).observe(this.chartEl);
    }

    _updateSize() {
        const rect = this.chartEl.getBoundingClientRect();
        const dpr = devicePixelRatio || 1;
        this.canvas.width = rect.width * dpr;
        this.canvas.height = rect.height * dpr;
        this.canvas.style.width = rect.width + 'px';
        this.canvas.style.height = rect.height + 'px';
        this.ctx = this.canvas.getContext('2d');
        this.ctx.scale(dpr, dpr);
    }

    _bindEvents() {
        this._handlers.mousedown = e => this._mouseDown(e);
        this._handlers.mousemove = e => this._mouseMove(e);
        this._handlers.mouseup = e => this._mouseUp(e);
        this._handlers.keydown = e => this._keyDown(e);
        this._handlers.contextmenu = e => this._contextMenu(e);
        this.chartEl.addEventListener('mousedown', this._handlers.mousedown, true);
        this.chartEl.addEventListener('mousemove', this._handlers.mousemove, true);
        this.chartEl.addEventListener('contextmenu', this._handlers.contextmenu, true);
        document.addEventListener('mouseup', this._handlers.mouseup);
        document.addEventListener('keydown', this._handlers.keydown);
    }

    destroy() {
        this.chartEl.removeEventListener('mousedown', this._handlers.mousedown, true);
        this.chartEl.removeEventListener('mousemove', this._handlers.mousemove, true);
        this.chartEl.removeEventListener('contextmenu', this._handlers.contextmenu, true);
        document.removeEventListener('mouseup', this._handlers.mouseup);
        document.removeEventListener('keydown', this._handlers.keydown);
        if (this.canvas) this.canvas.remove();
        if (this._overlay) this._overlay.remove();
        if (this._rafId) cancelAnimationFrame(this._rafId);
        this._closePropEditor();
    }

    // ── Coordinate mapping ───────────────────────────────────────────────────
    _priceToY(price) {
        try { const y = this.series.priceToCoordinate(price); return y != null && !isNaN(y) ? y : null; } catch { return null; }
    }
    _yToPrice(y) {
        try { const p = this.series.coordinateToPrice(y); return p != null && !isNaN(p) ? p : null; } catch { return null; }
    }
    _timeToX(time) {
        try {
            const x = this.chart.timeScale().timeToCoordinate(time);
            if (x != null && !isNaN(x)) return x;
        } catch {}
        try {
            const lr = this.chart.timeScale().getVisibleLogicalRange();
            const vr = this.chart.timeScale().getVisibleRange();
            if (!lr || !vr || !vr.to) return null;
            const tsW = this.chart.timeScale().width();
            if (!tsW || !lr.from || !lr.to) return null;
            const pxPerUnit = tsW / (lr.to - lr.from);
            const tf = window.candleTF || 60;
            const beyond = (time - vr.to) / tf;
            const lastX = this.chart.timeScale().timeToCoordinate(vr.to);
            return lastX != null ? lastX + beyond * pxPerUnit : null;
        } catch { return null; }
    }
    _xToTime(x) {
        try { return this.chart.timeScale().coordinateToTime(x) || null; } catch { return null; }
    }
    _xToTimeExt(x) {
        const t = this._xToTime(x);
        if (t) return t;
        try {
            const lr = this.chart.timeScale().getVisibleLogicalRange();
            const vr = this.chart.timeScale().getVisibleRange();
            if (!lr || !vr || !vr.to) return null;
            const tsW = this.chart.timeScale().width();
            if (!tsW) return null;
            const pxPerUnit = tsW / (lr.to - lr.from);
            const lastX = this.chart.timeScale().timeToCoordinate(vr.to);
            if (lastX == null) return null;
            const tf = window.candleTF || 60;
            return Math.round(vr.to + ((x - lastX) / pxPerUnit) * tf);
        } catch { return null; }
    }
    _localPt(e) { const r = this.chartEl.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; }
    _snap(v) { return Math.round(v * 100) / 100; }

    // ── Tool control ─────────────────────────────────────────────────────────
    setTool(tool) {
        this._drawState = null;
        this.activeTool = tool;
        this._overlay.style.pointerEvents = tool ? 'auto' : 'none';
        this.chartEl.style.cursor = tool ? 'crosshair' : '';
        this.chart.applyOptions({ handleScroll: !tool, handleScale: !tool });
        this._scheduleRedraw();
    }
    setColor(c) { this.activeColor = c; }
    setLineStyle(s) { this.activeLineStyle = s; }
    setLineWidth(w) { this.activeLineWidth = w; }

    // ── Mouse events ─────────────────────────────────────────────────────────
    _mouseDown(e) {
        if (e.button === 2) return; // right-click handled by contextmenu
        const pt = this._localPt(e);
        if (window._simDragActive) return;
        if (!this.activeTool) {
            const { drawing, handle } = this._hitTest(pt.x, pt.y);
            if (drawing) {
                e.preventDefault(); e.stopPropagation();
                this.chart.applyOptions({ handleScroll: false, handleScale: false });
                this._dragState = {
                    drawing, handle,
                    startX: pt.x, startY: pt.y,
                    startPrice: this._yToPrice(pt.y),
                    startTime: this._xToTimeExt(pt.x),
                    orig: JSON.parse(JSON.stringify(drawing))
                };
                this.chartEl.style.cursor = handle === 'body' ? 'move' : 'crosshair';
            }
            return;
        }
        e.preventDefault(); e.stopPropagation();
        const price = this._yToPrice(pt.y);
        const time = this._xToTimeExt(pt.x);
        if (price == null) return;

        // Multi-click position tools
        if (this._drawState && (this._drawState.tool === 'longpos' || this._drawState.tool === 'shortpos')) {
            const ds = this._drawState;
            if (ds.phase === 1) { ds.phase = 2; ds.tpPrice = this._snap(price); ds.tpTime = time; return; }
            if (ds.phase === 2) {
                const d = { type: ds.tool, p1: { time: ds.startTime, price: ds.startPrice }, p2: { time: ds.tpTime, price: ds.tpPrice }, p3: { time: ds.tpTime, price: this._snap(price) }, color: ds.tool === 'longpos' ? '#4caf82' : '#e05c5c', id: Date.now() };
                this.drawings.push(d);
                this._drawState = null;
                this._finalize();
                if (this.onDrawingComplete) this.onDrawingComplete(d);
                return;
            }
        }

        // Multi-click channel tool (3 clicks: p1, p2, p3)
        if (this._drawState && this._drawState.tool === 'channel') {
            const ds = this._drawState;
            if (ds.phase === 1) {
                ds.phase = 2;
                ds.p2Price = this._snap(price);
                ds.p2Time = time;
                ds.p2X = pt.x;
                ds.p2Y = pt.y;
                return;
            }
            if (ds.phase === 2) {
                const d = {
                    type: 'channel',
                    p1: { time: ds.startTime, price: ds.startPrice },
                    p2: { time: ds.p2Time, price: ds.p2Price },
                    p3: { time: time, price: this._snap(price) },
                    color: ds.color, lineStyle: ds.lineStyle, lineWidth: ds.lineWidth, id: Date.now()
                };
                this.drawings.push(d);
                this._drawState = null;
                this._finalize();
                if (this.onDrawingComplete) this.onDrawingComplete(d);
                return;
            }
        }

        if (this.activeTool === 'hline') {
            this.drawings.push({ type: 'hline', price: this._snap(price), color: this.activeColor, lineStyle: this.activeLineStyle, lineWidth: this.activeLineWidth, id: Date.now() });
            this._finalize();
        } else if (this.activeTool === 'vline') {
            if (time) this.drawings.push({ type: 'vline', time, color: this.activeColor, lineStyle: this.activeLineStyle, id: Date.now() });
            this._finalize();
        } else if (this.activeTool === 'longpos' || this.activeTool === 'shortpos') {
            this._drawState = { tool: this.activeTool, phase: 1, startX: pt.x, startY: pt.y, startPrice: price, startTime: time, curX: pt.x, curY: pt.y };
        } else if (this.activeTool === 'channel') {
            this._drawState = { tool: 'channel', phase: 1, color: this.activeColor, lineStyle: this.activeLineStyle, lineWidth: this.activeLineWidth, startX: pt.x, startY: pt.y, startPrice: price, startTime: time, curX: pt.x, curY: pt.y };
        } else {
            this._drawState = { tool: this.activeTool, color: this.activeColor, lineStyle: this.activeLineStyle, lineWidth: this.activeLineWidth, startX: pt.x, startY: pt.y, startPrice: price, startTime: time, curX: pt.x, curY: pt.y };
        }
    }

    _mouseMove(e) {
        const pt = this._localPt(e);
        if (this._dragState) { this._performDrag(pt); return; }
        if (this._drawState) {
            this._drawState.curX = pt.x;
            this._drawState.curY = pt.y;
            if (this._drawState.tool === 'line' && e.shiftKey) this._drawState.curY = this._drawState.startY;
            if (this._drawState.phase === 2 && (this._drawState.tool === 'longpos' || this._drawState.tool === 'shortpos')) this._drawState.slY = pt.y;
            this._scheduleRedraw();
            return;
        }
        if (!this.activeTool) {
            if (window._simDragActive) return;
            const { drawing, handle } = this._hitTest(pt.x, pt.y);
            this._hoveredDrawing = drawing;
            this._hoveredHandle = handle;
            if (!drawing) this.chartEl.style.cursor = '';
            else if (handle === 'p1' || handle === 'p2' || handle === 'p3') this.chartEl.style.cursor = 'crosshair';
            else if (drawing.type === 'hline') this.chartEl.style.cursor = 'ns-resize';
            else if (drawing.type === 'vline') this.chartEl.style.cursor = 'ew-resize';
            else this.chartEl.style.cursor = 'move';
        }
    }

    _mouseUp(e) {
        if (this._dragState) { this._endDrag(); return; }
        if (!this._drawState) return;
        const ds = this._drawState, pt = this._localPt(e);
        if (ds.tool === 'longpos' || ds.tool === 'shortpos') return;
        if (ds.tool === 'channel') return; // channel uses multi-click
        const dist = Math.hypot(pt.x - ds.startX, pt.y - ds.startY);
        if (dist < 5) { this._drawState = null; this._scheduleRedraw(); return; }

        const endPrice = this._yToPrice(pt.y);
        const endTime = this._xToTimeExt(pt.x);
        let ep = endPrice;
        if (ds.tool === 'line' && e.shiftKey) ep = ds.startPrice;
        const base = { p1: { time: ds.startTime, price: ds.startPrice }, p2: { time: endTime, price: ep }, color: ds.color, id: Date.now() };

        if (ds.tool === 'line') this.drawings.push({ ...base, type: 'line', lineStyle: ds.lineStyle, lineWidth: ds.lineWidth, p2: { time: endTime, price: ep } });
        else if (ds.tool === 'arrow') this.drawings.push({ ...base, type: 'arrow', lineWidth: ds.lineWidth, p2: { time: endTime, price: endPrice } });
        else {
            const entry = { type: ds.tool, p1: { time: ds.startTime, price: ds.startPrice }, p2: { time: endTime, price: endPrice }, color: ds.color, id: Date.now() };
            this.drawings.push(entry);
        }
        this._drawState = null;
        this._finalize();
    }

    _keyDown(e) {
        if (e.key === 'Escape') { this._drawState = null; this.setTool(null); if (window.setDrawTool) window.setDrawTool(null); this._scheduleRedraw(); return; }
        if ((e.key === 'Delete' || e.key === 'Backspace') && !this.activeTool && document.activeElement.tagName !== 'INPUT') {
            if (this._hoveredDrawing) { this.remove(this._hoveredDrawing.id); this._hoveredDrawing = null; }
            else if (this.drawings.length) this.drawings.pop();
            this._scheduleRedraw();
        }
    }

    _finalize() {
        this._scheduleRedraw();
        this.setTool(null);
        if (window.setDrawTool) window.setDrawTool(null);
        if (window._persistedDrawings !== undefined) window._persistedDrawings = JSON.parse(JSON.stringify(this.drawings));
    }

    // ── Right-click property editor ──────────────────────────────────────────
    _contextMenu(e) {
        const pt = this._localPt(e);
        const { drawing } = this._hitTest(pt.x, pt.y);
        if (!drawing) return;
        e.preventDefault();
        e.stopPropagation();
        this._closePropEditor();
        const popup = document.createElement('div');
        popup.style.cssText = 'position:fixed;z-index:9999;background:#1e1e2e;border:1px solid #444;border-radius:6px;padding:10px;display:flex;flex-direction:column;gap:8px;font:12px Inter,sans-serif;color:#ccc;min-width:160px;';
        popup.style.left = e.clientX + 'px';
        popup.style.top = e.clientY + 'px';

        // Color picker
        const colorRow = document.createElement('label');
        colorRow.textContent = 'Color: ';
        const colorInput = document.createElement('input');
        colorInput.type = 'color';
        colorInput.value = drawing.color || '#f0c040';
        colorInput.style.cssText = 'width:50px;height:22px;border:none;cursor:pointer;vertical-align:middle;';
        colorInput.addEventListener('input', () => { drawing.color = colorInput.value; this._scheduleRedraw(); });
        colorRow.appendChild(colorInput);
        popup.appendChild(colorRow);

        // Line width slider
        const widthRow = document.createElement('label');
        widthRow.textContent = 'Width: ';
        const widthInput = document.createElement('input');
        widthInput.type = 'range';
        widthInput.min = '1'; widthInput.max = '5'; widthInput.step = '1';
        widthInput.value = String(drawing.lineWidth || 1);
        widthInput.style.cssText = 'width:80px;vertical-align:middle;';
        widthInput.addEventListener('input', () => { drawing.lineWidth = Number(widthInput.value); this._scheduleRedraw(); });
        widthRow.appendChild(widthInput);
        popup.appendChild(widthRow);

        // Line style dropdown
        const styleRow = document.createElement('label');
        styleRow.textContent = 'Style: ';
        const styleSelect = document.createElement('select');
        styleSelect.style.cssText = 'background:#2a2a3e;color:#ccc;border:1px solid #555;border-radius:3px;padding:2px;vertical-align:middle;';
        for (const s of ['solid', 'dashed', 'dotted']) {
            const opt = document.createElement('option');
            opt.value = s; opt.textContent = s;
            if ((drawing.lineStyle || 'solid') === s) opt.selected = true;
            styleSelect.appendChild(opt);
        }
        styleSelect.addEventListener('change', () => { drawing.lineStyle = styleSelect.value; this._scheduleRedraw(); });
        styleRow.appendChild(styleSelect);
        popup.appendChild(styleRow);

        // Text-specific fields
        if (drawing.type === 'text') {
            const textRow = document.createElement('label');
            textRow.textContent = 'Text: ';
            const textInput = document.createElement('textarea');
            textInput.value = drawing.text || '';
            textInput.style.cssText = 'width:100%;min-height:50px;background:#111;border:1px solid #444;color:#ddd;border-radius:3px;padding:4px;font:11px Inter,sans-serif;resize:vertical;';
            textInput.addEventListener('input', () => { drawing.text = textInput.value; this._scheduleRedraw(); });
            textRow.appendChild(document.createElement('br'));
            textRow.appendChild(textInput);
            popup.appendChild(textRow);

            const sizeRow = document.createElement('label');
            sizeRow.textContent = 'Size: ';
            const sizeInput = document.createElement('input');
            sizeInput.type = 'range'; sizeInput.min = '8'; sizeInput.max = '32'; sizeInput.step = '1';
            sizeInput.value = String(drawing.fontSize || 12);
            sizeInput.style.cssText = 'width:80px;vertical-align:middle;';
            sizeInput.addEventListener('input', () => { drawing.fontSize = Number(sizeInput.value); this._scheduleRedraw(); });
            const sizeVal = document.createElement('span');
            sizeVal.textContent = ' ' + (drawing.fontSize || 12) + 'px';
            sizeVal.style.color = '#888';
            sizeInput.addEventListener('input', () => { sizeVal.textContent = ' ' + sizeInput.value + 'px'; });
            sizeRow.appendChild(sizeInput);
            sizeRow.appendChild(sizeVal);
            popup.appendChild(sizeRow);
        }

        // Delete button
        const delBtn = document.createElement('button');
        delBtn.textContent = 'Delete';
        delBtn.style.cssText = 'background:#e05c5c;color:#fff;border:none;border-radius:4px;padding:4px 8px;cursor:pointer;margin-top:4px;';
        delBtn.addEventListener('click', () => { this.remove(drawing.id); this._closePropEditor(); });
        popup.appendChild(delBtn);

        document.body.appendChild(popup);
        this._propEditor = popup;
        this._propEditorClose = (ev) => {
            if (!popup.contains(ev.target)) this._closePropEditor();
        };
        setTimeout(() => document.addEventListener('mousedown', this._propEditorClose), 0);
    }

    _closePropEditor() {
        if (this._propEditor) {
            this._propEditor.remove();
            this._propEditor = null;
        }
        if (this._propEditorClose) {
            document.removeEventListener('mousedown', this._propEditorClose);
            this._propEditorClose = null;
        }
        if (window._persistedDrawings !== undefined) window._persistedDrawings = this.toJSON();
    }

    // ── Hit testing ──────────────────────────────────────────────────────────
    _hitTest(x, y) {
        const T = 8;
        for (let i = this.drawings.length - 1; i >= 0; i--) {
            const d = this.drawings[i];
            if (d.type === 'hline') {
                const py = this._priceToY(d.price);
                if (py != null && Math.abs(y - py) < T) return { drawing: d, handle: 'body' };
            } else if (d.type === 'vline') {
                const px = this._timeToX(d.time);
                if (px != null && Math.abs(x - px) < T) return { drawing: d, handle: 'body' };
            } else if (d.p1 && d.p2) {
                const x1 = this._timeToX(d.p1.time), y1 = this._priceToY(d.p1.price);
                const x2 = this._timeToX(d.p2.time), y2 = this._priceToY(d.p2.price);
                if (x1 == null || y1 == null || x2 == null || y2 == null) continue;
                // p3 handle
                if (d.p3) {
                    const x3 = d.p3.time ? this._timeToX(d.p3.time) : null;
                    const y3 = this._priceToY(d.p3.price);
                    const px3 = (d.type === 'longpos' || d.type === 'shortpos') ? Math.max(x1, x2) : x3;
                    if (y3 != null && px3 != null && Math.hypot(x - px3, y - y3) < T) return { drawing: d, handle: 'p3' };
                }
                // Position tool handles
                if (d.type === 'longpos' || d.type === 'shortpos') {
                    const rx = Math.max(x1, x2);
                    if (Math.hypot(x - rx, y - y2) < T) return { drawing: d, handle: 'p2' };
                    if (Math.hypot(x - x1, y - y1) < T) return { drawing: d, handle: 'p1' };
                }
                // Endpoint handles
                if (Math.hypot(x - x1, y - y1) < T) return { drawing: d, handle: 'p1' };
                if (Math.hypot(x - x2, y - y2) < T) return { drawing: d, handle: 'p2' };
                // Body detection
                if (d.type === 'line' || d.type === 'arrow') {
                    if (this._segDist(x, y, x1, y1, x2, y2) < T) return { drawing: d, handle: 'body' };
                } else if (d.type === 'channel') {
                    // Channel: check both lines and the midline
                    if (d.p3) {
                        const x3 = this._timeToX(d.p3.time), y3 = this._priceToY(d.p3.price);
                        if (x3 != null && y3 != null) {
                            const offX = x3 - x1, offY = y3 - y1;
                            if (this._segDist(x, y, x1, y1, x2, y2) < T) return { drawing: d, handle: 'body' };
                            if (this._segDist(x, y, x1 + offX, y1 + offY, x2 + offX, y2 + offY) < T) return { drawing: d, handle: 'body' };
                        }
                    } else {
                        if (this._segDist(x, y, x1, y1, x2, y2) < T) return { drawing: d, handle: 'body' };
                    }
                } else if (d.type === 'ellipse') {
                    const cx = (x1 + x2) / 2, cy = (y1 + y2) / 2, rx2 = Math.abs(x2 - x1) / 2, ry2 = Math.abs(y2 - y1) / 2;
                    if (rx2 > 0 && ry2 > 0 && Math.abs(((x - cx) / rx2) ** 2 + ((y - cy) / ry2) ** 2 - 1) < 0.3) return { drawing: d, handle: 'body' };
                } else if (d.type === 'circle') {
                    const r = Math.hypot(x2 - x1, y2 - y1);
                    if (Math.abs(Math.hypot(x - x1, y - y1) - r) < T) return { drawing: d, handle: 'body' };
                } else if (d.type === 'longpos' || d.type === 'shortpos') {
                    const l = Math.min(x1, x2), r2 = Math.max(x1, x2);
                    if (x >= l - T && x <= r2 + T && Math.abs(y - y1) < T) return { drawing: d, handle: 'body' };
                } else {
                    const minX = Math.min(x1, x2), maxX = Math.max(x1, x2), minY = Math.min(y1, y2), maxY = Math.max(y1, y2);
                    if (x >= minX - T && x <= maxX + T && y >= minY - T && y <= maxY + T) {
                        if (Math.abs(x - minX) < T || Math.abs(x - maxX) < T || Math.abs(y - minY) < T || Math.abs(y - maxY) < T)
                            return { drawing: d, handle: 'body' };
                    }
                }
            }
        }
        return { drawing: null, handle: null };
    }

    _segDist(px, py, x1, y1, x2, y2) {
        const dx = x2 - x1, dy = y2 - y1, len2 = dx * dx + dy * dy;
        if (len2 === 0) return Math.hypot(px - x1, py - y1);
        const t = Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) / len2));
        return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
    }

    // ── Drag logic ───────────────────────────────────────────────────────────
    _performDrag(pt) {
        const { drawing: d, handle, orig, startX, startY, startPrice } = this._dragState;
        const curPrice = this._yToPrice(pt.y);
        const curTime = this._xToTimeExt(pt.x);

        if (d.type === 'hline') { if (curPrice != null) d.price = this._snap(curPrice); }
        else if (d.type === 'vline') { if (curTime) d.time = curTime; }
        else if (handle === 'p1') { if (curPrice != null) d.p1.price = this._snap(curPrice); if (curTime) d.p1.time = curTime; }
        else if (handle === 'p2') { if (curPrice != null) d.p2.price = this._snap(curPrice); if (curTime) d.p2.time = curTime; }
        else if (handle === 'p3' && d.p3) { if (curPrice != null) d.p3.price = this._snap(curPrice); if (curTime) d.p3.time = curTime; }
        else if (curPrice != null && startPrice != null && orig.p1 && orig.p2) {
            const dp = curPrice - startPrice;
            const dx = pt.x - startX;
            const ox1 = this._timeToX(orig.p1.time), ox2 = this._timeToX(orig.p2.time);
            const t1 = ox1 != null ? this._xToTimeExt(ox1 + dx) : orig.p1.time;
            const t2 = ox2 != null ? this._xToTimeExt(ox2 + dx) : orig.p2.time;
            d.p1 = { time: t1 || orig.p1.time, price: this._snap(orig.p1.price + dp) };
            d.p2 = { time: t2 || orig.p2.time, price: this._snap(orig.p2.price + dp) };
            if (orig.p3) {
                const ox3 = this._timeToX(orig.p3.time);
                const t3 = ox3 != null ? this._xToTimeExt(ox3 + dx) : orig.p3.time;
                d.p3 = { time: t3 || orig.p3.time, price: this._snap(orig.p3.price + dp) };
            }
        }
        this._scheduleRedraw();
    }

    _endDrag() {
        this._dragState = null;
        this.chart.applyOptions({ handleScroll: true, handleScale: true });
        this.chartEl.style.cursor = '';
        if (window._persistedDrawings !== undefined) window._persistedDrawings = this.toJSON();
    }

    // ── Rendering ────────────────────────────────────────────────────────────
    _scheduleRedraw() {
        if (this._rafId) return;
        this._rafId = requestAnimationFrame(() => { this._rafId = null; this._render(); });
    }

    _render() {
        if (!this.ctx) return;
        const dpr = devicePixelRatio || 1;
        const w = this.canvas.width / dpr, h = this.canvas.height / dpr;
        this.ctx.clearRect(0, 0, w, h);
        for (const d of this.drawings) this._renderDrawing(d, d === this._hoveredDrawing);
        if (this._drawState) this._renderPreview();
    }

    _applyDash(ctx, style, width) {
        ctx.lineWidth = width || 1;
        ctx.setLineDash(style === 'dashed' ? [6, 3] : style === 'dotted' ? [2, 2] : []);
    }

    _drawHandle(ctx, x, y, color) {
        ctx.fillStyle = color;
        ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = '#0d0d0d'; ctx.lineWidth = 1; ctx.setLineDash([]);
        ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI * 2); ctx.stroke();
    }

    _renderDrawing(d, hovered) {
        const ctx = this.ctx;
        const dpr = devicePixelRatio || 1;
        const w = this.canvas.width / dpr, h = this.canvas.height / dpr;
        ctx.save();

        if (d.type === 'hline') {
            const y = this._priceToY(d.price);
            if (y == null) { ctx.restore(); return; }
            ctx.strokeStyle = d.color || '#f0c040';
            this._applyDash(ctx, d.lineStyle, hovered ? 2 : (d.lineWidth || 1));
            ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
            ctx.fillStyle = d.color || '#f0c040'; ctx.font = '10px Inter,sans-serif';
            ctx.fillText(d.price.toFixed(2), 4, y - 3);
        } else if (d.type === 'vline') {
            const x = this._timeToX(d.time);
            if (x == null) { ctx.restore(); return; }
            ctx.strokeStyle = d.color || '#f0c040';
            this._applyDash(ctx, d.lineStyle, hovered ? 2 : 1);
            ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
        } else if (d.type === 'line') {
            const x1 = this._timeToX(d.p1.time), y1 = this._priceToY(d.p1.price);
            const x2 = this._timeToX(d.p2.time), y2 = this._priceToY(d.p2.price);
            if (x1 == null || y1 == null || x2 == null || y2 == null) { ctx.restore(); return; }
            ctx.strokeStyle = d.color || '#38bdf8';
            this._applyDash(ctx, d.lineStyle, hovered ? 2 : (d.lineWidth || 1));
            ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
            if (hovered) { this._drawHandle(ctx, x1, y1, d.color || '#38bdf8'); this._drawHandle(ctx, x2, y2, d.color || '#38bdf8'); }
        } else if (d.type === 'arrow') {
            const x1 = this._timeToX(d.p1.time), y1 = this._priceToY(d.p1.price);
            const x2 = this._timeToX(d.p2.time), y2 = this._priceToY(d.p2.price);
            if (x1 == null || y1 == null || x2 == null || y2 == null) { ctx.restore(); return; }
            ctx.strokeStyle = d.color || '#f0c040'; ctx.lineWidth = hovered ? 3 : (d.lineWidth || 2); ctx.setLineDash([]);
            ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
            const ang = Math.atan2(y2 - y1, x2 - x1);
            ctx.fillStyle = d.color || '#f0c040'; ctx.beginPath();
            ctx.moveTo(x2, y2);
            ctx.lineTo(x2 - 12 * Math.cos(ang - 0.4), y2 - 12 * Math.sin(ang - 0.4));
            ctx.lineTo(x2 - 12 * Math.cos(ang + 0.4), y2 - 12 * Math.sin(ang + 0.4));
            ctx.closePath(); ctx.fill();
            if (hovered) { this._drawHandle(ctx, x1, y1, d.color || '#f0c040'); this._drawHandle(ctx, x2, y2, d.color || '#f0c040'); }
        } else if (d.type === 'rect') {
            const x1 = this._timeToX(d.p1.time), y1 = this._priceToY(d.p1.price);
            const x2 = this._timeToX(d.p2.time), y2 = this._priceToY(d.p2.price);
            if (x1 == null || y1 == null || x2 == null || y2 == null) { ctx.restore(); return; }
            const rx = Math.min(x1, x2), ry = Math.min(y1, y2), rw = Math.abs(x2 - x1), rh = Math.abs(y2 - y1);
            ctx.fillStyle = (d.color || '#f0c040') + '18'; ctx.fillRect(rx, ry, rw, rh);
            ctx.strokeStyle = d.color || '#f0c040'; ctx.lineWidth = hovered ? 2 : 1; ctx.setLineDash([]);
            ctx.strokeRect(rx, ry, rw, rh);
            if (hovered) { ctx.fillStyle = d.color || '#f0c040'; for (const [px, py] of [[x1, y1], [x2, y2]]) { ctx.beginPath(); ctx.arc(px, py, 4, 0, Math.PI * 2); ctx.fill(); } }
        } else if (d.type === 'ellipse') {
            const x1 = this._timeToX(d.p1.time), y1 = this._priceToY(d.p1.price);
            const x2 = this._timeToX(d.p2.time), y2 = this._priceToY(d.p2.price);
            if (x1 == null || y1 == null || x2 == null || y2 == null) { ctx.restore(); return; }
            const cx = (x1 + x2) / 2, cy = (y1 + y2) / 2, rx = Math.abs(x2 - x1) / 2, ry = Math.abs(y2 - y1) / 2;
            ctx.fillStyle = (d.color || '#f0c040') + '15'; ctx.strokeStyle = d.color || '#f0c040';
            ctx.lineWidth = hovered ? 2 : 1; ctx.setLineDash([]);
            ctx.beginPath(); ctx.ellipse(cx, cy, Math.max(rx, 1), Math.max(ry, 1), 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
            if (hovered) { ctx.fillStyle = d.color || '#f0c040'; for (const [px, py] of [[x1, y1], [x2, y2]]) { ctx.beginPath(); ctx.arc(px, py, 4, 0, Math.PI * 2); ctx.fill(); } }
        } else if (d.type === 'circle') {
            const x1 = this._timeToX(d.p1.time), y1 = this._priceToY(d.p1.price);
            const x2 = this._timeToX(d.p2.time), y2 = this._priceToY(d.p2.price);
            if (x1 == null || y1 == null || x2 == null || y2 == null) { ctx.restore(); return; }
            const r = Math.hypot(x2 - x1, y2 - y1);
            ctx.fillStyle = (d.color || '#f0c040') + '15'; ctx.strokeStyle = d.color || '#f0c040';
            ctx.lineWidth = hovered ? 2 : 1; ctx.setLineDash([]);
            ctx.beginPath(); ctx.arc(x1, y1, Math.max(r, 1), 0, Math.PI * 2); ctx.fill(); ctx.stroke();
            if (hovered) { ctx.fillStyle = d.color || '#f0c040'; ctx.beginPath(); ctx.arc(x2, y2, 4, 0, Math.PI * 2); ctx.fill(); }
        } else if (d.type === 'channel') {
            this._renderChannel(d, hovered);
        } else if (d.type === 'fib') {
            this._renderFib(d, hovered);
        } else if (d.type === 'fibcircle') {
            this._renderFibCircle(d);
        } else if (d.type === 'gannbox') {
            this._renderGannBox(d, hovered);
        } else if (d.type === 'gannfan') {
            this._renderGannFan(d, hovered);
        } else if (d.type === 'longpos' || d.type === 'shortpos') {
            this._renderPosition(d, hovered);
        }
        ctx.restore();
    }

    _renderChannel(d, hovered) {
        const ctx = this.ctx;
        const x1 = this._timeToX(d.p1.time), y1 = this._priceToY(d.p1.price);
        const x2 = this._timeToX(d.p2.time), y2 = this._priceToY(d.p2.price);
        if (x1 == null || y1 == null || x2 == null || y2 == null) return;
        const color = d.color || '#38bdf8';
        ctx.strokeStyle = color;
        ctx.lineWidth = hovered ? 2 : (d.lineWidth || 1);
        ctx.setLineDash([]);

        // First line: p1 to p2
        ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();

        if (d.p3) {
            const x3 = this._timeToX(d.p3.time), y3 = this._priceToY(d.p3.price);
            if (x3 != null && y3 != null) {
                // Offset vector from p1 to p3
                const offX = x3 - x1, offY = y3 - y1;
                // Second parallel line
                ctx.beginPath(); ctx.moveTo(x1 + offX, y1 + offY); ctx.lineTo(x2 + offX, y2 + offY); ctx.stroke();
                // Midline dashed
                ctx.setLineDash([4, 3]);
                ctx.beginPath(); ctx.moveTo(x1 + offX / 2, y1 + offY / 2); ctx.lineTo(x2 + offX / 2, y2 + offY / 2); ctx.stroke();
                // Fill between
                ctx.setLineDash([]);
                ctx.fillStyle = color + '10';
                ctx.beginPath();
                ctx.moveTo(x1, y1); ctx.lineTo(x2, y2);
                ctx.lineTo(x2 + offX, y2 + offY); ctx.lineTo(x1 + offX, y1 + offY);
                ctx.closePath(); ctx.fill();
                if (hovered) {
                    this._drawHandle(ctx, x1, y1, color);
                    this._drawHandle(ctx, x2, y2, color);
                    this._drawHandle(ctx, x3, y3, color);
                }
            }
        } else {
            // Fallback: just the line
            if (hovered) {
                this._drawHandle(ctx, x1, y1, color);
                this._drawHandle(ctx, x2, y2, color);
            }
        }
    }

    _renderGannFan(d, hovered) {
        const ctx = this.ctx;
        const x1 = this._timeToX(d.p1.time), y1 = this._priceToY(d.p1.price);
        const x2 = this._timeToX(d.p2.time), y2 = this._priceToY(d.p2.price);
        if (x1 == null || y1 == null || x2 == null || y2 == null) return;
        const color = d.color || '#fb923c';
        const dx = x2 - x1, dy = y2 - y1;
        const baseLen = Math.hypot(dx, dy);
        if (baseLen < 1) return;

        // Direction sign: fan radiates from p1 toward p2
        const signX = Math.sign(dx) || 1;
        const signY = Math.sign(dy) || 1;
        // Use the 1x1 line distance as reference length
        const refLen = Math.max(baseLen, 200);

        // Gann angles: [label, time_units, price_units, opacity]
        const angles = [
            ['1x4', 1, 4, 0.35],
            ['1x3', 1, 3, 0.45],
            ['1x2', 1, 2, 0.55],
            ['1x1', 1, 1, 1.0],
            ['2x1', 2, 1, 0.55],
            ['3x1', 3, 1, 0.45],
            ['4x1', 4, 1, 0.35],
        ];

        // The 1x1 angle is 45° in pixel space based on p1->p2 direction
        // We normalize so that 1x1 goes at 45° from horizontal in the direction of p2
        const unitX = refLen; // horizontal pixel distance for 1 time unit
        const unitY = refLen; // vertical pixel distance for 1 price unit

        for (const [label, tUnits, pUnits, opacity] of angles) {
            const endX = x1 + signX * unitX * tUnits;
            const endY = y1 + signY * unitY * pUnits;

            ctx.globalAlpha = opacity;
            ctx.strokeStyle = color;
            ctx.lineWidth = label === '1x1' ? (hovered ? 2.5 : 2) : (hovered ? 1.5 : 1);
            ctx.setLineDash(label === '1x1' ? [] : [4, 3]);
            ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(endX, endY); ctx.stroke();

            // Label at end
            ctx.fillStyle = color;
            ctx.font = '9px Inter,sans-serif';
            ctx.fillText(label, endX + 3, endY - 3);
        }
        ctx.globalAlpha = 1.0;

        if (hovered) {
            this._drawHandle(ctx, x1, y1, color);
            this._drawHandle(ctx, x2, y2, color);
        }
    }

    _renderFib(d, hovered) {
        const ctx = this.ctx;
        const levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
        const bandColors = ['#ef535030', '#fb923c28', '#facc1525', '#4caf8225', '#38bdf828', '#a78bfa28'];
        const lineColors = ['#ef5350', '#fb923c', '#facc15', '#4caf82', '#38bdf8', '#a78bfa', '#a78bfa'];
        const range = d.p2.price - d.p1.price;
        const x1 = this._timeToX(d.p1.time), x2 = this._timeToX(d.p2.time);
        if (x1 == null || x2 == null) return;
        const left = Math.min(x1, x2), right = Math.max(x1, x2), rw = right - left;
        for (let i = 0; i < levels.length - 1; i++) {
            const ya = this._priceToY(d.p1.price + range * levels[i]);
            const yb = this._priceToY(d.p1.price + range * levels[i + 1]);
            if (ya != null && yb != null) { ctx.fillStyle = bandColors[i]; ctx.fillRect(left, Math.min(ya, yb), rw, Math.abs(yb - ya)); }
        }
        for (let i = 0; i < levels.length; i++) {
            const price = d.p1.price + range * levels[i];
            const y = this._priceToY(price);
            if (y == null) continue;
            ctx.strokeStyle = lineColors[i]; ctx.lineWidth = (levels[i] === 0 || levels[i] === 1) ? 1.5 : 1;
            ctx.setLineDash((levels[i] === 0 || levels[i] === 1) ? [] : [4, 3]);
            ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(right, y); ctx.stroke();
            ctx.fillStyle = lineColors[i]; ctx.font = '10px Inter,sans-serif';
            const lbl = (levels[i] === 0 ? '0%' : levels[i] === 1 ? '100%' : (levels[i] * 100).toFixed(1) + '%') + '  ' + price.toFixed(2);
            ctx.fillText(lbl, left + 4, y - 3);
        }
        if (hovered) {
            const yp1 = this._priceToY(d.p1.price), yp2 = this._priceToY(d.p2.price);
            ctx.fillStyle = '#a78bfa';
            if (yp1 != null) { ctx.beginPath(); ctx.arc(x1, yp1, 4, 0, Math.PI * 2); ctx.fill(); }
            if (yp2 != null) { ctx.beginPath(); ctx.arc(x2, yp2, 4, 0, Math.PI * 2); ctx.fill(); }
        }
    }

    _renderFibCircle(d) {
        const ctx = this.ctx;
        const x1 = this._timeToX(d.p1.time), y1 = this._priceToY(d.p1.price);
        const x2 = this._timeToX(d.p2.time), y2 = this._priceToY(d.p2.price);
        if (x1 == null || y1 == null || x2 == null || y2 == null) return;
        const maxR = Math.hypot(x2 - x1, y2 - y1);
        const levels = [0.236, 0.382, 0.5, 0.618, 0.786, 1.0];
        const color = d.color || '#a78bfa';
        for (const lvl of levels) {
            ctx.strokeStyle = lvl === 1 ? color : color + '88'; ctx.lineWidth = 1;
            ctx.setLineDash(lvl === 0.5 ? [] : [3, 3]);
            ctx.beginPath(); ctx.arc(x1, y1, maxR * lvl, 0, Math.PI * 2); ctx.stroke();
        }
        ctx.fillStyle = color; ctx.font = '9px Inter,sans-serif';
        for (const lvl of levels) ctx.fillText((lvl * 100).toFixed(1) + '%', x1 + maxR * lvl + 3, y1 - 3);
    }

    _renderGannBox(d, hovered) {
        const ctx = this.ctx;
        const x1 = this._timeToX(d.p1.time), y1 = this._priceToY(d.p1.price);
        const x2 = this._timeToX(d.p2.time), y2 = this._priceToY(d.p2.price);
        if (x1 == null || y1 == null || x2 == null || y2 == null) return;
        const color = d.color || '#fb923c';
        const left = Math.min(x1, x2), top = Math.min(y1, y2), bw = Math.abs(x2 - x1), bh = Math.abs(y2 - y1);
        ctx.strokeStyle = color; ctx.lineWidth = hovered ? 2 : 1; ctx.setLineDash([]);
        ctx.strokeRect(left, top, bw, bh);
        ctx.setLineDash([2, 2]); ctx.strokeStyle = color + '66';
        for (const f of [0.25, 0.5, 0.75]) {
            ctx.beginPath(); ctx.moveTo(left + bw * f, top); ctx.lineTo(left + bw * f, top + bh); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(left, top + bh * f); ctx.lineTo(left + bw, top + bh * f); ctx.stroke();
        }
        ctx.setLineDash([]); ctx.strokeStyle = color;
        ctx.beginPath(); ctx.moveTo(left, top); ctx.lineTo(left + bw, top + bh); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(left + bw, top); ctx.lineTo(left, top + bh); ctx.stroke();
    }

    _renderPosition(d, hovered) {
        const ctx = this.ctx;
        const x1 = this._timeToX(d.p1.time), x2 = this._timeToX(d.p2.time);
        const entryY = this._priceToY(d.p1.price), tpY = this._priceToY(d.p2.price), slY = this._priceToY(d.p3.price);
        if (x1 == null || x2 == null || entryY == null || tpY == null || slY == null) return;
        const left = Math.min(x1, x2), right = Math.max(x1, x2), rw = right - left;
        // TP zone
        ctx.fillStyle = '#4caf8225'; ctx.fillRect(left, Math.min(entryY, tpY), rw, Math.abs(tpY - entryY));
        ctx.strokeStyle = '#4caf82'; ctx.lineWidth = 1; ctx.setLineDash([]); ctx.strokeRect(left, Math.min(entryY, tpY), rw, Math.abs(tpY - entryY));
        // SL zone
        ctx.fillStyle = '#e05c5c25'; ctx.fillRect(left, Math.min(entryY, slY), rw, Math.abs(slY - entryY));
        ctx.strokeStyle = '#e05c5c'; ctx.strokeRect(left, Math.min(entryY, slY), rw, Math.abs(slY - entryY));
        // Entry line
        ctx.strokeStyle = '#f0c040'; ctx.setLineDash([4, 2]); ctx.beginPath(); ctx.moveTo(left, entryY); ctx.lineTo(right, entryY); ctx.stroke();
        // Labels
        const risk = Math.abs(d.p3.price - d.p1.price), reward = Math.abs(d.p2.price - d.p1.price);
        const rr = risk > 0 ? (reward / risk).toFixed(1) : '—';
        ctx.setLineDash([]); ctx.font = '10px Inter,sans-serif';
        ctx.fillStyle = '#4caf82'; ctx.fillText('TP ' + d.p2.price.toFixed(2), left + 3, tpY < entryY ? Math.min(entryY, tpY) - 3 : Math.max(entryY, tpY) + 12);
        ctx.fillStyle = '#e05c5c'; ctx.fillText('SL ' + d.p3.price.toFixed(2), left + 3, slY > entryY ? Math.max(entryY, slY) + 12 : Math.min(entryY, slY) - 3);
        ctx.fillStyle = '#f0c040'; ctx.fillText('Entry ' + d.p1.price.toFixed(2) + '  R:R 1:' + rr, left + 3, entryY - 3);
        if (hovered) {
            ctx.fillStyle = '#4caf82'; ctx.beginPath(); ctx.arc(right, tpY, 4, 0, Math.PI * 2); ctx.fill();
            ctx.fillStyle = '#e05c5c'; ctx.beginPath(); ctx.arc(right, slY, 4, 0, Math.PI * 2); ctx.fill();
            ctx.fillStyle = '#f0c040'; ctx.beginPath(); ctx.arc(left, entryY, 4, 0, Math.PI * 2); ctx.fill();
        }
    }

    _renderPreview() {
        const ds = this._drawState, ctx = this.ctx;
        ctx.save(); ctx.globalAlpha = 0.6;

        if (ds.tool === 'line') {
            ctx.strokeStyle = ds.color; this._applyDash(ctx, ds.lineStyle, ds.lineWidth);
            ctx.beginPath(); ctx.moveTo(ds.startX, ds.startY); ctx.lineTo(ds.curX, ds.curY); ctx.stroke();
        } else if (ds.tool === 'arrow') {
            ctx.strokeStyle = ds.color; ctx.lineWidth = 2; ctx.setLineDash([]);
            ctx.beginPath(); ctx.moveTo(ds.startX, ds.startY); ctx.lineTo(ds.curX, ds.curY); ctx.stroke();
            const ang = Math.atan2(ds.curY - ds.startY, ds.curX - ds.startX);
            ctx.fillStyle = ds.color; ctx.beginPath();
            ctx.moveTo(ds.curX, ds.curY);
            ctx.lineTo(ds.curX - 10 * Math.cos(ang - 0.4), ds.curY - 10 * Math.sin(ang - 0.4));
            ctx.lineTo(ds.curX - 10 * Math.cos(ang + 0.4), ds.curY - 10 * Math.sin(ang + 0.4));
            ctx.closePath(); ctx.fill();
        } else if (ds.tool === 'rect') {
            const rx = Math.min(ds.startX, ds.curX), ry = Math.min(ds.startY, ds.curY);
            const rw = Math.abs(ds.curX - ds.startX), rh = Math.abs(ds.curY - ds.startY);
            ctx.fillStyle = ds.color + '18'; ctx.fillRect(rx, ry, rw, rh);
            ctx.strokeStyle = ds.color; ctx.lineWidth = 1; ctx.setLineDash([]); ctx.strokeRect(rx, ry, rw, rh);
        } else if (ds.tool === 'ellipse') {
            const cx = (ds.startX + ds.curX) / 2, cy = (ds.startY + ds.curY) / 2;
            const rx = Math.abs(ds.curX - ds.startX) / 2, ry = Math.abs(ds.curY - ds.startY) / 2;
            ctx.fillStyle = ds.color + '15'; ctx.strokeStyle = ds.color; ctx.lineWidth = 1; ctx.setLineDash([]);
            ctx.beginPath(); ctx.ellipse(cx, cy, Math.max(rx, 1), Math.max(ry, 1), 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        } else if (ds.tool === 'circle') {
            const r = Math.hypot(ds.curX - ds.startX, ds.curY - ds.startY);
            ctx.fillStyle = ds.color + '15'; ctx.strokeStyle = ds.color; ctx.lineWidth = 1; ctx.setLineDash([]);
            ctx.beginPath(); ctx.arc(ds.startX, ds.startY, Math.max(r, 1), 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        } else if (ds.tool === 'channel') {
            ctx.strokeStyle = ds.color; ctx.lineWidth = 1; ctx.setLineDash([]);
            if (ds.phase === 1) {
                // Drawing first line from p1 toward cursor
                ctx.beginPath(); ctx.moveTo(ds.startX, ds.startY); ctx.lineTo(ds.curX, ds.curY); ctx.stroke();
            } else if (ds.phase === 2) {
                // First line locked, showing parallel offset
                const x1 = ds.startX, y1 = ds.startY, x2 = ds.p2X, y2 = ds.p2Y;
                ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
                const offX = ds.curX - x1, offY = ds.curY - y1;
                ctx.beginPath(); ctx.moveTo(x1 + offX, y1 + offY); ctx.lineTo(x2 + offX, y2 + offY); ctx.stroke();
                ctx.setLineDash([4, 3]);
                ctx.beginPath(); ctx.moveTo(x1 + offX / 2, y1 + offY / 2); ctx.lineTo(x2 + offX / 2, y2 + offY / 2); ctx.stroke();
                ctx.setLineDash([]);
                ctx.fillStyle = ds.color + '10';
                ctx.beginPath();
                ctx.moveTo(x1, y1); ctx.lineTo(x2, y2);
                ctx.lineTo(x2 + offX, y2 + offY); ctx.lineTo(x1 + offX, y1 + offY);
                ctx.closePath(); ctx.fill();
            }
        } else if (ds.tool === 'fib') {
            const sp = this._yToPrice(ds.startY), cp = this._yToPrice(ds.curY);
            if (sp != null && cp != null) {
                const levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1], range = cp - sp;
                const bandColors = ['#ef535020', '#fb923c18', '#facc1518', '#4caf8218', '#38bdf818', '#a78bfa18'];
                const lineColors = ['#ef5350', '#fb923c', '#facc15', '#4caf82', '#38bdf8', '#a78bfa', '#a78bfa'];
                const left = Math.min(ds.startX, ds.curX), right = Math.max(ds.startX, ds.curX), rw = right - left;
                for (let i = 0; i < levels.length - 1; i++) {
                    const ya = this._priceToY(sp + range * levels[i]), yb = this._priceToY(sp + range * levels[i + 1]);
                    if (ya != null && yb != null) { ctx.fillStyle = bandColors[i]; ctx.fillRect(left, Math.min(ya, yb), rw, Math.abs(yb - ya)); }
                }
                for (let i = 0; i < levels.length; i++) {
                    const y = this._priceToY(sp + range * levels[i]);
                    if (y == null) continue;
                    ctx.strokeStyle = lineColors[i] + '88'; ctx.lineWidth = 1; ctx.setLineDash([4, 3]);
                    ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(right, y); ctx.stroke();
                    ctx.fillStyle = lineColors[i]; ctx.font = '10px Inter,sans-serif';
                    ctx.fillText((levels[i] * 100).toFixed(1) + '%', left + 4, y - 3);
                }
            }
        } else if (ds.tool === 'fibcircle') {
            const maxR = Math.hypot(ds.curX - ds.startX, ds.curY - ds.startY);
            for (const lvl of [0.236, 0.382, 0.5, 0.618, 0.786, 1.0]) {
                ctx.strokeStyle = ds.color + '88'; ctx.lineWidth = 1; ctx.setLineDash([3, 3]);
                ctx.beginPath(); ctx.arc(ds.startX, ds.startY, maxR * lvl, 0, Math.PI * 2); ctx.stroke();
            }
        } else if (ds.tool === 'gannbox') {
            const left = Math.min(ds.startX, ds.curX), top = Math.min(ds.startY, ds.curY);
            const bw = Math.abs(ds.curX - ds.startX), bh = Math.abs(ds.curY - ds.startY);
            ctx.strokeStyle = ds.color; ctx.lineWidth = 1; ctx.setLineDash([]);
            ctx.strokeRect(left, top, bw, bh);
            ctx.beginPath(); ctx.moveTo(left, top); ctx.lineTo(left + bw, top + bh); ctx.stroke();
        } else if (ds.tool === 'gannfan') {
            // Preview: show radiating lines from start toward cursor
            const dx = ds.curX - ds.startX, dy = ds.curY - ds.startY;
            const baseLen = Math.hypot(dx, dy);
            if (baseLen > 1) {
                const signX = Math.sign(dx) || 1, signY = Math.sign(dy) || 1;
                const refLen = Math.max(baseLen, 150);
                const angles = [['1x4',1,4,0.35],['1x3',1,3,0.45],['1x2',1,2,0.55],['1x1',1,1,1.0],['2x1',2,1,0.55],['3x1',3,1,0.45],['4x1',4,1,0.35]];
                for (const [label, tU, pU, opacity] of angles) {
                    ctx.globalAlpha = 0.6 * opacity;
                    ctx.strokeStyle = ds.color;
                    ctx.lineWidth = label === '1x1' ? 2 : 1;
                    ctx.setLineDash(label === '1x1' ? [] : [4, 3]);
                    ctx.beginPath(); ctx.moveTo(ds.startX, ds.startY);
                    ctx.lineTo(ds.startX + signX * refLen * tU, ds.startY + signY * refLen * pU);
                    ctx.stroke();
                }
                ctx.globalAlpha = 0.6;
            }
        } else if (ds.tool === 'longpos' || ds.tool === 'shortpos') {
            const entryY = ds.startY;
            if (ds.phase === 1) {
                const tpY = ds.curY;
                const left = Math.min(ds.startX, ds.curX), rw = Math.abs(ds.curX - ds.startX);
                ctx.fillStyle = '#4caf8220'; ctx.fillRect(left, Math.min(entryY, tpY), rw, Math.abs(tpY - entryY));
                ctx.strokeStyle = '#f0c040'; ctx.setLineDash([4, 2]);
                ctx.beginPath(); ctx.moveTo(left, entryY); ctx.lineTo(left + rw, entryY); ctx.stroke();
            } else if (ds.phase === 2) {
                const tpY = this._priceToY(ds.tpPrice);
                const slY = ds.slY || ds.curY;
                const x2 = this._timeToX(ds.tpTime);
                const left = Math.min(ds.startX, x2 || ds.startX), rw = Math.abs((x2 || ds.startX) - ds.startX);
                if (tpY != null) { ctx.fillStyle = '#4caf8220'; ctx.fillRect(left, Math.min(entryY, tpY), rw, Math.abs(tpY - entryY)); }
                ctx.fillStyle = '#e05c5c20'; ctx.fillRect(left, Math.min(entryY, slY), rw, Math.abs(slY - entryY));
                ctx.strokeStyle = '#f0c040'; ctx.setLineDash([4, 2]);
                ctx.beginPath(); ctx.moveTo(left, entryY); ctx.lineTo(left + rw, entryY); ctx.stroke();
            }
        }
        ctx.restore();
    }

    // ── Public API ───────────────────────────────────────────────────────────
    clear() { this._drawState = null; this.drawings = []; this._scheduleRedraw(); }
    remove(id) {
        this.drawings = this.drawings.filter(d => d.id !== id);
        this._scheduleRedraw();
        if (window._persistedDrawings !== undefined) window._persistedDrawings = this.toJSON();
    }
    toJSON() { return this.drawings; }
    fromJSON(arr) { this.drawings = arr || []; this._scheduleRedraw(); }
}

// Text tool extension
(function() {
    const origRender = CanvasOverlay.prototype._renderDrawing;
    CanvasOverlay.prototype._renderDrawing = function(d, hovered) {
        if (d.type === 'text') {
            const ctx = this.ctx;
            const x = this._timeToX(d.p1.time);
            const y = this._priceToY(d.p1.price);
            if (x == null || y == null) return;
            ctx.save();
            const fontSize = d.fontSize || 12;
            ctx.font = fontSize + 'px Inter, sans-serif';
            ctx.fillStyle = d.color || '#f0c040';
            const lines = (d.text || 'Text').split('\n');
            lines.forEach((line, i) => ctx.fillText(line, x, y + i * (fontSize + 2)));
            if (hovered) this._drawHandle(ctx, x, y, d.color || '#f0c040');
            ctx.restore();
            return;
        }
        origRender.call(this, d, hovered);
    };

    const origMouseDown = CanvasOverlay.prototype._onMouseDown;
    CanvasOverlay.prototype._onMouseDown = function(e) {
        if (this.activeTool === 'text') {
            const rect = this.chartEl.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            const time = this._xToTime(x);
            const price = this._yToPrice(y);
            if (time == null || price == null) return;
            const text = prompt('Enter text:');
            if (!text) return;
            this.drawings.push({ type: 'text', p1: { time, price }, text, color: this.activeColor, fontSize: 12, lineStyle: 'solid', lineWidth: 1, id: Date.now() });
            this.activeTool = null;
            this._interactEl.style.pointerEvents = 'none';
            this._requestRedraw();
            return;
        }
        origMouseDown.call(this, e);
    };

    // Double-click to edit text - attach to chartEl
    document.addEventListener('dblclick', function(e) {
        if (!window.drawMgr) return;
        const chartEl = window.drawMgr.chartEl;
        if (!chartEl) return;
        const rect = chartEl.getBoundingClientRect();
        if (e.clientX < rect.left || e.clientX > rect.right || e.clientY < rect.top || e.clientY > rect.bottom) return;
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        for (const d of window.drawMgr.drawings) {
            if (d.type !== 'text') continue;
            const dx = window.drawMgr._timeToX(d.p1.time);
            const dy = window.drawMgr._priceToY(d.p1.price);
            if (dx == null || dy == null) continue;
            if (Math.abs(x - dx) < 60 && Math.abs(y - dy) < 16) {
                const newText = prompt('Edit text:', d.text);
                if (newText !== null) { d.text = newText; window.drawMgr._requestRedraw(); }
                return;
            }
        }
    });
})();
