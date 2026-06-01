# Chart Designer - Tick Engine Preview: Timeframe Aggregation Bug

## Context

PatternFoundry's Chart Designer (`/chartdesigner`) has two modes:
1. **Generate** - produces historical 1-min candles via the v2 pipeline, displays them on a LightweightCharts candlestick chart
2. **Tick Engine Preview (TEP)** - plays back second-by-second ticks from the microstructure engine, building candles live on the same chart

The user can switch timeframes (1m, 5m, 15m, 1H, 4H, 1D, 1W, 1M) at any time, including during TEP playback.

## The Bug

When the user plays the TEP on a 1m chart, then switches to a higher timeframe (e.g. 15m), the tick candles do NOT aggregate correctly into the expected bucket. For example:
- 3 ticks at 10:00, 10:01, 10:02 should become ONE 10:00 bar on the 15m chart
- Instead, they appear as separate bars at 10:15, 10:30, 10:45 (wrong boundaries)

Additionally, on very high TFs (4H, 1D, 1W), candles disappear entirely.

## Root Cause

There are **two incompatible bucketing approaches** in use:

### 1. Historical data: Factor-based bucketing (`rebucket()`)

```javascript
function rebucket(candles, tf) {
  if (tf <= 60) return candles;
  const factor = {300:5, 900:15, 3600:60, 14400:240, 86400:1250, 604800:6250, 2592000:26250}[tf];
  for (let i = 0; i < candles.length; i += factor) {
    const chunk = candles.slice(i, i + factor);
    // first chunk bar's timestamp becomes the bucket timestamp
  }
}
```

This works because historical candles are sequential 1-min bars - every 5 bars = one 5m bar, etc. The timestamp of the first bar in each chunk becomes the bucket's timestamp.

### 2. Tick data: Timestamp-based bucketing

```javascript
const ct = Math.floor(t.time / tf) * tf;
```

This divides the tick's Unix timestamp by the TF and floors it. This produces different bucket boundaries than the factor approach because:
- Historical timestamps come from `apply_session_structure()` which includes overnight/weekend gaps
- They are NOT evenly spaced at exactly 60 seconds
- `Math.floor(timestamp / 900) * 900` produces bucket boundaries based on Unix epoch alignment, not based on the candle sequence

### 3. The mixing problem

When `renderCandles()` is called on TF change:
- Historical candles are rebucketed with the factor approach → produces timestamps like `T0, T0+300, T0+600...`
- Tick candles are rebucketed with timestamp division → produces timestamps like `floor(T/900)*900`
- These two sets of timestamps don't align
- LWC requires strictly increasing timestamps
- Result: bars appear at wrong times, or LWC throws "Cannot update oldest data" errors

## What LightweightCharts Requires

- `setData([...])` - array of bars with strictly increasing `.time` values
- `update({time, open, high, low, close})` - time must be >= the last bar's time
- `timeToCoordinate(time)` - only works for timestamps that exist in the series data
- No built-in aggregation - the client must pre-aggregate before setting data

## What Needs to Happen

A single, consistent bucketing approach must be used for BOTH historical and tick data. Options:

### Option A: All timestamp-based
- Store all candles (historical + tick) with their real Unix timestamps
- Always bucket using `Math.floor(time / tf) * tf`
- Problem: historical timestamps have gaps (overnight), so at 1D TF, `Math.floor(time / 86400) * 86400` may put multiple sessions into one bucket or split one session across two buckets depending on timezone alignment

### Option B: All factor-based
- Store everything as sequential 1-min bars
- Tick candles get appended as 1-min bars (bucket ticks at 60s intervals first)
- Higher TFs always use factor chunking
- Problem: tick timestamps must align with the historical sequence. If historical ends at bar N, tick bars must be N+1, N+2, etc. with timestamps that continue the sequence.

### Option C: Separate series
- Historical data on one candlestick series
- Tick preview on a separate candlestick series overlaid
- Each manages its own timestamps independently
- TF change rebuckets each independently
- Problem: LWC doesn't natively support two candlestick series on the same price scale cleanly

## Current File Locations

- `templates/chartdesigner.html` - all frontend JS (rebucket, renderCandles, tick playback loop, onTfChange)
- `tick_engine.py` - generates tick objects `{time, price, volume, bid, ask, imbalance, hawkes, inst_remaining, inst_dir}`
- `app.py` - `/api/character/tick-preview` endpoint generates ticks and returns them

## Current State of the Code

- `allCandles` - array of 1-min candle objects from Generate (historical)
- `_playedTicks` - array of raw tick objects played so far
- `_tickPreviewCandle` - the in-progress candle being built from ticks
- `window._chartData` - the array currently set on `candleSeries`
- `rebucket(candles, tf)` - factor-based aggregation function
- `renderCandles()` - rebuckets historical + tick data and calls `candleSeries.setData()`
- `onTfChange()` - calls `renderCandles()`
- Tick playback loop - uses `Math.floor(t.time / tf) * tf` for bucketing, calls `candleSeries.update()`

## Constraints

- Historical chart data must NOT be cleared when TEP starts
- TEP candles must appear after the historical data on the chart
- Switching TF must show all data (historical + played ticks) correctly aggregated
- The chart's X-axis time labels must show sensible times (not offset garbage)
- Price must be continuous (no 800-tick gaps between historical close and first tick)
