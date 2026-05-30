"""generate_v2() pipeline orchestrator."""
from typing import Optional, Iterator, Tuple
import numpy as np
import pandas as pd

from .spec import CharacterSpec
from .characters import CHARACTERS, ES_CALM
from .engines import (_xp, _to_numpy, _seed_all, _GPU_AVAILABLE,
                      REGIME_IDS, REGIME_NAMES,
                      regime_engine, drift_engine, volatility_engine,
                      wick_engine, volume_engine, gap_engine, event_engine)


def generate_v2(n: int, spec: CharacterSpec = ES_CALM, seed: Optional[int] = None) -> pd.DataFrame:
    xp = _xp()
    if seed is not None:
        _seed_all(seed)

    regime_labels, session_bounds = regime_engine(spec, n, spec.volume.candles_per_session)
    drift = drift_engine(spec, regime_labels, xp)
    vol   = volatility_engine(spec, regime_labels, xp)

    innovations = xp.random.normal(0, 1, n).astype(xp.float32) * vol + drift
    gap_off     = gap_engine(spec, regime_labels, session_bounds, None, xp)
    gap_off_np  = _to_numpy(gap_off)

    # Geometric (log-return) price integration with mean-reverting tether
    initial    = float(np.random.uniform(*spec.price_range))
    innov_np   = _to_numpy(innovations)
    log_returns = np.clip(innov_np / initial, -0.05, 0.05)
    gap_log     = np.clip(gap_off_np / initial, -0.15, 0.15)
    gap_bars    = np.nonzero(np.abs(gap_log) > 0.001)[0]

    cum_log = np.zeros(n, dtype=np.float32)
    running = 0.0
    for i in range(n):
        running += log_returns[i] + gap_log[i] - 0.0005 * running
        cum_log[i] = running

    prices_np    = np.empty(n + 1, dtype=np.float32)
    prices_np[0] = initial
    prices_np[1:] = initial * np.exp(cum_log)
    prices = xp.asarray(prices_np)

    opens  = prices[:-1].copy()
    closes = prices[1:].copy()

    # Split gap bars: prior close stays pre-gap, gap bar opens post-gap
    if len(gap_bars):
        closes_np = _to_numpy(closes).copy()
        for idx in gap_bars:
            if idx == 0 or idx - 1 >= len(closes_np): continue
            closes_np[idx - 1] = closes_np[idx - 1] / float(np.exp(gap_log[idx]))
        closes = xp.asarray(closes_np)

    # Wicks proportional to current price
    upper_w, lower_w = wick_engine(spec, regime_labels, drift, vol, xp)
    price_scale = (xp.maximum(opens, closes) / initial).astype(xp.float32)
    upper_w = upper_w * price_scale
    lower_w = lower_w * price_scale
    highs = xp.maximum(opens, closes) + upper_w
    lows  = xp.minimum(opens, closes) - lower_w

    opens, highs, lows, closes = event_engine(spec, regime_labels, drift, opens, highs, lows, closes, xp)

    # Safety
    highs = xp.maximum(highs, xp.maximum(opens, closes))
    lows  = xp.minimum(lows,  xp.minimum(opens, closes))
    lows  = xp.maximum(lows,  xp.minimum(opens, closes) * 0.5)

    if len(gap_bars):
        lows_np  = _to_numpy(lows).copy()
        highs_np = _to_numpy(highs).copy()
        opens_np = _to_numpy(opens)
        for idx in gap_bars:
            if idx >= len(lows_np): continue
            if gap_log[idx] > 0:  lows_np[idx]  = float(opens_np[idx])
            elif gap_log[idx] < 0: highs_np[idx] = float(opens_np[idx])
        lows  = xp.asarray(lows_np)
        highs = xp.asarray(highs_np)

    tick = spec.tick
    opens  = xp.round(opens  / tick) * tick
    closes = xp.round(closes / tick) * tick
    highs  = xp.round(highs  / tick) * tick
    lows   = xp.round(lows   / tick) * tick

    idx_arr = xp.arange(n, dtype=xp.int32)
    volume  = volume_engine(spec, regime_labels, idx_arr, highs - lows, xp)

    opens_np  = _to_numpy(opens)
    highs_np  = _to_numpy(highs)
    lows_np   = _to_numpy(lows)
    closes_np = _to_numpy(closes)
    vol_np    = _to_numpy(vol)
    volume_np = _to_numpy(volume).astype(np.int32)
    regime_str = np.vectorize(lambda x: REGIME_NAMES.get(int(x), 'chop'))(regime_labels)

    timestamps = pd.date_range(start='2024-01-01 08:00', periods=n, freq='1min')
    return pd.DataFrame({
        'Timestamp': timestamps,
        'Open':      np.round(opens_np,  2),
        'High':      np.round(highs_np,  2),
        'Low':       np.round(lows_np,   2),
        'Close':     np.round(closes_np, 2),
        'Volume':    volume_np,
        'Volatility': np.round(vol_np, 4),
        'Regime':    regime_str,
    })


def generate_historical_data(n_candles: int, profile=None, seed: Optional[int] = None) -> Iterator[Tuple]:
    if profile is None:
        spec = ES_CALM
    elif isinstance(profile, CharacterSpec):
        spec = profile
    else:
        name = getattr(profile, 'name', '').split()[0]
        spec = CHARACTERS.get(name, ES_CALM)

    yield 10, None, None
    df = generate_v2(n_candles, spec, seed=seed)
    yield 50, None, None
    last_ts = df['Timestamp'].iloc[-1] if len(df) else pd.Timestamp('2024-01-01')
    yield 100, df, last_ts
