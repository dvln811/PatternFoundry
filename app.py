import random
import copy
import os
import json
import secrets
import pandas as pd
from datetime import date, datetime
from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

import data_generator as dg
from generators import (CHARACTERS, CharacterSpec, RegimeSpec, DriftSpec,
                        VolatilitySpec, WickSpec, VolumeSpec, GapSpec, EventSpec,
                        generate_v2, apply_session_structure,
                        extract_gap_cfg, disable_internal_gaps)
from models import User, init_db

app = Flask(__name__)
app.secret_key = os.environ.get('PF_SECRET', secrets.token_hex(32))
app.permanent_session_lifetime = __import__('datetime').timedelta(days=30)

# Flask-Login setup
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(int(user_id))

# Local dev: auto-login as admin (skip auth)
_IS_LOCAL = os.environ.get('PF_LOCAL', '1') == '1'

@app.before_request
def check_auth():
    # Public paths
    public = ['/login', '/register', '/static', '/api/']
    path = request.path
    if any(path.startswith(p) for p in public):
        return
    if _IS_LOCAL:
        return  # skip auth in local dev
    if not current_user.is_authenticated:
        if path != '/':
            return redirect(url_for('login'))

@app.context_processor
def inject_user():
    if _IS_LOCAL:
        return {'user': 'dev@local', 'is_admin': True, 'user_name': 'Developer', 'initials': 'DV'}
    if current_user.is_authenticated:
        initials = ''.join(w[0].upper() for w in current_user.name.split()[:2]) if current_user.name else 'U'
        return {'user': current_user.email, 'is_admin': current_user.is_admin, 'user_name': current_user.name, 'initials': initials}
    return {'user': None, 'is_admin': False, 'user_name': '', 'initials': ''}


# ── Auth routes ───────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        user = User.verify_password(email, password)
        if user:
            login_user(user, remember=True)
            User.record_login(user.id, request.remote_addr)
            session.permanent = True
            return redirect(url_for('dashboard'))
        return render_template('auth_login.html', error='Invalid email or password', email=email)
    return render_template('auth_login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        if len(password) < 8:
            return render_template('auth_register.html', error='Password must be at least 8 characters', name=name, email=email)
        user = User.create(email, password, name)
        if not user:
            return render_template('auth_register.html', error='Email already registered', name=name, email=email)
        login_user(user, remember=True)
        session.permanent = True
        return redirect(url_for('dashboard'))
    return render_template('auth_register.html')

@app.route('/logout')
def logout():
    logout_user()
    session.clear()
    resp = redirect('/')
    resp.delete_cookie('remember_token')
    resp.delete_cookie('session')
    return resp

@app.route('/admin')
def admin_hub():
    if not _IS_LOCAL and (not current_user.is_authenticated or not current_user.is_admin):
        return redirect('/')
    return render_template('admin_hub.html')

@app.route('/admin/users')
def admin_users():
    if not _IS_LOCAL and (not current_user.is_authenticated or not current_user.is_admin):
        return redirect('/')
    users = User.get_all()
    return render_template('admin_users.html', users=users, current_user_id=current_user.id if current_user.is_authenticated else 0)

@app.route('/admin/users/action', methods=['POST'])
def admin_users_action():
    if not _IS_LOCAL and (not current_user.is_authenticated or not current_user.is_admin):
        return redirect('/')
    uid = int(request.form.get('user_id', 0))
    action = request.form.get('action', '')
    if action == 'ban': User.set_banned(uid, True)
    elif action == 'unban': User.set_banned(uid, False)
    elif action == 'promote': User.set_role(uid, 'admin')
    elif action == 'demote': User.set_role(uid, 'user')
    return redirect(url_for('admin_users'))

@app.route('/admin/feedback')
def admin_feedback():
    if not _IS_LOCAL and (not current_user.is_authenticated or not current_user.is_admin):
        return redirect('/')
    fb_dir = os.path.join(os.path.dirname(__file__), 'data', 'feedback')
    items = []
    if os.path.isdir(fb_dir):
        for fn in sorted(os.listdir(fb_dir), reverse=True):
            if not fn.endswith('.json'): continue
            with open(os.path.join(fb_dir, fn)) as f:
                fb = json.load(f)
            from datetime import datetime
            fb['file'] = fn
            fb['time_str'] = datetime.fromtimestamp(fb.get('time', 0)).strftime('%Y-%m-%d %H:%M')
            items.append(fb)
    return render_template('admin_feedback.html', items=items)

@app.route('/admin/feedback/delete', methods=['POST'])
def admin_feedback_delete():
    if not _IS_LOCAL and (not current_user.is_authenticated or not current_user.is_admin):
        return redirect('/')
    fn = request.form.get('file', '')
    fb_dir = os.path.join(os.path.dirname(__file__), 'data', 'feedback')
    path = os.path.join(fb_dir, fn)
    if os.path.isfile(path): os.remove(path)
    return redirect('/admin/feedback')


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.route('/')
def dashboard():
    if not _IS_LOCAL and not current_user.is_authenticated:
        return render_template('landing.html')
    return render_template('dashboard.html')

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


@app.route('/simulator')
def simulator():
    return render_template('chart.html')

@app.route('/landing')
def landing_preview():
    return render_template('landing.html')

@app.route('/docs')
def docs():
    return render_template('docs.html')

@app.route('/docs/getting-started')
def docs_getting_started():
    return render_template('docs_getting_started.html')

@app.route('/docs/simulator')
def docs_simulator():
    return render_template('docs_simulator.html')

@app.route('/docs/designer')
def docs_designer():
    return render_template('docs_designer.html')

@app.route('/docs/indicators')
def docs_indicators():
    return render_template('docs_indicators.html')

@app.route('/docs/orderbook')
def docs_orderbook():
    return render_template('docs_orderbook.html')

@app.route('/docs/pricing')
def docs_pricing():
    return render_template('docs_pricing.html')

_BOARD_DIR = '/data/boards' if not _IS_LOCAL else os.path.join(os.path.dirname(__file__), 'Export', 'ProjectBoard')
os.makedirs(_BOARD_DIR, exist_ok=True)

@app.route('/board')
def board():
    if not _IS_LOCAL and (not current_user.is_authenticated or not current_user.is_admin):
        return redirect('/')
    return render_template('board.html', board_api_key=os.environ.get('BOARD_API_KEY', ''))

@app.route('/api/board/save', methods=['POST', 'OPTIONS'])
def board_save():
    if request.method == 'OPTIONS':
        return '', 204
    api_key = request.headers.get('X-Board-Key', '')
    valid_key = os.environ.get('BOARD_API_KEY', '')
    has_key = valid_key and api_key == valid_key
    if not has_key and not _IS_LOCAL:
        return jsonify({'error': 'unauthorized'}), 403
    data = request.get_json()
    path = os.path.join(_BOARD_DIR, 'pf_board.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    return jsonify({'saved': True})

@app.route('/api/board/load')
def board_load():
    api_key = request.headers.get('X-Board-Key', '')
    valid_key = os.environ.get('BOARD_API_KEY', '')
    has_key = valid_key and api_key == valid_key
    if not has_key and not _IS_LOCAL:
        return jsonify({'error': 'unauthorized'}), 403
    path = os.path.join(_BOARD_DIR, 'pf_board.json')
    if os.path.isfile(path):
        with open(path, encoding='utf-8') as f:
            return jsonify(json.load(f))
    return jsonify({}), 404

@app.route('/marketing')
def marketing():
    if not _IS_LOCAL and (not current_user.is_authenticated or not current_user.is_admin):
        return redirect('/')
    return render_template('marketing.html')


def _build_spec_from_payload(data):
    return CharacterSpec(
        name=data.get('name', 'Custom'),
        price_range=(float(data.get('p_lo', 5000)), float(data.get('p_hi', 7000))),
        tick=float(data.get('p_tick', 0.25)),
        regime=RegimeSpec(mean_duration={
            'chop': int(data.get('reg_chop', 25)), 'trend_up': int(data.get('reg_trendup', 20)),
            'trend_down': int(data.get('reg_trenddn', 20)), 'impulse': int(data.get('reg_impulse', 3)), 'gap_hold': 1,
        }),
        drift=DriftSpec(
            chop_sigma=float(data.get('drift_chop_sigma', 0.05)),
            trend_sigma=float(data.get('drift_trend_sigma', 0.15)),
            trend_magnitude=float(data.get('drift_trend_mag', 0.3)),
            impulse_magnitude=float(data.get('drift_impulse_mag', 1.5)),
            global_bias=float(data.get('drift_global_bias', 0.0)),
        ),
        volatility=VolatilitySpec(
            chop=float(data.get('vol_chop', 1.0)), trend=float(data.get('vol_trend', 2.0)),
            impulse=float(data.get('vol_impulse', 4.0)), gap_hold=float(data.get('vol_gaphold', 1.5)),
        ),
        wick=WickSpec(
            chop_ratio=float(data.get('wick_chop', 2.0)), trend_ratio=float(data.get('wick_trend', 0.6)),
            impulse_ratio=float(data.get('wick_impulse', 0.4)), gap_hold_ratio=float(data.get('wick_gaphold', 0.3)),
            asymmetry=float(data.get('wick_asym', 0.3)),
        ),
        volume=VolumeSpec(
            base=int(data.get('vol_base', 1000)), tod_open_mult=float(data.get('vol_open', 2.2)),
            tod_midday_mult=float(data.get('vol_midday', 0.8)), tod_close_mult=float(data.get('vol_close', 1.3)),
            spike_prob=float(data.get('vol_spike_p', 0.1)),
        ),
        gap=GapSpec(
            prob=float(data.get('gap_prob', 0.0)), min_size=float(data.get('gap_min', 0.005)),
            max_size=float(data.get('gap_max', 0.02)), intraday_prob=float(data.get('gap_intra', 0.0)),
        ),
        event=EventSpec(
            wick_stab_prob=float(data.get('ev_stab_prob', 0.02)),
            wick_stab_magnitude=float(data.get('ev_stab_mag', 3.0)),
        ),
    )


@app.route('/chartdesigner')
def chartdesigner():
    return render_template('chartdesigner.html')


@app.route('/api/character/generate', methods=['POST'])
def character_generate():
    import copy
    data = request.get_json()
    seed_arg = data.get('seed')
    seed     = int(seed_arg) if seed_arg else random.randrange(0, 1_000_000)
    n        = int(data.get('n', 1950))

    spec = _build_spec_from_payload(data)

    gap_cfg = extract_gap_cfg(spec)
    disable_internal_gaps(spec)
    df      = generate_v2(n, spec, seed=seed)
    candles = apply_session_structure(df, gap_cfg, tf_seconds=60, seed=seed)

    # Regime stats
    regime_counts = df['Regime'].value_counts().to_dict()
    total = len(df)
    regime_stats = {k: {'count': int(v), 'pct': round(v / total * 100, 1)} for k, v in regime_counts.items()}
    avg_body = float((df['Close'] - df['Open']).abs().mean())
    avg_range = float((df['High'] - df['Low']).mean())

    return jsonify({
        'candles': candles, 'seed': seed, 'n': len(candles),
        'stats': {
            'regimes': regime_stats,
            'avg_body': round(avg_body, 4),
            'avg_range': round(avg_range, 4),
            'total_bars': total,
        }
    })


@app.route('/api/character/save', methods=['POST'])
def character_save():
    data = request.get_json()
    name = data.get('name', 'Custom').strip()
    if not name:
        return jsonify({'error': 'Name required'}), 400
    filename = ''.join(c if c.isalnum() or c in '-_ ' else '_' for c in name).strip() + '.json'
    path = os.path.join('library', 'characters', filename)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    return jsonify({'status': 'ok', 'filename': filename, 'name': name})


@app.route('/api/character/tick-preview', methods=['POST'])
def character_tick_preview():
    """Generate a few candles + full tick objects for microstructure debugging."""
    data = request.get_json()
    seed = int(data.get('seed', 42))
    n_candles = int(data.get('n_candles', 30))  # 30 candles = 30 minutes of tick data

    spec = _build_spec_from_payload(data)
    gap_cfg = extract_gap_cfg(spec)
    disable_internal_gaps(spec)
    df = generate_v2(n_candles, spec, seed=seed)
    candles_structured = apply_session_structure(df, gap_cfg, tf_seconds=60, seed=seed)

    # Build a mini DataFrame for tick engine
    import pandas as pd
    mini_df = pd.DataFrame({
        'Timestamp': pd.to_datetime([c['time'] for c in candles_structured[:n_candles]], unit='s', utc=True),
        'Open': [c['open'] for c in candles_structured[:n_candles]],
        'High': [c['high'] for c in candles_structured[:n_candles]],
        'Low': [c['low'] for c in candles_structured[:n_candles]],
        'Close': [c['close'] for c in candles_structured[:n_candles]],
        'Volume': [c['volume'] for c in candles_structured[:n_candles]],
    })

    from tick_engine import generate_microstructure_ticks, MicroConfig
    tick_cfg = MicroConfig(
        tick_size=float(data.get('p_tick', 0.25)), seconds_per_candle=60,
        spread_base=float(data.get('mc_spread_base', 1.0)),
        spread_vol_mult=float(data.get('mc_spread_vol', 2.0)),
        inst_rate=float(data.get('mc_inst_rate', 0.02)),
        inst_size_min=int(data.get('mc_inst_size_min', 20)),
        inst_size_max=int(data.get('mc_inst_size_max', 200)),
        inst_persistence=float(data.get('mc_inst_persist', 0.92)),
        retail_rate=float(data.get('mc_retail_rate', 0.08)),
        momentum_rate=float(data.get('mc_momentum_rate', 0.04)),
        hawkes_base=float(data.get('mc_hawkes_base', 0.15)),
        hawkes_alpha=float(data.get('mc_hawkes_alpha', 0.6)),
        hawkes_beta=float(data.get('mc_hawkes_beta', 3.0)),
        pool_strength=float(data.get('mc_pool_strength', 0.3)),
        pool_count=int(data.get('mc_pool_count', 3)),
        mean_rev_strength=float(data.get('mc_mean_rev', 0.002)),
    )

    candle_dicts = [{
        'time': c['time'], 'open': c['open'], 'high': c['high'],
        'low': c['low'], 'close': c['close'], 'volume': c['volume'],
    } for c in candles_structured[:n_candles]]

    ticks = generate_microstructure_ticks(candle_dicts, tick_cfg)

    return jsonify({'ticks': ticks, 'candles': candle_dicts, 'seed': seed})


@app.route('/api/character/list')
def character_list():
    items = []
    for key, spec in CHARACTERS.items():
        items.append({'id': key, 'name': spec.name, 'kind': 'builtin'})
    chars_dir = os.path.join('library', 'characters')
    if os.path.isdir(chars_dir):
        for fn in sorted(os.listdir(chars_dir)):
            if not fn.endswith('.json'): continue
            try:
                with open(os.path.join(chars_dir, fn)) as f:
                    d = json.load(f)
                cid = fn.replace('.json', '')
                items.append({'id': cid, 'name': d.get('name', cid), 'kind': 'custom'})
            except Exception:
                pass
    return jsonify(items)


# ── /api/session - simple candle generation (used by chart.html) ─────────────

@app.route('/feedback')
def feedback_page():
    return render_template('feedback.html')

@app.route('/api/feedback', methods=['POST'])
def api_feedback():
    import smtplib
    from email.mime.text import MIMEText
    data = request.get_json()
    category = data.get('category', 'general')
    subject = data.get('subject', 'No subject')
    message = data.get('message', '')
    email = data.get('email', 'anonymous')
    # Store locally as JSON
    fb_dir = os.path.join(os.path.dirname(__file__), 'data', 'feedback')
    os.makedirs(fb_dir, exist_ok=True)
    import time
    fb_file = os.path.join(fb_dir, f'{int(time.time())}_{category}.json')
    with open(fb_file, 'w') as f:
        json.dump({'category': category, 'subject': subject, 'message': message, 'email': email, 'time': time.time()}, f)
    return jsonify({'ok': True})

@app.route('/api/upload-screenshot', methods=['POST'])
def upload_screenshot():
    if not _IS_LOCAL and (not current_user.is_authenticated or not current_user.is_admin):
        return jsonify({'error': 'unauthorized'}), 403
    file = request.files.get('file')
    slot = request.form.get('slot', 'simulator')
    if not file or slot not in ('simulator', 'designer'):
        return jsonify({'error': 'invalid'}), 400
    path = os.path.join('static', 'screenshots', f'{slot}.png')
    file.save(path)
    return jsonify({'ok': True, 'url': f'/static/screenshots/{slot}.png'})


@app.route('/api/news')
def api_news():
    import requests as req
    import xml.etree.ElementTree as ET
    try:
        resp = req.get('https://finance.yahoo.com/news/rssindex', timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        root = ET.fromstring(resp.content)
        items = []
        for item in root.findall('.//item')[:8]:
            title = item.findtext('title', '')
            link = item.findtext('link', '')
            pub = item.findtext('pubDate', '')
            items.append({'title': title, 'link': link, 'pubDate': pub})
        return jsonify(items)
    except Exception:
        return jsonify([])


# ── Yahoo Finance endpoints ────────────────────────────────────────────────────

@app.route('/api/quotes')
def api_quotes():
    import requests as req
    symbols = request.args.get('symbols', 'ES=F,NQ=F,GC=F,CL=F,SPY,QQQ').split(',')
    results = []
    for sym in symbols:
        try:
            url = f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=2d'
            resp = req.get(url, timeout=3, headers={'User-Agent': 'Mozilla/5.0'})
            if resp.status_code != 200: continue
            meta = resp.json().get('chart', {}).get('result', [{}])[0].get('meta', {})
            price = meta.get('regularMarketPrice', 0)
            prev = meta.get('chartPreviousClose', meta.get('previousClose', price))
            pct = ((price - prev) / prev * 100) if prev else 0
            results.append({'symbol': sym, 'name': meta.get('shortName', sym), 'price': price, 'changePct': round(pct, 2)})
        except Exception:
            continue
    return jsonify(results)

@app.route('/api/chart')
def api_chart():
    import requests as req
    symbol = request.args.get('symbol', 'ES=F')
    interval = request.args.get('interval', '1d')
    range_ = request.args.get('range', '6mo')
    try:
        url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={interval}&range={range_}'
        resp = req.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        result = resp.json().get('chart', {}).get('result', [{}])[0]
        timestamps = result.get('timestamp', [])
        quote = result.get('indicators', {}).get('quote', [{}])[0]
        candles = []
        for i, t in enumerate(timestamps):
            o, h, l, c = quote.get('open', [None])[i], quote.get('high', [None])[i], quote.get('low', [None])[i], quote.get('close', [None])[i]
            if o is None: continue
            v = (quote.get('volume', [0])[i] or 0)
            candles.append({'time': t, 'open': round(o, 2), 'high': round(h, 2), 'low': round(l, 2), 'close': round(c, 2), 'volume': int(v)})
        return jsonify(candles)
    except Exception:
        return jsonify([])


# ── /api/session - simple candle generation (used by chart.html) ─────────────

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


# ── /api/sim-session - full simulator session with history + ticks ────────────

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
        from datetime import timedelta
        while target.weekday() >= 5:
            target += timedelta(days=1)

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
    bars_today = 0
    for _ in range(total):
        new_ts.append(ts)
        bars_today += 1
        ts -= pd.Timedelta(minutes=5)
        # After 78 bars (one RTH session), jump to previous trading day's close
        if bars_today >= 78:
            bars_today = 0
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

    from tick_engine import generate_tick_path_v2, MicroConfig, MICRO_DEFAULTS
    # Use per-instrument micro defaults, or custom if saved
    tick_cfg = MICRO_DEFAULTS.get(instrument, MicroConfig(tick_size=profile.tick))
    # Check if custom character has micro params
    custom_path = os.path.join('library', 'characters', f'{instrument}.json')
    if os.path.isfile(custom_path):
        with open(custom_path) as f:
            cdata = json.load(f)
        if 'mc_spread_base' in cdata:
            tick_cfg = MicroConfig(
                tick_size=profile.tick, seconds_per_candle=60,
                spread_base=float(cdata.get('mc_spread_base', 1.0)),
                spread_vol_mult=float(cdata.get('mc_spread_vol', 2.0)),
                inst_rate=float(cdata.get('mc_inst_rate', 0.02)),
                inst_size_min=int(cdata.get('mc_inst_size_min', 20)),
                inst_size_max=int(cdata.get('mc_inst_size_max', 200)),
                inst_persistence=float(cdata.get('mc_inst_persist', 0.92)),
                retail_rate=float(cdata.get('mc_retail_rate', 0.08)),
                momentum_rate=float(cdata.get('mc_momentum_rate', 0.04)),
                hawkes_base=float(cdata.get('mc_hawkes_base', 0.15)),
                hawkes_alpha=float(cdata.get('mc_hawkes_alpha', 0.6)),
                hawkes_beta=float(cdata.get('mc_hawkes_beta', 3.0)),
                pool_strength=float(cdata.get('mc_pool_strength', 0.3)),
                pool_count=int(cdata.get('mc_pool_count', 3)),
                mean_rev_strength=float(cdata.get('mc_mean_rev', 0.002)),
            )
    ticks = generate_tick_path_v2(session_df, tick_size=profile.tick, seconds_per_candle=60, config=tick_cfg)

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
