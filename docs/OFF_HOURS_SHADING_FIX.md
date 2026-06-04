# Off-Hours Shading Fix — Root Cause Analysis & Implementation

## Summary

There were TWO problems preventing off-hours shading from working:

1. **Backend (app.py):** The `/api/sim-session` endpoint only generated RTH candles (9:30-16:00) for history. Off-hours candles didn't exist in the data, so there was nothing to shade.
2. **Frontend (chart.html, chartdesigner.html):** The shading function used `timeToCoordinate()` which returns null for off-screen candles, breaking the rectangle painting for all but the last visible block.

---

## Problem 1: No Off-Hours Candles in History Data

### Root Cause

The `/api/sim-session` endpoint in `app.py` was:
1. Generating `num_hist_days * 78` candles (78 = RTH bars per day at 5-min)
2. Restamping them with **RTH-only timestamps** — jumping from one day's 15:55 to the previous day's close, skipping all overnight/pre-market/post-market candles
3. Only the most recent pre-market block (6:00-9:25 on session day) was generated separately

The result: history data timestamps ran from 09:30 to 15:59 each day with NO off-hours candles between days. The shading function correctly found zero off-hours bars to shade.

### The Fix

Replace the RTH-only generation + manual restamping with `apply_session_structure()` from `generators/sessions.py`. This function:
- Assigns continuous timestamps including all session periods (overnight, london, pre_market, rth, post_market)
- Properly skips weekends
- **Dampens off-hours candles** — reduces body size and volume for non-RTH bars using session-specific multipliers

#### Changes to `app.py` `/api/sim-session`:

```python
# BEFORE: RTH-only (78 bars/day)
num_5min = num_hist_days * 78
# ... manual restamping that skipped off-hours ...

# AFTER: Full session (288 bars/day = 24hrs at 5-min)
num_5min = num_hist_days * 288
historical_df = None
for _pct, df_result, _ts in dg.generate_historical_data(num_5min, profile=profile, seed=seed):
    if df_result is not None:
        historical_df = df_result

from generators import apply_session_structure, extract_gap_cfg
if hasattr(profile, 'gap'):
    gap_cfg = extract_gap_cfg(profile)
else:
    gap_cfg = {'prob': getattr(profile, 'gap_prob', 0), 'min_size': 0.002, 'max_size': 0.005}
structured = apply_session_structure(historical_df, gap_cfg, tf_seconds=300, seed=seed)

# Shift timestamps so last candle ends just before target session's pre-market
premarket_open = pd.Timestamp(f'{target} 06:00:00', tz='UTC')
last_time = structured[-1]['time']
target_last = int(premarket_open.timestamp()) - 300  # 5 min before premarket
time_offset = target_last - last_time
for c in structured:
    c['time'] += time_offset

# Use structured candles directly as history
hist_1min = structured
```

Key points:
- `tf_seconds=300` tells the session structure to use 5-min bar spacing
- The time offset shifts all timestamps so the last history bar is just before the current session's pre-market open
- `structured` is a list of dicts: `{time, open, high, low, close, volume, session}`
- Off-hours candles have dampened bodies/volume via `oh_vol_mult=0.35` and `oh_volume_mult=0.30`

#### Downstream changes:

The pre-market and RTH session generation after history now uses the structured data:
```python
memory_hi = max(c['high'] for c in structured)
memory_lo = min(c['low'] for c in structured)
last_prices = [c['close'] for c in structured[-50:]]

# ... pm_profile setup unchanged ...
pm_df = dg.simulate_session_candles(last_prices, memory_hi, memory_lo, structured[-1]['time'], profile=pm_profile)
```

The old tiered tick-path resolution (splitting older_df/recent_df and generating 1-min bars from tick paths) is removed — the 5-min structured candles serve as history directly.

---

## Problem 2: Frontend Shading Logic

### Root Cause

The original `drawOffHoursShading()` function in `chart.html` used `timeToCoordinate(timestamp)` to convert candle times to pixel x-coordinates. This LightweightCharts API method returns `null` for timestamps that don't exist in the dataset or are off-screen.

The function was tracking **pixel coordinates** (`runX0`/`runX1`) during iteration. When `timeToCoordinate` returned null for any off-hours candle, the run would get fragmented or dropped entirely.

### The Fix

Use `logicalToCoordinate(index)` instead. This converts a **data array index** (0, 1, 2...) to a pixel x-coordinate. It works reliably for any bar in the dataset regardless of scroll position or timestamp matching.

The approach:
1. Iterate all candles, classify RTH vs off-hours by UTC time
2. Collect off-hours **index ranges** (not timestamps, not coordinates)
3. Paint using `logicalToCoordinate(startIdx)` and `logicalToCoordinate(endIdx)`

#### Working implementation for `chart.html`:

```javascript
function drawOffHoursShading() {
  const cv = window._pmCanvas; if (!cv) return;
  const ctx = cv.getContext('2d');
  ctx.clearRect(0, 0, cv.width, cv.height);
  if (candleTF > 3600) return;
  const data = window._chartData;
  if (!data || !data.length) return;
  const ts = chart.timeScale();
  ctx.fillStyle = 'rgba(100, 140, 200, 0.07)';
  let runs = [];
  let runStartIdx = null;
  for (let i = 0; i < data.length; i++) {
    const d = new Date(data[i].time * 1000);
    const mins = d.getUTCHours() * 60 + d.getUTCMinutes();
    const isRTH = mins >= 570 && mins < 960;  // 9:30-16:00 UTC
    if (!isRTH && runStartIdx === null) runStartIdx = i;
    if (isRTH && runStartIdx !== null) {
      runs.push([runStartIdx, i - 1]);
      runStartIdx = null;
    }
  }
  if (runStartIdx !== null) runs.push([runStartIdx, data.length - 1]);
  for (const [a, b] of runs) {
    const x0 = ts.logicalToCoordinate(a);
    const x1 = ts.logicalToCoordinate(b);
    if (x0 == null || x1 == null) continue;
    ctx.fillRect(Math.min(x0, x1), 0, Math.abs(x1 - x0) || 1, cv.height);
  }
}
```

#### Canvas setup (in initChart or after chart creation):

```javascript
const chartEl = document.getElementById('sim-chart');
if (window._pmCanvas && window._pmCanvas.parentNode) window._pmCanvas.parentNode.removeChild(window._pmCanvas);
const pmCanvas = document.createElement('canvas');
pmCanvas.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:1';
pmCanvas.width = chartEl.clientWidth; pmCanvas.height = chartEl.clientHeight;
chartEl.appendChild(pmCanvas);
window._pmCanvas = pmCanvas;
```

#### Subscriptions:

```javascript
// Only need one subscription (not both TimeRange AND LogicalRange)
chart.timeScale().subscribeVisibleTimeRangeChange(drawOffHoursShading);
window.drawOffHoursShading = drawOffHoursShading;
new ResizeObserver(() => { pmCanvas.width = chartEl.clientWidth; pmCanvas.height = chartEl.clientHeight; drawOffHoursShading(); }).observe(chartEl);
```

#### Trigger after data loads:

```javascript
// Call after candleSeries.setData():
setTimeout(function(){ if(window.drawOffHoursShading) window.drawOffHoursShading(); }, 100);
```

---

## Chart Designer (`chartdesigner.html`)

The Chart Designer had NO off-hours shading at all. The same pattern applies — add the canvas overlay in `initChart()`, subscribe to visible range changes, and trigger after `renderCandles()`.

The Chart Designer uses `window._chartData` (rebucketed) and its TF select has `id="tf"`.

After `renderCandles()` sets the data:
```javascript
if (window.drawOffHoursShading) setTimeout(drawOffHoursShading, 50);
```

---

## Why `timeToCoordinate` Fails But `logicalToCoordinate` Works

- `timeToCoordinate(timestamp)` — Looks up the exact timestamp in the dataset. Returns null if the timestamp doesn't match a bar exactly, OR if the bar is off-screen.
- `logicalToCoordinate(index)` — Converts a logical bar index (0-based) to pixel position. Works for ANY bar in the dataset, even off-screen ones (returns negative or beyond-width coordinates which are fine for fillRect).

The key insight: **use index-based coordinate mapping, not time-based**.

---

## RTH Time Classification

```
UTC minutes 570-960 → RTH (09:30-16:00)
Everything else → off-hours (gets shaded)
```

The candle timestamps from `apply_session_structure` are in UTC. The `_session_for()` function classifies:
- 03:00-06:00 → london
- 06:00-09:30 → pre_market
- 09:30-16:00 → rth
- 16:00-18:00 → post_market
- 18:00-03:00 → overnight

---

## Reference

Working reference implementation: `H:\Projects\strat_screener\templates\simulator.html`
Session structure module: `generators/sessions.py` → `apply_session_structure()`
