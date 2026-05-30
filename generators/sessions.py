"""Session structure post-processor: timestamps, off-hours dampening, RTH gaps."""
from __future__ import annotations
from typing import Dict, List, Optional
import random
import pandas as pd

SESSION_VOL_WEIGHT = {'rth': 1.0, 'pre_market': 1.15, 'post_market': 1.00, 'london': 1.55, 'overnight': 0.55}


def _session_for(dt: pd.Timestamp) -> str:
    mins = dt.hour * 60 + dt.minute
    if 360 <= mins < 570:  return 'pre_market'
    if 570 <= mins < 960:  return 'rth'
    if 960 <= mins < 1080: return 'post_market'
    if 180 <= mins < 360:  return 'london'
    return 'overnight'


def _build_session_timestamps(n: int, tf_seconds: int):
    step = pd.Timedelta(seconds=max(60, tf_seconds))
    timestamps, sessions = [], []
    t = pd.Timestamp('2024-01-01 06:00', tz='UTC')
    while len(timestamps) < n:
        if t.weekday() == 5:
            t = (t + pd.Timedelta(days=1)).normalize().tz_localize(None).tz_localize('UTC') + pd.Timedelta(hours=18)
            continue
        if t.weekday() == 6 and t.hour < 18:
            t = t.normalize().tz_localize(None).tz_localize('UTC') + pd.Timedelta(hours=18)
            continue
        timestamps.append(t)
        sessions.append(_session_for(t))
        t += step
    return timestamps, sessions


def apply_session_structure(df: pd.DataFrame, gap_cfg: Dict, *, tf_seconds: int = 60,
                            seed: Optional[int] = None, oh_vol_mult: float = 0.35,
                            oh_volume_mult: float = 0.30) -> List[Dict]:
    n = len(df)
    timestamps, sessions = _build_session_timestamps(n, tf_seconds)
    london_w = SESSION_VOL_WEIGHT['london']

    def session_mults(sess):
        if sess == 'rth': return 1.0, 1.0
        w = SESSION_VOL_WEIGHT.get(sess, 1.0) / london_w
        return oh_vol_mult * w, oh_volume_mult * w

    def _dampen_body(o, h, l, c, vm):
        new_c   = o + (c - o) * vm
        body_hi = max(o, new_c); body_lo = min(o, new_c)
        new_h   = max(body_hi + (h - max(o, c)) * vm, body_hi)
        new_l   = min(body_lo - (min(o, c) - l) * vm, body_lo)
        return new_c, new_h, new_l

    candles: List[Dict] = []
    _offset = 0.0
    for k, (_, row) in enumerate(df.iterrows()):
        sess = sessions[k]
        vm, vol_mult = session_mults(sess)
        o = float(row['Open'])  + _offset
        h = float(row['High'])  + _offset
        l = float(row['Low'])   + _offset
        c = float(row['Close']) + _offset
        if vm != 1.0:
            new_c, new_h, new_l = _dampen_body(o, h, l, c, vm)
            _offset += (new_c - c)
            c, h, l = new_c, new_h, new_l
        candles.append({
            'time': int(timestamps[k].timestamp()),
            'open': o, 'high': h, 'low': l, 'close': c,
            'volume': max(1, int(float(row['Volume']) * vol_mult)),
            'session': sess,
        })

    # RTH-open persistent multiplicative gaps
    rng      = random.Random(int(seed) if seed else 0)
    cum_mult = 1.0
    prob     = float(gap_cfg.get('prob', 0.0))
    min_size = float(gap_cfg.get('min_size', 0.0))
    max_size = float(gap_cfg.get('max_size', 0.0))

    def is_rth_open(i):
        return i > 0 and candles[i]['session'] == 'rth' and candles[i-1]['session'] != 'rth'

    for i in range(len(candles)):
        c = candles[i]
        if is_rth_open(i) and prob > 0:
            dt = pd.Timestamp(c['time'], unit='s', tz='UTC')
            weekday_mult = 1.8 if dt.weekday() == 0 else 1.0
            if rng.random() < prob * weekday_mult:
                size      = rng.uniform(min_size, max_size) if max_size > 0 else 0.0
                direction = 1 if rng.random() < 0.5 else -1
                cum_mult *= 1.0 + direction * size
                for k in ('open', 'high', 'low', 'close'):
                    c[k] *= cum_mult
                if direction > 0: c['low']  = c['open']
                else:             c['high'] = c['open']
                continue
        if cum_mult != 1.0:
            for k in ('open', 'high', 'low', 'close'):
                c[k] *= cum_mult

    for c in candles:
        c['open']  = round(c['open'],  2)
        c['high']  = round(c['high'],  2)
        c['low']   = round(c['low'],   2)
        c['close'] = round(c['close'], 2)

    return candles


def extract_gap_cfg(spec) -> Dict:
    return {'prob': float(spec.gap.prob), 'min_size': float(spec.gap.min_size),
            'max_size': float(spec.gap.max_size), 'intraday_prob': float(getattr(spec.gap, 'intraday_prob', 0.0))}


def disable_internal_gaps(spec) -> None:
    spec.gap.prob = 0.0
    spec.gap.intraday_prob = 0.0
