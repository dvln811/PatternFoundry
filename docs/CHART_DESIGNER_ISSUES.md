# Chart Designer — 4 Issues Analysis & Fix Guide

## Issue 1: Generation Produces Candles Into RTH (should stop at 09:29)

### Root Cause

**File:** `app.py` → `character_generate()` (line ~637)  
**File:** `generators/sessions.py` → `_build_session_timestamps()`

The `/api/character/generate` endpoint calls:
```python
df = generate_v2(n, spec, seed=seed)
candles = apply_session_structure(df, gap_cfg, tf_seconds=60, seed=seed)
```

`apply_session_structure` calls `_build_session_timestamps(n, tf_seconds=60)` which starts at `2024-01-01 06:00 UTC` and advances 1 minute at a time, assigning sessions based on time-of-day:
- 06:00-09:29 → pre_market
- 09:30-15:59 → rth
- 16:00-17:59 → post_market
- 18:00-02:59 → overnight
- 03:00-05:59 → london

With "1 session" selected, `n=1250` candles are generated. 1250 minutes from 06:00 = ~20.8 hours, ending at ~02:50 the next day. This includes a FULL RTH day (09:30-16:00 = 390 candles) within the generated data.

The user expectation: generated history should be the **pre-session context** (off-hours only), stopping at 09:29 so the tick engine can take over for RTH playback.

### The Fix

After `apply_session_structure` returns the candles list, **truncate to only include candles where `session != 'rth'` at the tail end**. Specifically: find the LAST rth→non-rth transition and keep everything after it (or keep everything up to the first RTH open if we want pre-market history only).

The cleanest approach: truncate the result to stop at the last candle before the final RTH session starts.

```python
# In character_generate(), after apply_session_structure:
candles = apply_session_structure(df, gap_cfg, tf_seconds=60, seed=seed)

# Truncate: stop at the last bar before RTH opens (09:29)
# Find the last RTH open boundary (last transition from non-rth to rth)
last_rth_start = None
for i in range(1, len(candles)):
    if candles[i]['session'] == 'rth' and candles[i-1]['session'] != 'rth':
        last_rth_start = i
if last_rth_start is not None:
    candles = candles[:last_rth_start]
```

This keeps all history up to 09:29 of the final day, leaving RTH for the tick engine.

**Note on `n` values:** The dropdown values (1250, 6250, etc.) were calculated for RTH-only bars. With full 24hr sessions, you may want to adjust these or just accept that fewer RTH days appear (since off-hours bars consume the count). Alternatively, generate enough bars to cover the desired number of full-session days, then truncate at the final RTH boundary.

---

## Issue 2: Tick Engine Performance/Lag at 60x Speed

### Root Cause

**File:** `templates/chartdesigner.html` → `startTickPlayback()` (line ~810)

```javascript
const speed = parseFloat(document.getElementById('tick-speed').value);
const interval = Math.max(16, Math.round(1000 / speed));

_tickPreviewTimer = setInterval(() => {
    // ... process ONE tick ...
    candleSeries.update({...});  // ← chart repaint triggered here
    volSeries.update({...});     // ← another repaint
}, interval);
```

At 60x speed: `interval = Math.max(16, 1000/60) = 16ms`. This means:
- 1 tick processed per 16ms
- `candleSeries.update()` called 60× per second
- `volSeries.update()` called 60× per second
- Each `.update()` triggers a full chart canvas repaint

That's **120 chart repaints per second** — way too many. The browser's refresh rate is 60fps max, so half are wasted and cause jank.

### The Fix

Batch multiple ticks per interval call, but only update the chart ONCE at the end of the batch:

```javascript
_tickPreviewTimer = setInterval(() => {
    // Process multiple ticks per frame at high speeds
    const ticksPerFrame = Math.max(1, Math.round(speed / 10));
    for (let t_i = 0; t_i < ticksPerFrame; t_i++) {
        if (_tickPreviewIdx >= _tickPreviewData.length) { stopTickPreview(); return; }
        const t = _tickPreviewData[_tickPreviewIdx++];
        
        // ... all the tick processing logic (candle building, display candle, debug panel) ...
        // BUT do NOT call candleSeries.update() inside this loop
    }
    
    // Single chart update after processing the batch
    if (window._displayCandle) {
        candleSeries.update({ time: window._displayCandle.time, open: window._displayCandle.open,
            high: window._displayCandle.high, low: window._displayCandle.low, close: window._displayCandle.close });
        volSeries.update({ time: window._displayCandle.time, value: window._displayCandle.volume,
            color: window._displayCandle.close >= window._displayCandle.open ? '#4caf8266' : '#e05c5c66' });
    }
}, interval);
```

At 60x: `ticksPerFrame = 6`, so 6 ticks processed per 16ms interval, with only 1 chart update. That's 60 chart updates/sec (matching display refresh) while processing 360 ticks/sec.

For even smoother playback, consider using `requestAnimationFrame` instead of `setInterval`:

```javascript
let _lastTickFrame = 0;
function tickFrame(timestamp) {
    if (!_tickPreviewData || _tickPreviewIdx >= _tickPreviewData.length) { stopTickPreview(); return; }
    const elapsed = timestamp - _lastTickFrame;
    const ticksToProcess = Math.max(1, Math.round(speed * elapsed / 1000));
    _lastTickFrame = timestamp;
    
    for (let i = 0; i < ticksToProcess && _tickPreviewIdx < _tickPreviewData.length; i++) {
        // process tick...
    }
    // single chart update
    candleSeries.update({...});
    _tickPreviewTimer = requestAnimationFrame(tickFrame);
}
```

---

## Issue 3: Off-Hours Shading Lag on Chart Move

### Root Cause

**File:** `templates/chartdesigner.html` (line ~556)

```javascript
function throttledShading() {
    if (_shadingTimer) return;
    _shadingTimer = setTimeout(() => { _shadingTimer = null; drawOffHoursShading(); }, 200);
}
chart.timeScale().subscribeVisibleTimeRangeChange(throttledShading);
```

There's a **200ms throttle** wrapping the shading function. When you pan/scroll the chart, the shading doesn't redraw for 200ms — creating a visible lag where the chart moves but the shading stays in place momentarily.

### Comparison with Simulator (chart.html)

The Simulator subscribes directly with NO throttle:
```javascript
chart.timeScale().subscribeVisibleTimeRangeChange(drawOffHoursShading);
```

This is why the Simulator's shading "sticks" perfectly during scrolling — it redraws synchronously with every visible range change.

### The Fix

Remove the throttle entirely. Replace lines 556-557 with:

```javascript
chart.timeScale().subscribeVisibleTimeRangeChange(drawOffHoursShading);
```

Also delete the `_shadingTimer` variable wherever it's declared.

The `drawOffHoursShading` function using `logicalToCoordinate` is lightweight enough to run on every scroll event without performance concern — it's just iterating an array and doing a few `fillRect` calls on a canvas.

---

## Issue 4: Tick Engine Generates Off-Hours Data During RTH

### Root Cause — Two Sub-Problems

#### A) Frontend timestamp calculation (chartdesigner.html, line ~817)

```javascript
const minuteIdx = Math.floor((_tickPreviewIdx - 1) / 60);
const candleTime = _lastHistTime + (minuteIdx + 1) * 60;
```

This just increments from the last history timestamp — it has NO session awareness. If history ends at 05:55 (pre-market), the tick candles get timestamps 05:56, 05:57, etc. — which are off-hours timestamps even though we want RTH playback.

#### B) Backend tick-preview data generation (app.py, line ~682)

```python
df = generate_v2(n_candles, spec, seed=seed)
candles_structured = apply_session_structure(df, gap_cfg, tf_seconds=60, seed=seed)
mini_df = pd.DataFrame({...from candles_structured[:n_candles]...})
ticks = generate_microstructure_ticks(candle_dicts, tick_cfg)
```

`apply_session_structure` starts timestamps at `2024-01-01 06:00` — the first candles are pre_market (06:00-09:29) with dampened volatility/volume. If `n_candles=390`, the first 210 bars are off-hours (dampened) and only the last 180 are RTH. The ticks generated from these candles inherit the dampened characteristics.

### The Fix

#### Backend fix (app.py `character_tick_preview`):

Don't use `apply_session_structure` for the tick preview. Instead, generate raw candles and stamp them as RTH directly:

```python
def character_tick_preview():
    data = request.get_json()
    seed = int(data.get('seed', 42))
    n_candles = int(data.get('n_candles', 30))

    spec = _build_spec_from_payload(data)
    gap_cfg = extract_gap_cfg(spec)
    disable_internal_gaps(spec)
    df = generate_v2(n_candles, spec, seed=seed)

    # Stamp as RTH (09:30 onward, 1-min intervals) — NO session dampening
    import pandas as pd
    rth_start = pd.Timestamp('2024-01-02 09:30:00', tz='UTC')  # a weekday
    mini_df = pd.DataFrame({
        'Timestamp': pd.date_range(start=rth_start, periods=n_candles, freq='1min'),
        'Open': df['Open'].values[:n_candles],
        'High': df['High'].values[:n_candles],
        'Low': df['Low'].values[:n_candles],
        'Close': df['Close'].values[:n_candles],
        'Volume': df['Volume'].values[:n_candles],
    })

    # ... rest of tick generation unchanged ...
    candle_dicts = [{
        'time': int(row['Timestamp'].timestamp()),
        'open': round(float(row['Open']), 2), 'high': round(float(row['High']), 2),
        'low': round(float(row['Low']), 2), 'close': round(float(row['Close']), 2),
        'volume': int(row['Volume']),
    } for _, row in mini_df.iterrows()]

    ticks = generate_microstructure_ticks(candle_dicts, tick_cfg)
    return jsonify({'ticks': ticks, 'candles': candle_dicts, 'seed': seed})
```

This ensures tick data has full RTH volatility/volume characteristics (no dampening).

#### Frontend fix (chartdesigner.html):

After fixing Issue 1 (history truncated at 09:29), `_lastHistTime` will be the timestamp of the 09:29 bar. The tick candle time calculation `_lastHistTime + (minuteIdx + 1) * 60` will then correctly produce 09:30, 09:31, etc. — proper RTH timestamps.

If you want belt-and-suspenders, explicitly anchor to 09:30:

```javascript
// In runTickPreview(), after setting _lastHistTime:
_lastHistTime = allCandles.length ? allCandles[allCandles.length - 1].time : 0;
// Ensure tick candles start at 09:30 of the session day
const lastDate = new Date(_lastHistTime * 1000);
const rthOpen = new Date(Date.UTC(lastDate.getUTCFullYear(), lastDate.getUTCMonth(), lastDate.getUTCDate(), 9, 30));
if (rthOpen.getTime() / 1000 > _lastHistTime) {
    _lastHistTime = Math.floor(rthOpen.getTime() / 1000) - 60; // so first candle = 09:30
}
```

---

## File Reference

| Issue | File(s) | Lines |
|-------|---------|-------|
| 1 - RTH overflow | `app.py` (`character_generate`) | ~637-658 |
| 2 - Tick lag | `templates/chartdesigner.html` (`startTickPlayback`) | ~810-870 |
| 3 - Shading throttle | `templates/chartdesigner.html` | ~556-557 |
| 4a - Tick timestamps | `templates/chartdesigner.html` (`startTickPlayback`) | ~817 |
| 4b - Tick dampening | `app.py` (`character_tick_preview`) | ~682-730 |

## Dependencies Between Fixes

- Fix **Issue 1 first** — it ensures history ends at 09:29, which makes Issue 4's frontend fix (timestamp anchoring) work correctly.
- Fix **Issue 3** is independent and trivial — just remove the throttle.
- Fix **Issue 2** is independent — batching ticks per frame.
- Fix **Issue 4 backend** is independent — stop using apply_session_structure for tick-preview.
- Fix **Issue 4 frontend** depends on Issue 1 being fixed (so _lastHistTime lands at 09:29).
