"""Legacy per-candle generator + tick path decomposition. Used by the live simulator."""
from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd
from datetime import timedelta

try:
    import cupy as cp
    cp.cuda.Device(0).use()
    _GPU = True
except Exception:
    _GPU = False


def _xp():
    return cp if _GPU else np

def _to_numpy(arr):
    return cp.asnumpy(arr) if _GPU and isinstance(arr, cp.ndarray) else np.asarray(arr)


@dataclass
class InstrumentProfile:
    price_range:     tuple
    tick:            float
    vol_chop:        float
    vol_trend:       float
    trend_duration:  int
    drift_bias:      float
    wick_ratio_chop: float
    gap_prob:        float
    volume_base:     int
    name:            str

INSTRUMENT_PROFILES = {
    'ES':   InstrumentProfile((5000, 7000),   0.25, 1.0, 2.5, 20, 0.02,  2.0, 0.00, 1000, 'ES (calm futures)'),
    'NQ':   InstrumentProfile((18000, 22000), 0.25, 2.5, 6.0, 15, 0.03,  1.8, 0.00, 800,  'NQ (active)'),
    'SPY':  InstrumentProfile((520, 580),     0.01, 0.3, 0.8, 25, 0.015, 2.2, 0.00, 5000, 'SPY (quiet)'),
    'TSLA': InstrumentProfile((200, 280),     0.01, 1.2, 2.5, 10, 0.00,  2.5, 0.35, 3000, 'TSLA (gappy)'),
    'GME':  InstrumentProfile((18, 35),       0.01, 0.8, 1.8, 10, 0.00,  2.8, 0.35, 2500, 'GME (high-beta retail)'),
    'CL':   InstrumentProfile((70, 90),       0.01, 0.8, 1.5, 12, 0.00,  1.5, 0.02, 600,  'CL (choppy)'),
    'GC':   InstrumentProfile((1900, 2400),   0.10, 1.5, 3.0, 18, 0.005, 1.7, 0.01, 400,  'GC (Gold Futures)'),
}

DEFAULT_PROFILE    = INSTRUMENT_PROFILES['ES']
NUM_SESSION_CANDLES = 390
TICK_SIZE           = 0.25
TRAP_CANDLE_CHANCE  = 0.04


def generate_historical_data(n_candles: int = 50000, profile=None, seed: Optional[int] = None):
    """Delegates to v2 generator, falls back to legacy vectorized path."""
    try:
        from generators import generate_historical_data as _v2
        yield from _v2(n_candles, profile=profile, seed=seed)
        return
    except Exception:
        pass

    # Legacy fallback
    if profile is None: profile = DEFAULT_PROFILE
    xp = _xp()
    if seed is not None:
        np.random.seed(int(seed))
        if _GPU: cp.random.seed(int(seed))

    idx      = xp.arange(n_candles)
    is_chop  = ((idx // profile.trend_duration) % 2 == 0)
    vol      = xp.where(is_chop, profile.vol_chop, profile.vol_trend).astype(xp.float32)
    drift    = xp.where(is_chop,
                        xp.random.normal(0.0, 0.05, n_candles).astype(xp.float32),
                        xp.random.choice(xp.array([-0.2, 0.2], dtype=xp.float32), n_candles))
    drift    = xp.where(~is_chop, drift + profile.drift_bias, drift)

    changes  = xp.random.normal(drift, vol).astype(xp.float32)
    init     = float(xp.random.uniform(*profile.price_range))
    prices   = xp.empty(n_candles + 1, dtype=xp.float32)
    prices[0] = init
    prices[1:] = init + xp.cumsum(changes)

    opens  = prices[:-1]; closes = prices[1:]
    wv     = vol * xp.where(is_chop, profile.wick_ratio_chop, 0.5)
    highs  = xp.maximum(opens, closes) + xp.abs(xp.random.normal(0, wv)).astype(xp.float32)
    lows   = xp.minimum(opens, closes) - xp.abs(xp.random.normal(0, wv)).astype(xp.float32)

    tick = profile.tick
    for arr in (opens, closes, highs, lows):
        arr[:] = xp.round(arr / tick) * tick

    pos        = (idx % NUM_SESSION_CANDLES).astype(xp.float32) / NUM_SESSION_CANDLES
    range_mult = xp.clip((highs - lows) / (profile.vol_trend * 2), 0.4, 3.0)
    tod        = xp.where(pos < 0.19, 1.5, xp.where((pos >= 0.38) & (pos < 0.58), 0.5,
                 xp.where(pos >= 0.77, 1.2, xp.ones(n_candles, dtype=xp.float32))))
    spike      = xp.where(xp.random.rand(n_candles) < 0.10,
                          xp.random.uniform(1.5, 2.5, n_candles).astype(xp.float32),
                          xp.ones(n_candles, dtype=xp.float32))
    volume     = xp.maximum(float(profile.volume_base) * tod * spike * range_mult *
                            xp.random.uniform(0.6, 1.3, n_candles).astype(xp.float32), 1.0)

    opens_np  = _to_numpy(opens);  closes_np = _to_numpy(closes)
    highs_np  = _to_numpy(highs);  lows_np   = _to_numpy(lows)
    vol_np    = _to_numpy(vol);    volume_np = _to_numpy(volume).astype(int)
    is_chop_np = _to_numpy(is_chop)

    timestamps = pd.date_range(start='2024-01-01 08:00', periods=n_candles, freq='5min')
    for start in range(0, n_candles, max(n_candles // 10, 1000)):
        yield round(start / n_candles * 100), None, None

    df = pd.DataFrame({
        'Timestamp': timestamps, 'Open': np.round(opens_np, 2), 'High': np.round(highs_np, 2),
        'Low': np.round(lows_np, 2), 'Close': np.round(closes_np, 2),
        'Volume': volume_np, 'Volatility': np.round(vol_np, 4),
        'Regime': np.where(is_chop_np, 'chop', 'trend'),
    })
    yield 100, df, timestamps[-1]


def simulate_session_candles(p_memory_prices, clamp_hi, clamp_lo, last_hist_timestamp,
                             profile: InstrumentProfile = None):
    if profile is None: profile = DEFAULT_PROFILE
    current_price = p_memory_prices[-1]
    next_day      = pd.Timestamp(last_hist_timestamp).normalize() + pd.Timedelta(days=1)
    current_time  = next_day + pd.Timedelta(hours=9, minutes=30)

    spike_state = {'active': False, 'strength': 1.0}
    fvg_zones   = []
    ohlc        = []
    timestamps  = []
    zone_counter   = 0
    current_regime = np.random.choice(['trend', 'chop'])
    regime_state   = {'target': max(5, int(np.random.geometric(1.0 / profile.trend_duration)))}
    prev_volume    = None

    for i in range(NUM_SESSION_CANDLES):
        current_regime, zone_counter = _update_regime(current_regime, zone_counter, profile, regime_state)
        drift = _compute_drift(i, current_regime, current_price, fvg_zones, profile)
        o, c  = _generate_open_close(current_price, drift, current_regime, profile)
        h, l  = _generate_wicks(o, c, current_regime, profile)
        vol, spike_state = _generate_volume(i, NUM_SESSION_CANDLES, profile.volume_base,
                                            h - l, spike_state, prev_volume)
        prev_volume = vol
        c = _clamp_price(c, clamp_lo, clamp_hi)
        h = max(o, c, h); l = min(o, c, l)
        snap = lambda p: round(p / profile.tick) * profile.tick
        o, c, h, l = snap(o), snap(c), snap(h), snap(l)
        ohlc.append([o, h, l, c, vol])
        timestamps.append(current_time)
        current_time  += timedelta(minutes=1)
        current_price  = c
        if i >= 2: _detect_fvg(ohlc[i-1], ohlc[i], i, fvg_zones)
        _mark_fvg_fills(current_price, fvg_zones)

    df = pd.DataFrame(ohlc, columns=['Open', 'High', 'Low', 'Close', 'Volume'])
    df['Timestamp'] = timestamps
    df['TimeLabel'] = [ts.strftime('%H:%M') for ts in timestamps]
    return df


def _update_regime(regime, counter, profile, state):
    counter += 1
    if counter >= state['target']:
        regime = 'chop' if regime == 'trend' else 'trend'
        counter = 0
        state['target'] = max(5, int(np.random.geometric(1.0 / profile.trend_duration)))
    return regime, counter


def _compute_drift(i, regime, price, fvg_zones, profile):
    if i < 2: return 0 if regime == 'chop' else np.random.choice([0.05, -0.05])
    if regime == 'chop': return np.random.normal(0.0, 0.05)
    d = np.random.choice([0.2, -0.2]) + profile.drift_bias
    if np.random.rand() < 0.35: d = -d * np.random.uniform(0.3, 0.8)
    # Smooth time-of-day energy curve with randomness (no fixed breakout times)
    session_pct = i / NUM_SESSION_CANDLES
    if session_pct < 0.08:
        d *= np.random.uniform(1.2, 1.6)  # opening energy
    elif session_pct > 0.85:
        d *= np.random.uniform(0.6, 1.0)  # late-day fade
    return d


def _generate_open_close(prev_close, drift, regime, profile):
    vol  = profile.vol_chop if regime == 'chop' else profile.vol_trend
    tick = profile.tick
    trap = np.random.uniform(1.5, 2.5) if np.random.rand() < TRAP_CANDLE_CHANCE else 1.0
    if np.random.rand() < 0.04: trap *= np.random.uniform(2.0, 3.0)
    snap = lambda p: round(p / tick) * tick
    o = snap(np.clip(prev_close + np.random.normal(0, vol * 0.15), prev_close - vol*2, prev_close + vol*2))
    c = snap(np.clip(o + np.random.normal(drift, vol) * trap, o - vol*3, o + vol*3))
    return o, c


def _generate_wicks(o, c, regime, profile):
    vol  = profile.vol_chop if regime == 'chop' else profile.vol_trend
    tick = profile.tick
    wr   = profile.wick_ratio_chop if regime == 'chop' else 1.0
    wv   = vol * wr
    hw   = np.random.uniform(0, wv); lw = np.random.uniform(0, wv)
    if abs(hw - lw) < 0.05:
        if np.random.rand() < 0.5: hw *= np.random.uniform(1.1, 1.5)
        else:                      lw *= np.random.uniform(1.1, 1.5)
    snap = lambda p: round(p / tick) * tick
    return snap(max(o, c) + hw), snap(min(o, c) - lw)


def _generate_volume(idx, total, base, price_range, spike_state, prev_volume):
    tf = idx / total
    if   tf < 0.10: tb = np.random.uniform(2.0, 2.5)
    elif tf < 0.30: tb = np.random.uniform(1.5, 2.5)
    elif tf < 0.60: tb = np.random.uniform(0.6, 1.0)
    elif tf < 0.85: tb = np.random.uniform(1.0, 1.4)
    else:
        taper = (tf - 0.85) / 0.15
        tb    = np.random.uniform(0.5, 0.9) * np.interp(taper, [0, 1], [1.0, 0.2])

    if spike_state['active']:
        spike_state['strength'] *= 0.85
        if spike_state['strength'] < 0.95: spike_state['active'] = False
    elif idx == 0 or np.random.rand() < (0.15 if tf < 0.3 else 0.05):
        spike_state = {'active': True, 'strength': np.random.uniform(1.5, 2.5)}

    sm  = spike_state['strength'] if spike_state['active'] else 1.0
    rm  = np.clip(price_range / 2.0, 0.4, 3.0)
    vol = base * tb * sm * rm * np.random.uniform(0.6, 1.3)
    if prev_volume and spike_state['active']: vol = 0.5 * prev_volume + 0.5 * vol
    if tf < 0.1: vol = max(vol, base * 1.5)
    return int(vol), spike_state


def _clamp_price(price, lo, hi):
    if price > hi: return hi - np.random.uniform(0.5, 1.5)
    if price < lo: return lo + np.random.uniform(0.5, 1.5)
    return price


def _detect_fvg(prev2, curr, index, zones):
    if prev2[1] < curr[2]:
        zones.append({'type': 'bullish', 'price_low': prev2[1], 'price_high': curr[2], 'active': True})
    elif curr[1] < prev2[2]:
        zones.append({'type': 'bearish', 'price_low': curr[1], 'price_high': prev2[2], 'active': True})


def _mark_fvg_fills(price, zones):
    for z in zones:
        if z['active'] and z['price_low'] <= price <= z['price_high']:
            z['active'] = False


def generate_tick_path(ohlc_df, tick_size=0.25, seconds_per_candle=60):
    """Second-by-second price path from OHLC candles. Returns [{time, price, volume}]."""
    ticks = []
    for _, row in ohlc_df.iterrows():
        o, h, l, c = row['Open'], row['High'], row['Low'], row['Close']
        vol     = int(row['Volume'])
        base_ts = int(row['Timestamp'].timestamp())
        n       = seconds_per_candle
        bullish = c >= o

        if bullish:
            low_at  = np.random.uniform(0.05, 0.45)
            high_at = np.random.uniform(max(low_at + 0.1, 0.4), 0.9)
            waypoints = [(0.0, o), (low_at, l), (high_at, h), (1.0, c)]
        else:
            high_at = np.random.uniform(0.05, 0.45)
            low_at  = np.random.uniform(max(high_at + 0.1, 0.4), 0.9)
            waypoints = [(0.0, o), (high_at, h), (low_at, l), (1.0, c)]

        prices = np.empty(n)
        for si in range(len(waypoints) - 1):
            t0, p0 = waypoints[si]; t1, p1 = waypoints[si + 1]
            i0 = int(t0 * n)
            i1 = int(t1 * n) if si < len(waypoints) - 2 else n
            seg = i1 - i0
            if seg <= 0: continue
            linear      = np.linspace(p0, p1, seg)
            noise_scale = (h - l) * 0.08
            noise       = np.cumsum(np.random.normal(0, noise_scale, seg))
            fade        = np.sin(np.linspace(0, np.pi, seg))
            prices[i0:i1] = np.clip(linear + noise * fade, l, h)

        prices[0] = o; prices[-1] = c
        prices    = np.round(prices / tick_size) * tick_size

        vol_w = np.ones(n); vol_w[:n//10] = 2.0; vol_w[-n//10:] = 1.5
        vols  = np.maximum((vol_w / vol_w.sum() * vol).astype(int), 1)

        for j in range(n):
            ticks.append({'time': base_ts + j, 'price': round(float(prices[j]), 2), 'volume': int(vols[j])})

    return ticks
