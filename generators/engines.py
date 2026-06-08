"""Vectorized generation engines. Pure functions, GPU-accelerated via CuPy with NumPy fallback."""
import numpy as np

try:
    import cupy as cp
    cp.cuda.Device(0).use()
    _GPU_AVAILABLE = True
except Exception:
    _GPU_AVAILABLE = False


def _xp():
    return cp if _GPU_AVAILABLE else np

def _to_numpy(arr):
    if _GPU_AVAILABLE and isinstance(arr, cp.ndarray):
        return cp.asnumpy(arr)
    return np.asarray(arr)

def _seed_all(seed):
    np.random.seed(int(seed))
    if _GPU_AVAILABLE:
        cp.random.seed(int(seed))


REGIME_IDS   = {'chop': 0, 'trend_up': 1, 'trend_down': 2, 'impulse': 3, 'gap_hold': 4}
REGIME_NAMES = {v: k for k, v in REGIME_IDS.items()}


def regime_engine(spec, n, session_len):
    """Markov chain regime walk. Returns (regime_labels[n], session_boundaries[n])."""
    rng = np.random.RandomState()
    rng.set_state(np.random.get_state())

    name_to_id = REGIME_IDS
    transitions = {}
    for state_name in list(spec.regime.states) + ['impulse', 'gap_hold']:
        sid = name_to_id.get(state_name)
        if sid is None: continue
        cands = [(nxt, p) for (cur, nxt), p in spec.regime.transition.items() if cur == state_name]
        if not cands:
            transitions[sid] = ([name_to_id['chop']], np.array([1.0]))
        else:
            nids  = [name_to_id.get(c[0], 0) for c in cands]
            probs = np.array([c[1] for c in cands], dtype=np.float64)
            transitions[sid] = (nids, probs / probs.sum())

    dur_mean = {name_to_id.get(k, 0): max(2, v) for k, v in spec.regime.mean_duration.items()}
    min_dur  = max(2, min(dur_mean.values()))
    max_trans = int(n / min_dur) + 100

    states    = np.empty(max_trans, dtype=np.int8)
    durations = np.empty(max_trans, dtype=np.int32)
    current   = name_to_id['chop']
    i = total = 0
    while total < n and i < max_trans:
        d = max(1, int(rng.geometric(1.0 / dur_mean.get(current, 15))))
        d = min(d, n - total)
        states[i] = current; durations[i] = d
        total += d
        nids, probs = transitions[current]
        current = int(rng.choice(nids, p=probs))
        i += 1

    regime_labels = np.repeat(states[:i], durations[:i])[:n]
    session_boundaries = np.zeros(n, dtype=bool)
    for s in range(session_len, n, session_len):
        session_boundaries[s] = True
    return regime_labels, session_boundaries


def drift_engine(spec, regime_labels, xp):
    n      = regime_labels.shape[0]
    regime = xp.asarray(regime_labels, dtype=xp.int32)
    d      = spec.drift

    mean_table  = xp.asarray([0.0, d.trend_magnitude, -d.trend_magnitude, 0.0, 0.0], dtype=xp.float32)
    sigma_table = xp.asarray([d.chop_sigma, d.trend_sigma, d.trend_sigma, 0.0, 0.0], dtype=xp.float32)

    noise = xp.random.normal(0, 1, n).astype(xp.float32)
    drift = mean_table[regime] + noise * sigma_table[regime]

    # 18% counter-trend flips on trend bars
    trend_mask   = (regime == REGIME_IDS['trend_up']) | (regime == REGIME_IDS['trend_down'])
    counter_mask = trend_mask & (xp.random.rand(n) < 0.18)
    flip_scale   = xp.random.uniform(0.3, 0.8, n).astype(xp.float32)
    drift        = xp.where(counter_mask, -drift * flip_scale, drift)

    # Impulse: large random-sign magnitude
    imp_mask = (regime == REGIME_IDS['impulse'])
    imp_sign = xp.where(xp.random.rand(n) < 0.5, 1.0, -1.0).astype(xp.float32)
    drift    = xp.where(imp_mask, imp_sign * d.impulse_magnitude, drift)

    return drift + d.global_bias


def volatility_engine(spec, regime_labels, xp):
    regime    = xp.asarray(regime_labels, dtype=xp.int32)
    v         = spec.volatility
    vol_table = xp.asarray([v.chop, v.trend, v.trend, v.impulse, v.gap_hold], dtype=xp.float32)
    return vol_table[regime]


def gap_engine(spec, regime_labels, session_boundaries, prices_so_far, xp):
    n       = regime_labels.shape[0]
    g       = spec.gap
    offsets = xp.zeros(n, dtype=xp.float32)
    if g.prob <= 0 and g.intraday_prob <= 0:
        return offsets

    sb        = xp.asarray(session_boundaries)
    avg_price = (spec.price_range[0] + spec.price_range[1]) / 2

    if g.prob > 0:
        gap_mask = sb & (xp.random.rand(n) < g.prob)
        sizes    = xp.random.uniform(g.min_size, g.max_size, n).astype(xp.float32)
        bias     = xp.where(xp.random.rand(n) < 0.5 + g.bias * 0.5, 1.0, -1.0).astype(xp.float32)
        offsets  = xp.where(gap_mask, sizes * bias * avg_price, offsets)

    if g.intraday_prob > 0:
        intra_mask = (~sb) & (xp.random.rand(n) < g.intraday_prob)
        sizes      = xp.random.uniform(g.min_size * 0.5, g.max_size * 0.5, n).astype(xp.float32)
        bias       = xp.where(xp.random.rand(n) < 0.5, 1.0, -1.0).astype(xp.float32)
        offsets    = xp.where(intra_mask, offsets + sizes * bias * avg_price, offsets)

    return offsets


def wick_engine(spec, regime_labels, drift, vol, xp):
    regime      = xp.asarray(regime_labels, dtype=xp.int32)
    w           = spec.wick
    ratio_table = xp.asarray([w.chop_ratio, w.trend_ratio, w.trend_ratio,
                               w.impulse_ratio, w.gap_hold_ratio], dtype=xp.float32)
    ratio = ratio_table[regime]
    base  = vol * ratio
    n     = drift.shape[0]
    upper = xp.abs(xp.random.normal(0, 1, n).astype(xp.float32)) * base
    lower = xp.abs(xp.random.normal(0, 1, n).astype(xp.float32)) * base
    if w.asymmetry > 0:
        ds    = xp.sign(drift)
        lower = xp.maximum(lower * (1 + w.asymmetry * ds), 0.01)
        upper = xp.maximum(upper * (1 - w.asymmetry * ds), 0.01)
    return upper, lower


def volume_engine(spec, regime_labels, idx, price_range, xp):
    n           = idx.shape[0]
    v           = spec.volume
    session_pos = (idx % v.candles_per_session).astype(xp.float32) / v.candles_per_session

    tod = xp.ones(n, dtype=xp.float32)
    tod = xp.where(session_pos < 0.2,  v.tod_open_mult,   tod)
    tod = xp.where((session_pos >= 0.2) & (session_pos < 0.6), v.tod_midday_mult, tod)
    tod = xp.where(session_pos >= 0.8,  v.tod_close_mult,  tod)

    spike_starts = xp.random.rand(n) < v.spike_prob
    spike_mags   = xp.random.uniform(v.spike_min, v.spike_max, n).astype(xp.float32)
    spike_mult   = xp.where(spike_starts, spike_mags, xp.ones(n, dtype=xp.float32))

    range_mult = xp.clip(price_range / (spec.volatility.trend * 2), 0.4, 3.0).astype(xp.float32)
    noise      = xp.random.uniform(0.6, 1.3, n).astype(xp.float32)

    return xp.maximum(float(v.base) * tod * spike_mult * range_mult * noise, 1.0).astype(xp.float32)


def event_engine(spec, regime_labels, drift, opens, highs, lows, closes, xp):
    e = spec.event
    if e.wick_stab_prob <= 0:
        return opens, highs, lows, closes
    n         = opens.shape[0]
    stab_mask = xp.random.rand(n) < e.wick_stab_prob
    stab_sign = xp.where(drift >= 0, -1.0, 1.0).astype(xp.float32)
    stab_size = xp.minimum(xp.abs(xp.random.normal(0, 1.0, n).astype(xp.float32)) * e.wick_stab_magnitude, 3.0)
    lo_adj    = xp.where(stab_mask & (stab_sign < 0), lows  - stab_size * (highs - lows), lows)
    hi_adj    = xp.where(stab_mask & (stab_sign > 0), highs + stab_size * (highs - lows), highs)
    return opens, hi_adj, lo_adj, closes
