# Tick Engine v2 - Market Microstructure Simulation

## Overview

`tick_engine.py` generates second-by-second price ticks from 1-minute OHLCV candles using an agent-based market microstructure model. It replaces the old waypoint interpolation (`data_generator.generate_tick_path`).

## Input / Output

**Input:** List of 1-min candle dicts `{time, open, high, low, close, volume}` (from `simulate_session_candles`)

**Output:** List of tick dicts `{time, price, volume}` - one per second (390 candles × 60 = 23,400 ticks for full RTH)

## Architecture

```
OHLCV Candles (macro structure)
       │
       ▼
┌─────────────────────────────────┐
│  Per-candle tick simulation     │
│                                 │
│  For each second within candle: │
│    1. Compute target price      │
│    2. Run agent actions          │
│    3. Form price from forces    │
│    4. Clamp to [Low, High]      │
│    5. Emit tick                  │
└─────────────────────────────────┘
       │
       ▼
  23,400 ticks with realistic microstructure
```

## Agent Types

| Agent | Rate | Behavior |
|-------|------|----------|
| **Market Maker** | 0.3/sec | Provides liquidity, adjusts spread based on local volatility |
| **Institutional** | 0.02/sec | Large persistent directional orders (20-200 lots), creates price impact, Hawkes excitation |
| **Retail** | 0.08/sec | Random noise flow, triggered more during high-activity periods |
| **Momentum** | 0.04/sec | Follows recent 5-tick direction, amplifies moves |

## Key Mechanisms

### Hawkes Self-Excitation
Trades cluster in time. Each trade event increases the intensity (probability of more trades), which decays exponentially. Creates realistic bursts of activity.

```
intensity(t) = base + (intensity - base) × e^(-beta/spc)
```

### Price Formation (per second)
Price change = sum of forces:
- **Target pull (15%)** - pulls toward the candle's expected path (ensures OHLC constraint)
- **Order flow impact** - imbalance × tick × 0.05
- **Liquidity pool attraction** - price pulled toward nearby S/R levels
- **VWAP mean-reversion** - micro pull toward session VWAP
- **Noise** - N(0, tick × 0.3)

### Liquidity Pools
3 S/R levels generated per session within the price range. Price is attracted toward these levels (simulates real order clustering). Strength configurable via `pool_strength`.

### Dynamic Spread
```
spread = tick × spread_base × (1 + spread_vol_mult × local_volatility)
```
Widens during fast moves, tightens during calm. Clamped to [1 tick, 8 ticks].

### OHLC Constraint
Each candle's ticks are constrained:
- First tick = Open
- Last tick = Close
- All ticks clamped to [Low, High]
- Waypoints guide the path: O→L→H→C (bullish) or O→H→L→C (bearish)

## Configuration (`MicroConfig`)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `tick_size` | 0.25 | Minimum price increment |
| `seconds_per_candle` | 60 | Ticks per candle |
| `lob_levels` | 10 | Depth levels each side |
| `lob_base_size` | 50 | Base lots per level |
| `mm_rate` | 0.3 | Market maker refresh rate |
| `inst_rate` | 0.02 | Institutional order rate |
| `inst_size_min/max` | 20/200 | Institutional order size range |
| `inst_persistence` | 0.92 | Prob of continuing same direction |
| `retail_rate` | 0.08 | Retail noise rate |
| `momentum_rate` | 0.04 | Momentum chaser rate |
| `hawkes_base` | 0.15 | Base intensity |
| `hawkes_alpha` | 0.6 | Excitation jump per event |
| `hawkes_beta` | 3.0 | Decay rate |
| `pool_strength` | 0.3 | S/R attraction strength |
| `pool_count` | 3 | Number of S/R levels |
| `mean_rev_strength` | 0.002 | VWAP pull strength |
| `spread_base` | 1.0 | Base spread in ticks |
| `spread_vol_mult` | 2.0 | Spread volatility multiplier |

## Usage

```python
from tick_engine import generate_tick_path_v2, MicroConfig

config = MicroConfig(tick_size=0.25, seconds_per_candle=60)
ticks = generate_tick_path_v2(session_df, config=config)
# ticks = [{time, price, volume}, ...]
```

## Wiring

In `app.py`, the `/api/sim-session` endpoint uses:
```python
from tick_engine import generate_tick_path_v2, MicroConfig
tick_cfg = MicroConfig(tick_size=profile.tick, seconds_per_candle=60)
ticks = generate_tick_path_v2(session_df, tick_size=profile.tick, config=tick_cfg)
```

The frontend receives ticks and plays them back at the selected speed (0.25x–200x).
