"""
Procedural RTH OHLCV candle generator.
Seed-deterministic: same seed → same session.

RTH structure (1-minute bars, 9:30–16:00 ET = 390 bars):
  - Open drive    9:30–9:50  (20 bars) — high volatility, directional
  - Morning trend 9:50–11:30 (100 bars) — moderate trend
  - Lunch chop    11:30–13:30 (120 bars) — low volatility, mean-reverting
  - Afternoon     13:30–15:00 (90 bars) — moderate, slight trend
  - Power hour    15:00–16:00 (60 bars) — elevated volatility
"""

import random
import math
from datetime import datetime, timedelta, timezone


# Instrument defaults: (typical_price, tick_size, daily_range_pct)
INSTRUMENTS = {
    "ES":  (5300.0, 0.25, 0.012),
    "NQ":  (18500.0, 0.25, 0.018),
    "GC":  (2350.0, 0.10, 0.010),
    "CL":  (78.0,   0.01, 0.020),
}

# RTH session phases: (name, bar_count, volatility_multiplier, drift_bias)
PHASES = [
    ("open_drive",    20,  3.0,  None),   # bias chosen randomly
    ("morning",      100,  1.5,  None),
    ("lunch",        120,  0.5,  0.0),
    ("afternoon",     90,  1.2,  None),
    ("power_hour",    60,  2.0,  None),
]


def _round_to_tick(price: float, tick: float) -> float:
    return round(round(price / tick) * tick, 10)


def generate_session(seed: int, instrument: str = "ES", timeframe: int = 1) -> list[dict]:
    """
    Returns a list of OHLCV dicts with 'time' (Unix timestamp, ET open = UTC-4 in summer).
    timeframe: minutes per bar (1, 5, or 15).
    """
    if instrument not in INSTRUMENTS:
        raise ValueError(f"Unknown instrument: {instrument}")

    rng = random.Random(seed)
    base_price, tick, range_pct = INSTRUMENTS[instrument]

    # Starting price: ±0.5% random offset from base
    price = base_price * (1 + rng.uniform(-0.005, 0.005))

    # RTH open: 9:30 ET = 13:30 UTC (EDT, UTC-4)
    session_open = datetime(2024, 1, 2, 13, 30, 0, tzinfo=timezone.utc)

    # Per-bar volatility (1-min base)
    bar_vol = base_price * range_pct / math.sqrt(390)

    candles = []
    bar_index = 0

    for phase_name, phase_bars, vol_mult, drift in PHASES:
        # Aggregate if timeframe > 1
        agg_bars = phase_bars // timeframe

        # Choose phase drift if not fixed
        if drift is None:
            drift = rng.uniform(-0.6, 0.6)

        # Build 1-min bars then aggregate
        minute_bars = []
        p = price
        for _ in range(phase_bars):
            sigma = bar_vol * vol_mult
            move = rng.gauss(drift * sigma * 0.1, sigma)
            o = p
            c = p + move
            hi = max(o, c) + abs(rng.gauss(0, sigma * 0.4))
            lo = min(o, c) - abs(rng.gauss(0, sigma * 0.4))
            vol = int(rng.gauss(800, 200) * vol_mult)
            minute_bars.append((o, hi, lo, c, max(vol, 50)))
            p = c

        price = p

        # Aggregate into timeframe bars
        for i in range(0, len(minute_bars), timeframe):
            chunk = minute_bars[i:i + timeframe]
            if not chunk:
                continue
            o  = _round_to_tick(chunk[0][0], tick)
            hi = _round_to_tick(max(b[1] for b in chunk), tick)
            lo = _round_to_tick(min(b[2] for b in chunk), tick)
            c  = _round_to_tick(chunk[-1][3], tick)
            v  = sum(b[4] for b in chunk)
            ts = int((session_open + timedelta(minutes=bar_index * timeframe)).timestamp())
            candles.append({"time": ts, "open": o, "high": hi, "low": lo, "close": c, "volume": v})
            bar_index += 1

    return candles
