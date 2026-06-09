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

// ── Incremental: compute only the last point for each indicator ──────────
// These return {time, value} or null (or structured object for multi-series)
// State-cached versions store running accumulators on the `ind` object for O(1) updates.

Indicators.lastSma = function(candles, period) {
  const n = candles.length;
  if (n < period) return null;
  let s = 0;
  for (let j = n - period; j < n; j++) s += candles[j].close;
  return { time: candles[n-1].time, value: Math.round(s / period * 100) / 100 };
};

Indicators.lastEma = function(candles, period) {
  const n = candles.length;
  if (n < period) return null;
  const k = 2 / (period + 1);
  let val = 0;
  for (let j = 0; j < period; j++) val += candles[j].close;
  val /= period;
  for (let i = period; i < n; i++) val = candles[i].close * k + val * (1 - k);
  return { time: candles[n-1].time, value: Math.round(val * 100) / 100 };
};

Indicators.lastVwap = function(candles) {
  const n = candles.length;
  if (n === 0) return null;
  let cumTPV = 0, cumVol = 0, lastDay = null;
  for (const c of candles) {
    const day = new Date(c.time * 1000).toDateString();
    if (day !== lastDay) { cumTPV = 0; cumVol = 0; lastDay = day; }
    const tp = (c.high + c.low + c.close) / 3;
    cumTPV += tp * c.volume;
    cumVol += c.volume;
  }
  const last = candles[n-1];
  const tp = (last.high + last.low + last.close) / 3;
  return { time: last.time, value: cumVol > 0 ? Math.round(cumTPV / cumVol * 100) / 100 : tp };
};

Indicators.lastRsi = function(candles, period) {
  const n = candles.length;
  if (n < period + 1) return null;
  let gains = 0, losses = 0;
  for (let i = 1; i <= period; i++) {
    const d = candles[i].close - candles[i-1].close;
    if (d > 0) gains += d; else losses -= d;
  }
  gains /= period; losses /= period;
  for (let i = period + 1; i < n; i++) {
    const d = candles[i].close - candles[i-1].close;
    gains  = (gains  * (period-1) + (d > 0 ?  d : 0)) / period;
    losses = (losses * (period-1) + (d < 0 ? -d : 0)) / period;
  }
  const rs = losses === 0 ? 100 : gains / losses;
  return { time: candles[n-1].time, value: Math.round((100 - 100/(1+rs)) * 100) / 100 };
};

Indicators.lastMacd = function(candles, fast, slow, signal) {
  const n = candles.length;
  if (n < slow) return null;
  const kf = 2/(fast+1), ks = 2/(slow+1), ksig = 2/(signal+1);
  let ef = candles[0].close, es = candles[0].close, esig = null;
  let macdCount = 0, lastM = 0, lastSig = 0;
  for (let i = 1; i < n; i++) {
    const c = candles[i].close;
    ef = c * kf + ef * (1-kf);
    es = c * ks + es * (1-ks);
    if (i >= slow - 1) {
      lastM = Math.round((ef - es) * 10000) / 10000;
      macdCount++;
      esig = esig === null ? lastM : lastM * ksig + esig * (1-ksig);
      if (macdCount >= signal) lastSig = Math.round(esig * 10000) / 10000;
    }
  }
  if (macdCount < signal) return null;
  const hist = Math.round((lastM - lastSig) * 10000) / 10000;
  const t = candles[n-1].time;
  return { macd: {time:t, value:lastM}, signal: {time:t, value:lastSig}, histogram: {time:t, value:hist, color: lastM >= lastSig ? '#26a69a88' : '#ef535088'} };
};

Indicators.lastBbands = function(candles, period, mult) {
  const n = candles.length;
  if (n < period) return null;
  let s = 0;
  for (let j = n - period; j < n; j++) s += candles[j].close;
  const mean = s / period;
  let sq = 0;
  for (let j = n - period; j < n; j++) sq += (candles[j].close - mean) ** 2;
  const std = Math.sqrt(sq / period);
  const t = candles[n-1].time;
  return { upper: {time:t, value: Math.round((mean+mult*std)*100)/100}, mid: {time:t, value: Math.round(mean*100)/100}, lower: {time:t, value: Math.round((mean-mult*std)*100)/100} };
};

Indicators.lastAtr = function(candles, period) {
  const n = candles.length;
  if (n < period + 1) return null;
  const start = Math.max(1, n - period);
  let sum = 0;
  for (let i = start; i < n; i++) {
    const h = candles[i].high, l = candles[i].low, pc = candles[i-1].close;
    sum += Math.max(h-l, Math.abs(h-pc), Math.abs(l-pc));
  }
  return { time: candles[n-1].time, value: Math.round(sum / (n - start) * 100) / 100 };
};
