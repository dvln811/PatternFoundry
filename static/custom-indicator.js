/**
 * custom-indicator.js - Sandboxed execution engine for user-defined indicators.
 *
 * Users write JS that receives `candles` (array of {time, open, high, low, close, volume})
 * and helper functions. They return an array of {time, value} or {time, value, color}.
 *
 * Execution is sandboxed via Function() with no access to DOM, window, fetch, etc.
 */

const CustomIndicator = {

  // Helper functions available inside user code
  helpers: {
    sma(candles, period, field = 'close') {
      const out = [];
      for (let i = period - 1; i < candles.length; i++) {
        let s = 0;
        for (let j = i - period + 1; j <= i; j++) s += candles[j][field];
        out.push({ time: candles[i].time, value: Math.round(s / period * 100) / 100 });
      }
      return out;
    },

    ema(candles, period, field = 'close') {
      const out = [], k = 2 / (period + 1);
      let val = null;
      for (let i = 0; i < candles.length; i++) {
        const v = candles[i][field];
        if (val === null) {
          if (i < period - 1) continue;
          let s = 0;
          for (let j = i - period + 1; j <= i; j++) s += candles[j][field];
          val = s / period;
        } else {
          val = v * k + val * (1 - k);
        }
        out.push({ time: candles[i].time, value: Math.round(val * 100) / 100 });
      }
      return out;
    },

    rsi(candles, period) {
      const out = [];
      let gains = 0, losses = 0;
      for (let i = 1; i < candles.length; i++) {
        const d = candles[i].close - candles[i - 1].close;
        if (i <= period) {
          if (d > 0) gains += d; else losses -= d;
          if (i === period) {
            gains /= period; losses /= period;
            const rs = losses === 0 ? 100 : gains / losses;
            out.push({ time: candles[i].time, value: Math.round((100 - 100 / (1 + rs)) * 100) / 100 });
          }
        } else {
          gains = (gains * (period - 1) + (d > 0 ? d : 0)) / period;
          losses = (losses * (period - 1) + (d < 0 ? -d : 0)) / period;
          const rs = losses === 0 ? 100 : gains / losses;
          out.push({ time: candles[i].time, value: Math.round((100 - 100 / (1 + rs)) * 100) / 100 });
        }
      }
      return out;
    },

    atr(candles, period) {
      const out = [], trs = [];
      for (let i = 1; i < candles.length; i++) {
        const h = candles[i].high, l = candles[i].low, pc = candles[i - 1].close;
        trs.push(Math.max(h - l, Math.abs(h - pc), Math.abs(l - pc)));
        if (trs.length >= period) {
          out.push({ time: candles[i].time, value: Math.round(trs.slice(-period).reduce((a, b) => a + b) / period * 100) / 100 });
        }
      }
      return out;
    },

    stdev(candles, period, field = 'close') {
      const out = [];
      for (let i = period - 1; i < candles.length; i++) {
        let s = 0;
        for (let j = i - period + 1; j <= i; j++) s += candles[j][field];
        const mean = s / period;
        let sq = 0;
        for (let j = i - period + 1; j <= i; j++) sq += (candles[j][field] - mean) ** 2;
        out.push({ time: candles[i].time, value: Math.round(Math.sqrt(sq / period) * 100) / 100 });
      }
      return out;
    },

    highest(candles, period, field = 'high') {
      const out = [];
      for (let i = period - 1; i < candles.length; i++) {
        let mx = -Infinity;
        for (let j = i - period + 1; j <= i; j++) mx = Math.max(mx, candles[j][field]);
        out.push({ time: candles[i].time, value: mx });
      }
      return out;
    },

    lowest(candles, period, field = 'low') {
      const out = [];
      for (let i = period - 1; i < candles.length; i++) {
        let mn = Infinity;
        for (let j = i - period + 1; j <= i; j++) mn = Math.min(mn, candles[j][field]);
        out.push({ time: candles[i].time, value: mn });
      }
      return out;
    },

    crossover(a, b) {
      // Returns array of {time, value: 1 or 0} where 1 = a crossed above b
      const out = [];
      const len = Math.min(a.length, b.length);
      for (let i = 1; i < len; i++) {
        out.push({ time: a[i].time, value: (a[i].value > b[i].value && a[i-1].value <= b[i-1].value) ? 1 : 0 });
      }
      return out;
    },

    crossunder(a, b) {
      const out = [];
      const len = Math.min(a.length, b.length);
      for (let i = 1; i < len; i++) {
        out.push({ time: a[i].time, value: (a[i].value < b[i].value && a[i-1].value >= b[i-1].value) ? 1 : 0 });
      }
      return out;
    },

    // Align two indicator arrays by timestamp, return matched pairs
    align(a, b) {
      const bMap = {};
      b.forEach(p => bMap[p.time] = p.value);
      return a.filter(p => bMap[p.time] !== undefined).map(p => ({
        time: p.time, a: p.value, b: bMap[p.time]
      }));
    },
  },

  /**
   * Execute user code in a sandboxed context.
   * @param {string} code - User's indicator code
   * @param {Array} candles - OHLCV candle data
   * @returns {Array|Object} - Array of {time, value} or {error: string}
   */
  execute(code, candles) {
    try {
      const helperNames = Object.keys(this.helpers);
      const rawHelpers = {};
      for (const [name, fn] of Object.entries(this.helpers)) {
        rawHelpers[name] = fn;
      }

      const fnBody = `
        "use strict";
        const {${helperNames.join(',')}} = __helpers__;
        const close = candles.map(c => c.close);
        const open = candles.map(c => c.open);
        const high = candles.map(c => c.high);
        const low = candles.map(c => c.low);
        const volume = candles.map(c => c.volume);
        ${code}
      `;

      const fn = new Function('candles', '__helpers__', fnBody);
      const result = fn(candles, rawHelpers);

      // Support multi-line: { lines: [{data, label, color, style}] }
      if (result && result.lines && Array.isArray(result.lines)) {
        return { multiLine: true, lines: result.lines };
      }
      if (!Array.isArray(result)) {
        return { error: 'Return an array of {time, value} or {lines: [...]}' };
      }
      return result;
    } catch (e) {
      return { error: e.message };
    }
  },

  /**
   * Save a custom indicator to localStorage.
   */
  save(name, code, displayType, color) {
    const saved = JSON.parse(localStorage.getItem('pf_custom_indicators') || '[]');
    const existing = saved.findIndex(s => s.name === name);
    const entry = { name, code, displayType, color, savedAt: Date.now() };
    if (existing >= 0) saved[existing] = entry;
    else saved.push(entry);
    localStorage.setItem('pf_custom_indicators', JSON.stringify(saved));
  },

  /**
   * Load all saved custom indicators.
   */
  loadAll() {
    return JSON.parse(localStorage.getItem('pf_custom_indicators') || '[]');
  },

  /**
   * Delete a saved custom indicator.
   */
  remove(name) {
    const saved = JSON.parse(localStorage.getItem('pf_custom_indicators') || '[]');
    localStorage.setItem('pf_custom_indicators', JSON.stringify(saved.filter(s => s.name !== name)));
  },
};
