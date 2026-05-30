import random
import copy
import os
import json
import pandas as pd
from datetime import date, datetime
from flask import Flask, render_template, jsonify, request

import data_generator as dg
from generators import (CHARACTERS, CharacterSpec, RegimeSpec, DriftSpec,
                        VolatilitySpec, WickSpec, VolumeSpec, GapSpec, EventSpec,
                        generate_v2, apply_session_structure,
                        extract_gap_cfg, disable_internal_gaps)

app = Flask(__name__)

_SESSIONS_DIR = os.path.join(os.path.dirname(__file__), 'sessions')
os.makedirs(_SESSIONS_DIR, exist_ok=True)


def _resolve_spec(instrument: str):
    """Return CharacterSpec or InstrumentProfile for the given instrument key."""
    if instrument in CHARACTERS:
        return CHARACTERS[instrument]
    custom = os.path.join('library', 'characters', f'{instrument}.json')
    if os.path.isfile(custom):
        with open(custom, encoding='utf-8') as f:
            sj = json.load(f)
        def mk(cls, d):
            if not d: return cls()
            return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        return CharacterSpec(
            name=sj.get('name', instrument),
            price_range=tuple(sj.get('price_range', [5000, 7000])),
            tick=float(sj.get('tick', 0.25)),
            regime=mk(RegimeSpec, sj.get('regime')),
            drift=mk(DriftSpec, sj.get('drift')),
            volatility=mk(VolatilitySpec, sj.get('volatility')),
            wick=mk(WickSpec, sj.get('wick')),
            volume=mk(VolumeSpec, sj.get('volume')),
            gap=mk(GapSpec, sj.get('gap')),
            event=mk(EventSpec, sj.get('event')),
        )
    return dg.INSTRUMENT_PROFILES.get(instrument, dg.DEFAULT_PROFILE)


@app.route('/')
def index():
    return render_template('simulator.html')


# ── /api/session — simple candle generation (used by chart.html) ─────────────

@app.route('/api/session')
def api_session():
    seed       = request.args.get('seed', type=int, default=random.randint(0, 2**31))
    instrument = request.args.get('instrument', default='ES').upper()
    timeframe  = request.args.get('timeframe', type=int, default=1)
    hist_days  = request.args.get('history_days', type=int, default=5)

    if timeframe not in (1, 5, 15):
        return jsonify({'error': 'timeframe must be 1, 5, or 15'}), 400

    spec = _resolve_spec(instrument)
    if not isinstance(spec, CharacterSpec):
        return jsonify({'error': f'Unknown instrument: {instrument}'}), 400

    all_candles = []
    for day_offset in range(hist_days, -1, -1):
        day_seed = (seed + day_offset * 1_000_003) & 0x7FFFFFFF
        sp = copy.deepcopy(spec)
        gap_cfg = extract_gap_cfg(sp)
        disable_internal_gaps(sp)
        df = generate_v2(390, sp, seed=day_seed)
        day_candles = apply_session_structure(df, gap_cfg, tf_seconds=60, seed=day_seed)
        time_shift = -day_offset * 86400
        for c in day_candles:
            all_candles.append({**c, 'time': c['time'] + time_shift})

    session_start_idx = hist_days * 390
    return jsonify({
        'seed': seed, 'instrument': instrument, 'timeframe': timeframe,
        'candles': all_candles, 'session_start_idx': session_start_idx,
    })


# ── /api/sim-session — full simulator session with history + ticks ────────────

@app.route('/api/sim-session')
def sim_session():
    num_hist_days = int(request.args.get('num_hist_days', 5))
    instrument    = request.args.get('instrument', 'ES')
    session_date  = request.args.get('session_date', '')
    seed_arg      = request.args.get('seed')
    seed          = int(seed_arg) if seed_arg else random.randrange(0, 1_000_000)

    profile = _resolve_spec(instrument)

    # Resolve session date
    if session_date:
        target = datetime.strptime(session_date, '%Y-%m-%d').date()
    else:
        target = date.today()
        while target.weekday() >= 5:
            target = target.replace(day=target.day + 1)

    # Generate 5-min history (78 candles/day)
    num_5min = num_hist_days * 78
    historical_df = None
    for _pct, df_result, _ts in dg.generate_historical_data(num_5min, profile=profile, seed=seed):
        if df_result is not None:
            historical_df = df_result

    # Restamp history backwards from session open
    premarket_open = pd.Timestamp(f'{target} 06:00:00', tz='UTC')
    session_open   = pd.Timestamp(f'{target} 09:30:00', tz='UTC')
    total = len(historical_df)
    new_ts = []
    ts = premarket_open - pd.Timedelta(minutes=5)
    for _ in range(total - 1, -1, -1):
        new_ts.append(ts)
        ts -= pd.Timedelta(minutes=5)
        if ts.hour < 6:
            prev = ts.normalize() - pd.Timedelta(days=1)
            while prev.weekday() >= 5:
                prev -= pd.Timedelta(days=1)
            ts = prev + pd.Timedelta(hours=15, minutes=55)
    new_ts.reverse()
    historical_df = historical_df.copy()
    historical_df['Timestamp'] = new_ts

    # Tiered resolution: older as 5-min, recent 2 weeks via tick paths → 1-min
    TICK_LIMIT = 780
    older_df  = historical_df.iloc[:-TICK_LIMIT] if len(historical_df) > TICK_LIMIT else None
    recent_df = historical_df.iloc[-TICK_LIMIT:] if len(historical_df) > TICK_LIMIT else historical_df

    hist_1min = []
    if older_df is not None:
        for _, row in older_df.iterrows():
            hist_1min.append({
                'time': int(row['Timestamp'].timestamp()),
                'open': round(float(row['Open']), 2), 'high': round(float(row['High']), 2),
                'low': round(float(row['Low']), 2),   'close': round(float(row['Close']), 2),
                'volume': int(row['Volume']),
            })

    # Aggregate tick path of recent 5-min candles into 1-min bars
    hist_ticks = dg.generate_tick_path(recent_df, tick_size=profile.tick, seconds_per_candle=300)
    bucket = None
    for t in hist_ticks:
        ct = (t['time'] // 60) * 60
        if not bucket or bucket['time'] != ct:
            if bucket: hist_1min.append(bucket)
            bucket = {'time': ct, 'open': t['price'], 'high': t['price'],
                      'low': t['price'], 'close': t['price'], 'volume': t['volume']}
        else:
            bucket['close'] = t['price']
            bucket['high']  = max(bucket['high'], t['price'])
            bucket['low']   = min(bucket['low'],  t['price'])
            bucket['volume'] += t['volume']
    if bucket: hist_1min.append(bucket)

    # Pre-market session (6:00–9:25, dampened vol)
    memory_hi = historical_df['High'].max()
    memory_lo = historical_df['Low'].min()
    last_ts   = historical_df['Timestamp'].iloc[-1]

    pm_profile = dg.InstrumentProfile(
        price_range=profile.price_range, tick=profile.tick,
        vol_chop=profile.vol_chop * 0.4, vol_trend=profile.vol_trend * 0.4,
        trend_duration=profile.trend_duration, drift_bias=profile.drift_bias * 0.3,
        wick_ratio_chop=profile.wick_ratio_chop, gap_prob=profile.gap_prob,
        volume_base=int(profile.volume_base * 0.25), name=profile.name + ' PM',
    )
    dg.NUM_SESSION_CANDLES = 210
    pm_df = dg.simulate_session_candles(historical_df['Close'].tolist(), memory_hi, memory_lo, last_ts, profile=pm_profile)
    dg.NUM_SESSION_CANDLES = 390

    pm_df = pm_df.copy()
    pm_df['Timestamp'] = pd.date_range(start=premarket_open, periods=len(pm_df), freq='1min')

    # RTH session (9:30–16:00)
    session_df = dg.simulate_session_candles(pm_df['Close'].tolist(), memory_hi, memory_lo,
                                             pm_df['Timestamp'].iloc[-1], profile=profile)
    session_df = session_df.copy()
    session_df['Timestamp'] = pd.date_range(start=session_open, periods=len(session_df), freq='1min')

    # Pre-market → history (static), RTH → ticks (playback)
    for _, row in pm_df.iterrows():
        hist_1min.append({
            'time': int(row['Timestamp'].timestamp()),
            'open': round(float(row['Open']), 2), 'high': round(float(row['High']), 2),
            'low': round(float(row['Low']), 2),   'close': round(float(row['Close']), 2),
            'volume': int(row['Volume']),
        })

    ticks = dg.generate_tick_path(session_df, tick_size=profile.tick, seconds_per_candle=60)

    return jsonify({
        'history':      hist_1min,
        'ticks':        ticks,
        'instrument':   instrument,
        'tick_size':    profile.tick,
        'tick_value':   1.25 if instrument in ('ES', 'NQ') else 0.01,
        'session_date': str(target),
        'seed':         seed,
    })


# ── Session persistence ───────────────────────────────────────────────────────

@app.route('/api/sim-export', methods=['POST'])
def sim_export():
    data     = request.get_json()
    name     = data.get('name', 'session')
    filename = ''.join(c if c.isalnum() or c in '-_ ' else '_' for c in name).strip() + '.json'
    path     = os.path.join(_SESSIONS_DIR, filename)
    with open(path, 'w') as f:
        json.dump(data, f)
    return jsonify({'status': 'ok', 'filename': filename})


@app.route('/api/sim-sessions')
def sim_sessions_list():
    sessions = []
    for fn in sorted(os.listdir(_SESSIONS_DIR)):
        if not fn.endswith('.json'): continue
        try:
            with open(os.path.join(_SESSIONS_DIR, fn)) as f:
                d = json.load(f)
            pnl    = d.get('account', {}).get('sessionPnl', 0)
            trades = len(d.get('account', {}).get('trades', []))
            size   = round(os.path.getsize(os.path.join(_SESSIONS_DIR, fn)) / 1_000_000, 2)
            sessions.append({'filename': fn, 'name': d.get('name', fn), 'instrument': d.get('instrument', ''),
                             'pnl': pnl, 'trades': trades, 'size_mb': size})
        except Exception:
            pass
    return jsonify(sessions)


@app.route('/api/sim-session-load/<filename>')
def sim_session_load(filename):
    path = os.path.join(_SESSIONS_DIR, filename)
    if not os.path.isfile(path):
        return jsonify({'error': 'not found'}), 404
    with open(path) as f:
        return jsonify(json.load(f))


@app.route('/api/sim-session-delete/<filename>', methods=['DELETE'])
def sim_session_delete(filename):
    path = os.path.join(_SESSIONS_DIR, filename)
    if os.path.isfile(path):
        os.remove(path)
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(debug=True)
