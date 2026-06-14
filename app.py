import random
import copy
import os
import json
import secrets
import pandas as pd
from datetime import date, datetime
from flask import Flask, render_template, jsonify, request, redirect, url_for, session, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

import data_generator as dg
from generators import (CHARACTERS, CharacterSpec, RegimeSpec, DriftSpec,
                        VolatilitySpec, WickSpec, VolumeSpec, GapSpec, EventSpec,
                        generate_v2, apply_session_structure,
                        extract_gap_cfg, disable_internal_gaps)
from models import User, init_db, _get_db, save_session, get_sessions, \
    get_active_account, create_account, update_account_balance, update_account_settings, reset_account, \
    get_archived_accounts, get_account_sessions, purge_archived_accounts, nuke_user_stats

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

@app.after_request
def _board_cors(response):
    if request.path.startswith('/api/board') or request.path.startswith('/api/marketing-board'):
        response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-Board-Key'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

@app.before_request
def check_auth():
    # Public paths
    public = ['/login', '/register', '/static', '/api/', '/robots.txt', '/sitemap.xml', '/blog', '/docs', '/free-trading-simulator']
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
    elif action == 'nuke': nuke_user_stats(uid)
    elif action == 'grant_edge': User.set_tier(uid, 'edge')
    elif action == 'mark_test': User.set_tier(uid, 'test')
    elif action == 'set_free': User.set_tier(uid, 'free')
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
            tick_value=float(sj.get('tick_value', 12.50)),
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

@app.route('/robots.txt')
def robots():
    return send_from_directory('static', 'robots.txt')


@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory('static', 'sitemap.xml')


@app.route('/docs')
def docs():
    return render_template('docs.html')

@app.route('/free-trading-simulator')
def seo_simulator():
    return render_template('seo_simulator.html')

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

@app.route('/docs/ironman')
def docs_ironman():
    return render_template('docs_ironman.html')

@app.route('/docs/stats')
def docs_stats():
    return render_template('docs_stats.html')

@app.route('/docs/presets')
def docs_presets():
    return render_template('docs_presets.html')

# ── Blog ──────────────────────────────────────────────────────────────────────
import markdown as _md

_BLOG_DIR = '/data/blog' if not _IS_LOCAL else os.path.join(os.path.dirname(__file__), 'blog')
os.makedirs(_BLOG_DIR, exist_ok=True)
# Seed from repo on first deploy
_BLOG_SEED = os.path.join(os.path.dirname(__file__), 'blog')
if _BLOG_DIR != _BLOG_SEED and os.path.isdir(_BLOG_SEED):
    for f in os.listdir(_BLOG_SEED):
        if f.endswith('.md') and not os.path.isfile(os.path.join(_BLOG_DIR, f)):
            import shutil
            shutil.copy2(os.path.join(_BLOG_SEED, f), os.path.join(_BLOG_DIR, f))

def _parse_post(filename):
    path = os.path.join(_BLOG_DIR, filename)
    with open(path) as f:
        content = f.read()
    meta = {}
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split('\n'):
                if ':' in line:
                    k, v = line.split(':', 1)
                    meta[k.strip()] = v.strip()
            content = parts[2]
    html = _md.markdown(content, extensions=['fenced_code', 'tables'])
    meta['slug'] = filename.replace('.md', '')
    meta['html'] = html
    return meta

def _get_posts():
    posts = []
    for f in sorted(os.listdir(_BLOG_DIR), reverse=True):
        if f.endswith('.md'):
            try:
                posts.append(_parse_post(f))
            except Exception:
                pass
    return posts

@app.route('/blog')
def blog_index():
    return render_template('blog_index.html', posts=_get_posts())

@app.route('/blog/images/<filename>')
def blog_image(filename):
    img_dir = '/data/blog/images' if not _IS_LOCAL else os.path.join(os.path.dirname(__file__), 'static', 'blog')
    return send_from_directory(img_dir, filename)

@app.route('/blog/<slug>')
def blog_post(slug):
    path = os.path.join(_BLOG_DIR, slug + '.md')
    if not os.path.isfile(path):
        return 'Not found', 404
    post = _parse_post(slug + '.md')
    return render_template('blog_post.html', post=post)

@app.route('/admin/blog')
def admin_blog():
    if not _IS_LOCAL and (not current_user.is_authenticated or not current_user.is_admin):
        return redirect('/')
    return render_template('admin_blog.html')

@app.route('/api/blog/posts')
def api_blog_list():
    return jsonify(_get_posts())

@app.route('/api/blog/posts/<slug>')
def api_blog_get(slug):
    path = os.path.join(_BLOG_DIR, slug + '.md')
    if not os.path.isfile(path):
        return jsonify({'error': 'not found'}), 404
    with open(path) as f:
        raw = f.read()
    post = _parse_post(slug + '.md')
    post['raw'] = raw
    return jsonify(post)

@app.route('/api/blog/posts', methods=['POST'])
def api_blog_save():
    if not _IS_LOCAL and (not current_user.is_authenticated or not current_user.is_admin):
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json()
    slug = data.get('slug', '').strip()
    content = data.get('content', '')
    if not slug:
        return jsonify({'error': 'slug required'}), 400
    slug = ''.join(c if c.isalnum() or c in '-_' else '-' for c in slug).strip('-')
    path = os.path.join(_BLOG_DIR, slug + '.md')
    with open(path, 'w') as f:
        f.write(content)
    return jsonify({'saved': True, 'slug': slug})

@app.route('/api/blog/posts/<slug>', methods=['DELETE'])
def api_blog_delete(slug):
    if not _IS_LOCAL and (not current_user.is_authenticated or not current_user.is_admin):
        return jsonify({'error': 'unauthorized'}), 401
    path = os.path.join(_BLOG_DIR, slug + '.md')
    if os.path.isfile(path):
        os.remove(path)
    return jsonify({'deleted': True})

@app.route('/api/blog/upload', methods=['POST'])
def api_blog_upload():
    if not _IS_LOCAL and (not current_user.is_authenticated or not current_user.is_admin):
        return jsonify({'error': 'unauthorized'}), 401
    f = request.files.get('file')
    if not f:
        return jsonify({'error': 'no file'}), 400
    filename = ''.join(c if c.isalnum() or c in '-_.' else '_' for c in f.filename)
    img_dir = '/data/blog/images' if not _IS_LOCAL else os.path.join(os.path.dirname(__file__), 'static', 'blog')
    os.makedirs(img_dir, exist_ok=True)
    f.save(os.path.join(img_dir, filename))
    url = '/blog/images/' + filename if not _IS_LOCAL else '/static/blog/' + filename
    return jsonify({'url': url})

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
    if not has_key and not _IS_LOCAL and not (current_user.is_authenticated and current_user.is_admin):
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
    if not has_key and not _IS_LOCAL and not (current_user.is_authenticated and current_user.is_admin):
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

@app.route('/marketing/board')
def marketing_board():
    if not _IS_LOCAL and (not current_user.is_authenticated or not current_user.is_admin):
        return redirect('/')
    return render_template('marketing_board.html', board_api_key=os.environ.get('BOARD_API_KEY', ''))

@app.route('/marketing/scripts')
def marketing_scripts():
    if not _IS_LOCAL and (not current_user.is_authenticated or not current_user.is_admin):
        return redirect('/')
    return render_template('marketing_scripts.html')

@app.route('/api/marketing-board/save', methods=['POST', 'OPTIONS'])
def marketing_board_save():
    if request.method == 'OPTIONS':
        return '', 204
    api_key = request.headers.get('X-Board-Key', '')
    valid_key = os.environ.get('BOARD_API_KEY', '')
    has_key = valid_key and api_key == valid_key
    if not has_key and not _IS_LOCAL and not (current_user.is_authenticated and current_user.is_admin):
        return jsonify({'error': 'unauthorized'}), 403
    data = request.get_json()
    path = os.path.join(_BOARD_DIR, 'pf_marketing_board.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    return jsonify({'saved': True})

@app.route('/api/marketing-board/load')
def marketing_board_load():
    api_key = request.headers.get('X-Board-Key', '')
    valid_key = os.environ.get('BOARD_API_KEY', '')
    has_key = valid_key and api_key == valid_key
    if not has_key and not _IS_LOCAL and not (current_user.is_authenticated and current_user.is_admin):
        return jsonify({'error': 'unauthorized'}), 403
    path = os.path.join(_BOARD_DIR, 'pf_marketing_board.json')
    if os.path.isfile(path):
        with open(path, encoding='utf-8') as f:
            return jsonify(json.load(f))
    return jsonify({}), 404

@app.route('/feature-ideas')
def feature_ideas():
    if not _IS_LOCAL and (not current_user.is_authenticated or not current_user.is_admin):
        return redirect('/')
    return render_template('feature_ideas.html')

@app.route('/stats')
def stats():
    return render_template('stats.html')


# ── Iron Man Mode API ─────────────────────────────────────────────────────────

def _get_user_id():
    if _IS_LOCAL:
        return 1
    return current_user.id if current_user.is_authenticated else None

@app.route('/api/ironman/status')
def ironman_status():
    uid = _get_user_id()
    if not uid:
        return jsonify({'error': 'unauthorized'}), 401
    conn = _get_db()
    run = conn.execute(
        'SELECT * FROM ironman_runs WHERE user_id=? AND status="active" ORDER BY id DESC LIMIT 1',
        (uid,)).fetchone()
    if not run:
        # Return history of past runs
        past = conn.execute(
            'SELECT * FROM ironman_runs WHERE user_id=? ORDER BY id DESC LIMIT 20', (uid,)).fetchall()
        conn.close()
        return jsonify({'active': False, 'history': [dict(r) for r in past]})
    sessions = conn.execute(
        'SELECT * FROM ironman_sessions WHERE run_id=? ORDER BY day_num', (run['id'],)).fetchall()
    conn.close()
    return jsonify({
        'active': True,
        'run': dict(run),
        'sessions': [dict(s) for s in sessions],
    })

@app.route('/api/ironman/start', methods=['POST'])
def ironman_start():
    uid = _get_user_id()
    if not uid:
        return jsonify({'error': 'unauthorized'}), 401
    conn = _get_db()
    # Check no active run
    active = conn.execute(
        'SELECT id FROM ironman_runs WHERE user_id=? AND status="active"', (uid,)).fetchone()
    if active:
        conn.close()
        return jsonify({'error': 'already_active'}), 409
    data = request.get_json(force=True) if request.is_json else {}
    balance = float(data.get('balance', 10000))
    target_pct = float(data.get('target_pct', 10.0))
    drawdown_pct = float(data.get('drawdown_pct', 20.0))
    max_sessions = int(data.get('max_sessions', 0))
    # Determine attempt number
    count = conn.execute(
        'SELECT COUNT(*) FROM ironman_runs WHERE user_id=?', (uid,)).fetchone()[0]
    conn.execute(
        'INSERT INTO ironman_runs (user_id, attempt, start_balance, balance, peak_balance, target_pct, drawdown_limit_pct, max_sessions) VALUES (?,?,?,?,?,?,?,?)',
        (uid, count + 1, balance, balance, balance, target_pct, drawdown_pct, max_sessions))
    conn.commit()
    run = conn.execute(
        'SELECT * FROM ironman_runs WHERE user_id=? AND status="active" ORDER BY id DESC LIMIT 1',
        (uid,)).fetchone()
    conn.close()
    return jsonify({'started': True, 'run': dict(run)})

@app.route('/api/ironman/session-complete', methods=['POST'])
def ironman_session_complete():
    uid = _get_user_id()
    if not uid:
        return jsonify({'error': 'unauthorized'}), 401
    conn = _get_db()
    run = conn.execute(
        'SELECT * FROM ironman_runs WHERE user_id=? AND status="active" ORDER BY id DESC LIMIT 1',
        (uid,)).fetchone()
    if not run:
        conn.close()
        return jsonify({'error': 'no_active_run'}), 404
    data = request.get_json()
    pnl = float(data.get('pnl', 0))
    new_balance = run['balance'] + pnl
    new_peak = max(run['peak_balance'], new_balance)
    day_num = run['day_count'] + 1

    conn.execute(
        'INSERT INTO ironman_sessions (run_id, day_num, character, seed, trades, wins, losses, pnl, balance_after) VALUES (?,?,?,?,?,?,?,?,?)',
        (run['id'], day_num, data.get('character'), data.get('seed'),
         int(data.get('trades', 0)), int(data.get('wins', 0)), int(data.get('losses', 0)),
         pnl, new_balance))
    conn.execute(
        'UPDATE ironman_runs SET balance=?, peak_balance=?, day_count=? WHERE id=?',
        (new_balance, new_peak, day_num, run['id']))

    # Check drawdown breach
    drawdown_pct = ((new_peak - new_balance) / run['start_balance']) * 100
    target_balance = run['start_balance'] * (1 + run['target_pct'] / 100)
    end_reason = None

    if drawdown_pct >= run['drawdown_limit_pct']:
        end_reason = 'drawdown_breach'
    elif new_balance >= target_balance:
        end_reason = 'target_reached'
    elif run['max_sessions'] and day_num >= run['max_sessions']:
        end_reason = 'max_sessions_reached'

    if end_reason:
        conn.execute(
            'UPDATE ironman_runs SET status="completed", ended_at=CURRENT_TIMESTAMP, end_reason=? WHERE id=?',
            (end_reason, run['id']))

    conn.commit()
    conn.close()
    return jsonify({
        'balance': new_balance,
        'peak': new_peak,
        'day': day_num,
        'drawdown_pct': round(drawdown_pct, 2),
        'ended': end_reason,
    })

@app.route('/api/ironman/forfeit', methods=['POST'])
def ironman_forfeit():
    uid = _get_user_id()
    if not uid:
        return jsonify({'error': 'unauthorized'}), 401
    conn = _get_db()
    run = conn.execute(
        'SELECT id FROM ironman_runs WHERE user_id=? AND status="active"', (uid,)).fetchone()
    if not run:
        conn.close()
        return jsonify({'error': 'no_active_run'}), 404
    conn.execute(
        'UPDATE ironman_runs SET status="completed", ended_at=CURRENT_TIMESTAMP, end_reason="forfeit" WHERE id=?',
        (run['id'],))
    conn.commit()
    conn.close()
    return jsonify({'forfeited': True})


@app.route('/api/sessions', methods=['POST'])
def api_save_session():
    uid = _get_user_id()
    if not uid:
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json(force=True)
    acct_id = None
    if not data.get('ironman'):
        acct = get_active_account(uid)
        acct_id = acct['id'] if acct else None
    import json as _json
    candles_json = _json.dumps(data['candles']) if data.get('candles') else None
    drawings_json = _json.dumps(data['drawings']) if data.get('drawings') else None
    session_id = save_session(uid, data.get('date', ''), data.get('character', ''),
                 int(data.get('trades', 0)), int(data.get('wins', 0)), float(data.get('pnl', 0)), acct_id,
                 seed=data.get('seed'), hist_days=data.get('hist_days'),
                 tick_size=data.get('tick_size'), tick_value=data.get('tick_value'),
                 candles=candles_json, trade_list=data.get('trade_list'), drawings=drawings_json,
                 ironman_run_id=data.get('ironman_run_id'))
    return jsonify({'saved': True, 'session_id': session_id})


@app.route('/api/sessions')
def api_get_sessions():
    uid = _get_user_id()
    if not uid:
        return jsonify({'error': 'unauthorized'}), 401
    account_id = request.args.get('account_id')
    if account_id:
        return jsonify(get_account_sessions(int(account_id)))
    return jsonify(get_sessions(uid))


@app.route('/api/sessions/<int:session_id>')
def api_get_session_detail(session_id):
    uid = _get_user_id()
    if not uid:
        return jsonify({'error': 'unauthorized'}), 401
    conn = _get_db()
    session = conn.execute('SELECT * FROM sessions WHERE id=? AND user_id=?', (session_id, uid)).fetchone()
    if not session:
        conn.close()
        return jsonify({'error': 'not_found'}), 404
    trades = conn.execute('SELECT * FROM trades WHERE session_id=? ORDER BY id', (session_id,)).fetchall()
    conn.close()
    s = dict(session)
    import json as _json
    s['candles'] = _json.loads(s['candles']) if s.get('candles') else []
    s['drawings'] = _json.loads(s['drawings']) if s.get('drawings') else []
    s['trade_list'] = [dict(t) for t in trades]
    return jsonify(s)


@app.route('/api/sessions/<int:session_id>/date', methods=['POST'])
def api_update_session_date(session_id):
    uid = _get_user_id()
    if not uid:
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json(force=True)
    new_date = data.get('date', '')
    conn = _get_db()
    row = conn.execute('SELECT id FROM sessions WHERE id=? AND user_id=?', (session_id, uid)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'not_found'}), 404
    conn.execute('UPDATE sessions SET date=? WHERE id=?', (new_date, session_id))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/trades')
def api_get_trades():
    uid = _get_user_id()
    if not uid:
        return jsonify({'error': 'unauthorized'}), 401
    account_id = request.args.get('account_id')
    conn = _get_db()
    if account_id:
        rows = conn.execute('SELECT t.* FROM trades t JOIN sessions s ON t.session_id=s.id WHERE s.user_id=? AND s.account_id=? ORDER BY t.id', (uid, int(account_id))).fetchall()
    else:
        rows = conn.execute('SELECT t.* FROM trades t JOIN sessions s ON t.session_id=s.id WHERE s.user_id=? AND s.account_id IS NOT NULL ORDER BY t.id', (uid,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/account')
def api_get_account():
    uid = _get_user_id()
    if not uid:
        return jsonify({'error': 'unauthorized'}), 401
    acct = get_active_account(uid)
    if not acct:
        create_account(uid)
        acct = get_active_account(uid)
    # Compute true balance from starting + sum of session PnLs
    from models import _get_db
    conn = _get_db()
    row = conn.execute('SELECT COALESCE(SUM(pnl),0) as total_pnl FROM sessions WHERE account_id=?', (acct['id'],)).fetchone()
    conn.close()
    acct['balance'] = acct['starting_balance'] + row['total_pnl']
    return jsonify(acct)


@app.route('/api/account', methods=['POST'])
def api_update_account():
    uid = _get_user_id()
    if not uid:
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json(force=True)
    acct = get_active_account(uid)
    if not acct:
        create_account(uid, float(data.get('balance', 50000)), float(data.get('commission', 2.25)))
    else:
        update_account_settings(acct['id'], float(data.get('balance', acct['balance'])),
                                float(data.get('commission', acct['commission_per_contract'])))
    return jsonify({'saved': True})


@app.route('/api/account/reset', methods=['POST'])
def api_reset_account():
    uid = _get_user_id()
    if not uid:
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json(force=True)
    reset_account(uid, float(data.get('balance', 50000)), float(data.get('commission', 2.25)))
    return jsonify({'reset': True})


@app.route('/api/account/update-balance', methods=['POST'])
def api_update_balance():
    uid = _get_user_id()
    if not uid:
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json(force=True)
    acct = get_active_account(uid)
    if not acct:
        return jsonify({'error': 'no_account'}), 404
    update_account_balance(acct['id'], float(data['balance']))
    return jsonify({'saved': True})


@app.route('/api/account/<int:account_id>/notes', methods=['GET', 'POST'])
def api_account_notes(account_id):
    uid = _get_user_id()
    if not uid:
        return jsonify({'error': 'unauthorized'}), 401
    from models import _get_db
    conn = _get_db()
    if request.method == 'POST':
        data = request.get_json(force=True)
        conn.execute('UPDATE trading_accounts SET notes=? WHERE id=? AND user_id=?', (data.get('notes', ''), account_id, uid))
        conn.commit()
        conn.close()
        return jsonify({'saved': True})
    row = conn.execute('SELECT notes FROM trading_accounts WHERE id=? AND user_id=?', (account_id, uid)).fetchone()
    conn.close()
    return jsonify({'notes': row['notes'] if row and row['notes'] else ''})


@app.route('/api/account/<int:account_id>/exclude', methods=['POST'])
def api_account_exclude(account_id):
    uid = _get_user_id()
    if not uid:
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json(force=True)
    from models import _get_db
    conn = _get_db()
    conn.execute('UPDATE trading_accounts SET excluded=? WHERE id=? AND user_id=?', (1 if data.get('excluded') else 0, account_id, uid))
    conn.commit()
    conn.close()
    return jsonify({'saved': True})


@app.route('/api/account/<int:account_id>', methods=['DELETE'])
def api_account_delete(account_id):
    uid = _get_user_id()
    if not uid:
        return jsonify({'error': 'unauthorized'}), 401
    from models import _get_db
    conn = _get_db()
    row = conn.execute('SELECT id FROM trading_accounts WHERE id=? AND user_id=?', (account_id, uid)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'not found'}), 404
    sess_ids = [r['id'] for r in conn.execute('SELECT id FROM sessions WHERE account_id=?', (account_id,)).fetchall()]
    if sess_ids:
        conn.execute(f"DELETE FROM trades WHERE session_id IN ({','.join('?'*len(sess_ids))})", sess_ids)
    conn.execute('DELETE FROM sessions WHERE account_id=?', (account_id,))
    conn.execute('DELETE FROM trading_accounts WHERE id=?', (account_id,))
    conn.commit()
    conn.close()
    return jsonify({'deleted': True})


@app.route('/api/account/<int:account_id>/export')
def api_account_export(account_id):
    uid = _get_user_id()
    if not uid:
        return jsonify({'error': 'unauthorized'}), 401
    from models import _get_db
    import csv, io
    conn = _get_db()
    acct = conn.execute('SELECT id, starting_balance FROM trading_accounts WHERE id=? AND user_id=?', (account_id, uid)).fetchone()
    if not acct:
        conn.close()
        return jsonify({'error': 'not found'}), 404
    sessions = conn.execute('SELECT id, date, character, trades, wins, pnl, tick_size, tick_value FROM sessions WHERE account_id=? ORDER BY id', (account_id,)).fetchall()
    sess_ids = [s['id'] for s in sessions]
    trades = []
    if sess_ids:
        trades = conn.execute(f"SELECT session_id, direction, qty, entry_price, entry_time, exit_price, exit_time, pnl, exit_reason FROM trades WHERE session_id IN ({','.join('?'*len(sess_ids))}) ORDER BY session_id, entry_time", sess_ids).fetchall()
    conn.close()

    sess_map = {s['id']: s for s in sessions}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['date', 'instrument', 'direction', 'qty', 'entry_price', 'exit_price', 'pnl', 'exit_reason', 'tick_size', 'tick_value'])
    for t in trades:
        s = sess_map[t['session_id']]
        w.writerow([s['date'], s['character'], t['direction'], t['qty'], t['entry_price'], t['exit_price'], round(t['pnl'] or 0, 2), t['exit_reason'], s['tick_size'], s['tick_value']])

    resp = app.response_class(buf.getvalue(), mimetype='text/csv')
    resp.headers['Content-Disposition'] = f'attachment; filename=account_{account_id}_trades.csv'
    return resp


@app.route('/api/account/<int:account_id>/export-candles')
def api_account_export_candles(account_id):
    uid = _get_user_id()
    if not uid:
        return jsonify({'error': 'unauthorized'}), 401
    from models import _get_db
    import csv, io
    conn = _get_db()
    acct = conn.execute('SELECT id FROM trading_accounts WHERE id=? AND user_id=?', (account_id, uid)).fetchone()
    if not acct:
        conn.close()
        return jsonify({'error': 'not found'}), 404
    sessions = conn.execute('SELECT date, character, candles FROM sessions WHERE account_id=? AND candles IS NOT NULL ORDER BY id', (account_id,)).fetchall()
    conn.close()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['session_date', 'instrument', 'time', 'open', 'high', 'low', 'close', 'volume'])
    for s in sessions:
        candles = json.loads(s['candles']) if s['candles'] else []
        for c in candles:
            w.writerow([s['date'], s['character'], c.get('t', ''), c.get('o', ''), c.get('h', ''), c.get('l', ''), c.get('c', ''), c.get('v', 0)])

    resp = app.response_class(buf.getvalue(), mimetype='text/csv')
    resp.headers['Content-Disposition'] = f'attachment; filename=account_{account_id}_candles.csv'
    return resp


@app.route('/api/account/archived')
def api_archived_accounts():
    uid = _get_user_id()
    if not uid:
        return jsonify({'error': 'unauthorized'}), 401
    return jsonify(get_archived_accounts(uid))


@app.route('/api/account/<int:account_id>/sessions')
def api_account_sessions(account_id):
    uid = _get_user_id()
    if not uid:
        return jsonify({'error': 'unauthorized'}), 401
    return jsonify(get_account_sessions(account_id))


@app.route('/api/account/purge-archived', methods=['POST'])
def api_purge_archived():
    uid = _get_user_id()
    if not uid:
        return jsonify({'error': 'unauthorized'}), 401
    purge_archived_accounts(uid)
    return jsonify({'purged': True})


@app.route('/settings')
def settings_page():
    return render_template('settings.html')


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

    # Truncate at last RTH boundary — history should stop at 09:29
    last_rth_start = None
    for i in range(1, len(candles)):
        if candles[i]['session'] == 'rth' and candles[i-1]['session'] != 'rth':
            last_rth_start = i
    if last_rth_start is not None:
        candles = candles[:last_rth_start]

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

    # Stamp as RTH directly — no session dampening
    import pandas as pd
    rth_start = pd.Timestamp('2024-01-02 09:30:00', tz='UTC')
    candle_dicts = []
    for i, (_, row) in enumerate(df.iterrows()):
        if i >= n_candles:
            break
        candle_dicts.append({
            'time': int((rth_start + pd.Timedelta(minutes=i)).timestamp()),
            'open': round(float(row['Open']), 2), 'high': round(float(row['High']), 2),
            'low': round(float(row['Low']), 2), 'close': round(float(row['Close']), 2),
            'volume': int(row['Volume']),
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

    ticks = generate_microstructure_ticks(candle_dicts, tick_cfg)

    return jsonify({'ticks': ticks, 'candles': candle_dicts, 'seed': seed})


@app.route('/api/character/list')
def character_list():
    items = []
    for key, spec in CHARACTERS.items():
        items.append({'id': key, 'name': spec.name, 'kind': 'builtin', 'initial_margin': spec.initial_margin})
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
    if not file or slot not in ('simulator', 'designer', 'stats'):
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

    # Generate full-session history (288 bars/day = 24hrs at 5-min)
    num_5min = num_hist_days * 288
    historical_df = None
    for _pct, df_result, _ts in dg.generate_historical_data(num_5min, profile=profile, seed=seed):
        if df_result is not None:
            historical_df = df_result

    from generators import apply_session_structure, extract_gap_cfg
    gap_cfg = extract_gap_cfg(profile) if hasattr(profile, 'gap') else {'prob': getattr(profile, 'gap_prob', 0), 'min_size': 0.002, 'max_size': 0.005}
    structured = apply_session_structure(historical_df, gap_cfg, tf_seconds=300, seed=seed)

    # Shift timestamps so last candle ends just before session's pre-market
    premarket_open = pd.Timestamp(f'{target} 06:00:00', tz='UTC')
    session_open   = pd.Timestamp(f'{target} 09:30:00', tz='UTC')
    target_last = int(premarket_open.timestamp()) - 300
    time_offset = target_last - structured[-1]['time']
    for c in structured:
        c['time'] += time_offset

    hist_1min = structured

    # Pre-market session (6:00–9:25, dampened vol)
    memory_hi = max(c['high'] for c in structured)
    memory_lo = min(c['low'] for c in structured)
    last_prices = [c['close'] for c in structured[-50:]]

    pm_profile = dg.InstrumentProfile(
        price_range=profile.price_range, tick=profile.tick,
        vol_chop=profile.vol_chop * 0.4, vol_trend=profile.vol_trend * 0.4,
        trend_duration=profile.trend_duration, drift_bias=profile.drift_bias * 0.3,
        wick_ratio_chop=profile.wick_ratio_chop, gap_prob=profile.gap_prob,
        volume_base=int(profile.volume_base * 0.25), name=profile.name + ' PM',
    )
    last_ts = pd.Timestamp(structured[-1]['time'], unit='s', tz='UTC')
    dg.NUM_SESSION_CANDLES = 210
    pm_df = dg.simulate_session_candles(last_prices, memory_hi, memory_lo, last_ts, profile=pm_profile)
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
        'tick_value':   getattr(profile, 'tick_value', 12.50),
        'initial_margin': getattr(profile, 'initial_margin', 0),
        'maintenance_margin': getattr(profile, 'maintenance_margin', 0),
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
