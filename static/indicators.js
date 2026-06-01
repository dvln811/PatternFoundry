// indicators.js - PatternFoundry client-side indicator math
// Input: [{time, open, high, low, close, volume}]
// Output: [{time, value}] or structured object for multi-line indicators

const Indicators = {

  sma(candles, period) {
    const out = [];
    for (let i = period - 1; i < candles.length; i++) {
      let s = 0;
      for (let j = i - period + 1; j <= i; j++) s += candles[j].close;
      out.push({ time: candles[i].time, value: Math.round(s / period * 100) / 100 });
    }
    return out;
  },

  ema(candles, period) {
    const out = [], k = 2 / (period + 1);
    let val = null;
    for (let i = 0; i < candles.length; i++) {
      if (val === null) {
        if (i < period - 1) continue;
        let s = 0;
        for (let j = i - period + 1; j <= i; j++) s += candles[j].close;
        val = s / period;
      } else {
        val = candles[i].close * k + val * (1 - k);
      }
      out.push({ time: candles[i].time, value: Math.round(val * 100) / 100 });
    }
    return out;
  },

  vwap(candles) {
    const out = [];
    let cumTPV = 0, cumVol = 0, lastDay = null;
    for (const c of candles) {
      const day = new Date(c.time * 1000).toDateString();
      if (day !== lastDay) { cumTPV = 0; cumVol = 0; lastDay = day; }
      const tp = (c.high + c.low + c.close) / 3;
      cumTPV += tp * c.volume;
      cumVol += c.volume;
      out.push({ time: c.time, value: cumVol > 0 ? Math.round(cumTPV / cumVol * 100) / 100 : tp });
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
        gains  = (gains  * (period - 1) + (d > 0 ?  d : 0)) / period;
        losses = (losses * (period - 1) + (d < 0 ? -d : 0)) / period;
        const rs = losses === 0 ? 100 : gains / losses;
        out.push({ time: candles[i].time, value: Math.round((100 - 100 / (1 + rs)) * 100) / 100 });
      }
    }
    return out;
  },

  macd(candles, fast = 12, slow = 26, signal = 9) {
    const kf = 2 / (fast + 1), ks = 2 / (slow + 1), ksig = 2 / (signal + 1);
    let ef = null, es = null, esig = null;
    const macdLine = [], signalLine = [], histogram = [];
    for (let i = 0; i < candles.length; i++) {
      const c = candles[i].close;
      ef = ef === null ? c : c * kf + ef * (1 - kf);
      es = es === null ? c : c * ks + es * (1 - ks);
      if (i >= slow - 1) {
        const m = Math.round((ef - es) * 10000) / 10000;
        macdLine.push({ time: candles[i].time, value: m });
        esig = esig === null ? m : m * ksig + esig * (1 - ksig);
        if (macdLine.length >= signal) {
          signalLine.push({ time: candles[i].time, value: Math.round(esig * 10000) / 10000 });
          histogram.push({ time: candles[i].time, value: Math.round((m - esig) * 10000) / 10000, color: m >= esig ? '#26a69a88' : '#ef535088' });
        }
      }
    }
    return { macd: macdLine, signal: signalLine, histogram };
  },

  bbands(candles, period = 20, mult = 2) {
    const upper = [], mid = [], lower = [];
    for (let i = period - 1; i < candles.length; i++) {
      let s = 0;
      for (let j = i - period + 1; j <= i; j++) s += candles[j].close;
      const mean = s / period;
      let sq = 0;
      for (let j = i - period + 1; j <= i; j++) sq += (candles[j].close - mean) ** 2;
      const std = Math.sqrt(sq / period);
      mid.push(  { time: candles[i].time, value: Math.round(mean * 100) / 100 });
      upper.push({ time: candles[i].time, value: Math.round((mean + mult * std) * 100) / 100 });
      lower.push({ time: candles[i].time, value: Math.round((mean - mult * std) * 100) / 100 });
    }
    return { upper, mid, lower };
  },

  atr(candles, period = 14) {
    const out = [], trs = [];
    for (let i = 1; i < candles.length; i++) {
      const h = candles[i].high, l = candles[i].low, pc = candles[i - 1].close;
      trs.push(Math.max(h - l, Math.abs(h - pc), Math.abs(l - pc)));
      if (trs.length >= period) {
        const avg = trs.slice(-period).reduce((a, b) => a + b, 0) / period;
        out.push({ time: candles[i].time, value: Math.round(avg * 100) / 100 });
      }
    }
    return out;
  },
};
