"""User model - SQLite + bcrypt + Flask-Login."""
import os
import sqlite3
import bcrypt
from datetime import datetime, timedelta
from flask_login import UserMixin

DB_PATH = os.environ.get('PF_DB_PATH', os.path.join(os.path.dirname(__file__), 'data', 'users.db'))


def _get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        name TEXT NOT NULL,
        role TEXT DEFAULT 'user',
        tier TEXT DEFAULT 'free',
        banned INTEGER DEFAULT 0,
        last_login_ip TEXT,
        last_login_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS ironman_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        attempt INTEGER DEFAULT 1,
        status TEXT DEFAULT 'active',
        start_balance REAL DEFAULT 10000,
        balance REAL DEFAULT 10000,
        peak_balance REAL DEFAULT 10000,
        target_pct REAL DEFAULT 10.0,
        drawdown_limit_pct REAL DEFAULT 20.0,
        day_count INTEGER DEFAULT 0,
        started_at TEXT DEFAULT CURRENT_TIMESTAMP,
        ended_at TEXT,
        end_reason TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS ironman_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        day_num INTEGER NOT NULL,
        character TEXT,
        seed TEXT,
        trades INTEGER DEFAULT 0,
        wins INTEGER DEFAULT 0,
        losses INTEGER DEFAULT 0,
        pnl REAL DEFAULT 0,
        balance_after REAL,
        completed_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(run_id) REFERENCES ironman_runs(id)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        character TEXT,
        trades INTEGER DEFAULT 0,
        wins INTEGER DEFAULT 0,
        pnl REAL DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS trading_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        starting_balance REAL DEFAULT 50000,
        balance REAL DEFAULT 50000,
        commission_per_contract REAL DEFAULT 2.25,
        status TEXT DEFAULT 'active',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        archived_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')
    # Add account_id to sessions if missing (migration-safe)
    try:
        conn.execute('ALTER TABLE sessions ADD COLUMN account_id INTEGER')
    except Exception:
        pass
    # Session replay columns
    for col in [('seed', 'TEXT'), ('hist_days', 'INTEGER'), ('tick_size', 'REAL'), ('tick_value', 'REAL'), ('candles', 'TEXT'), ('drawings', 'TEXT')]:
        try:
            conn.execute(f'ALTER TABLE sessions ADD COLUMN {col[0]} {col[1]}')
        except Exception:
            pass
    try:
        conn.execute('ALTER TABLE sessions ADD COLUMN ironman_run_id INTEGER')
    except Exception:
        pass
    try:
        conn.execute('ALTER TABLE ironman_runs ADD COLUMN max_sessions INTEGER DEFAULT 0')
    except Exception:
        pass
    try:
        conn.execute('ALTER TABLE trading_accounts ADD COLUMN notes TEXT DEFAULT ""')
    except Exception:
        pass
    try:
        conn.execute('ALTER TABLE trading_accounts ADD COLUMN excluded INTEGER DEFAULT 0')
    except Exception:
        pass
    # Per-trade data
    conn.execute('''CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        direction TEXT,
        qty INTEGER,
        entry_price REAL,
        entry_time INTEGER,
        exit_price REAL,
        exit_time INTEGER,
        pnl REAL,
        exit_reason TEXT,
        FOREIGN KEY(session_id) REFERENCES sessions(id)
    )''')
    conn.commit()
    conn.close()


def get_active_account(user_id):
    conn = _get_db()
    row = conn.execute('SELECT * FROM trading_accounts WHERE user_id=? AND status="active"', (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_account(user_id, balance=50000, commission=2.25):
    conn = _get_db()
    conn.execute('INSERT INTO trading_accounts (user_id, starting_balance, balance, commission_per_contract) VALUES (?,?,?,?)',
                 (user_id, balance, balance, commission))
    conn.commit()
    conn.close()


def update_account_balance(account_id, new_balance):
    conn = _get_db()
    conn.execute('UPDATE trading_accounts SET balance=? WHERE id=?', (new_balance, account_id))
    conn.commit()
    conn.close()


def update_account_settings(account_id, balance, commission):
    conn = _get_db()
    conn.execute('UPDATE trading_accounts SET balance=?, starting_balance=?, commission_per_contract=? WHERE id=?',
                 (balance, balance, commission, account_id))
    conn.commit()
    conn.close()


def reset_account(user_id, balance=50000, commission=2.25):
    conn = _get_db()
    # If active account has no sessions, just delete it instead of archiving
    active = conn.execute('SELECT id FROM trading_accounts WHERE user_id=? AND status="active"', (user_id,)).fetchone()
    if active:
        has_sessions = conn.execute('SELECT 1 FROM sessions WHERE account_id=? LIMIT 1', (active['id'],)).fetchone()
        if has_sessions:
            conn.execute('UPDATE trading_accounts SET status="archived", archived_at=CURRENT_TIMESTAMP WHERE id=?', (active['id'],))
        else:
            conn.execute('DELETE FROM trading_accounts WHERE id=?', (active['id'],))
    conn.execute('INSERT INTO trading_accounts (user_id, starting_balance, balance, commission_per_contract) VALUES (?,?,?,?)',
                 (user_id, balance, balance, commission))
    conn.commit()
    conn.close()


def get_archived_accounts(user_id):
    conn = _get_db()
    rows = conn.execute('SELECT * FROM trading_accounts WHERE user_id=? AND status="archived" ORDER BY archived_at DESC', (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_account_sessions(account_id):
    conn = _get_db()
    acct = conn.execute('SELECT user_id, status FROM trading_accounts WHERE id=?', (account_id,)).fetchone()
    if not acct:
        conn.close()
        return []
    first = conn.execute('SELECT id FROM trading_accounts WHERE user_id=? ORDER BY id ASC LIMIT 1', (acct['user_id'],)).fetchone()
    if first and first['id'] == account_id:
        rows = conn.execute('SELECT id, date, character, trades, wins, pnl FROM sessions WHERE (account_id=? OR (account_id IS NULL AND user_id=?)) ORDER BY id ASC', (account_id, acct['user_id'])).fetchall()
    else:
        rows = conn.execute('SELECT id, date, character, trades, wins, pnl FROM sessions WHERE account_id=? ORDER BY id ASC', (account_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def purge_archived_accounts(user_id):
    conn = _get_db()
    conn.execute('DELETE FROM sessions WHERE account_id IN (SELECT id FROM trading_accounts WHERE user_id=? AND status="archived")', (user_id,))
    conn.execute('DELETE FROM sessions WHERE account_id IS NULL AND user_id=?', (user_id,))
    conn.execute('DELETE FROM trading_accounts WHERE user_id=? AND status="archived"', (user_id,))
    conn.commit()
    conn.close()


def nuke_user_stats(user_id):
    conn = _get_db()
    # Delete trades for all user sessions
    conn.execute('DELETE FROM trades WHERE session_id IN (SELECT id FROM sessions WHERE user_id=?)', (user_id,))
    conn.execute('DELETE FROM sessions WHERE user_id=?', (user_id,))
    conn.execute('DELETE FROM ironman_sessions WHERE run_id IN (SELECT id FROM ironman_runs WHERE user_id=?)', (user_id,))
    conn.execute('DELETE FROM ironman_runs WHERE user_id=?', (user_id,))
    conn.execute('DELETE FROM trading_accounts WHERE user_id=?', (user_id,))
    conn.commit()
    conn.close()


def save_session(user_id, date, character, trades, wins, pnl, account_id=None, seed=None, hist_days=None, tick_size=None, tick_value=None, candles=None, trade_list=None, drawings=None, ironman_run_id=None):
    conn = _get_db()
    conn.execute('INSERT INTO sessions (user_id, date, character, trades, wins, pnl, account_id, seed, hist_days, tick_size, tick_value, candles, drawings, ironman_run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                 (user_id, date, character, trades, wins, pnl, account_id, seed, hist_days, tick_size, tick_value, candles, drawings, ironman_run_id))
    session_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    if trade_list:
        for t in trade_list:
            conn.execute('INSERT INTO trades (session_id, direction, qty, entry_price, entry_time, exit_price, exit_time, pnl, exit_reason) VALUES (?,?,?,?,?,?,?,?,?)',
                         (session_id, t.get('dir'), t.get('qty'), t.get('entry'), t.get('entryTime'), t.get('exit'), t.get('exitTime'), t.get('pnl'), t.get('reason')))
    conn.commit()
    conn.close()
    return session_id


def get_sessions(user_id):
    conn = _get_db()
    first = conn.execute('SELECT id FROM trading_accounts WHERE user_id=? ORDER BY id ASC LIMIT 1', (user_id,)).fetchone()
    active = conn.execute('SELECT id FROM trading_accounts WHERE user_id=? AND status="active"', (user_id,)).fetchone()
    include_nulls = first and active and first['id'] != active['id']
    if include_nulls:
        rows = conn.execute('SELECT id, date, character, trades, wins, pnl, account_id, created_at FROM sessions WHERE user_id=? ORDER BY id ASC', (user_id,)).fetchall()
    else:
        rows = conn.execute('SELECT id, date, character, trades, wins, pnl, account_id, created_at FROM sessions WHERE user_id=? AND account_id IS NOT NULL ORDER BY id ASC', (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


class User(UserMixin):
    def __init__(self, id, email, name, role='user', tier='free', banned=0):
        self.id = id
        self.email = email
        self.name = name
        self.role = role
        self.tier = tier
        self.banned = banned

    @property
    def is_admin(self):
        return self.role == 'admin'

    @staticmethod
    def create(email, password, name):
        email = email.strip().lower()
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        conn = _get_db()
        # First user becomes admin
        count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        role = 'admin' if count == 0 else 'user'
        tier = 'edge' if count < 50 else 'free'
        try:
            conn.execute('INSERT INTO users (email, password_hash, name, role, tier) VALUES (?, ?, ?, ?, ?)',
                         (email, pw_hash, name, role, tier))
            conn.commit()
            user_id = conn.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone()[0]
            conn.close()
            return User(user_id, email, name, role, tier)
        except sqlite3.IntegrityError:
            conn.close()
            return None  # duplicate email

    @staticmethod
    def verify_password(email, password):
        email = email.strip().lower()
        conn = _get_db()
        row = conn.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
        conn.close()
        if not row:
            return None
        if row['banned']:
            return None
        if bcrypt.checkpw(password.encode(), row['password_hash'].encode()):
            return User(row['id'], row['email'], row['name'], row['role'], row['tier'], row['banned'])
        return None

    @staticmethod
    def get_by_id(user_id):
        conn = _get_db()
        row = conn.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
        conn.close()
        if not row:
            return None
        return User(row['id'], row['email'], row['name'], row['role'], row['tier'], row['banned'])

    @staticmethod
    def get_all():
        conn = _get_db()
        rows = conn.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def record_login(user_id, ip):
        conn = _get_db()
        conn.execute('UPDATE users SET last_login_ip=?, last_login_at=? WHERE id=?',
                     (ip, datetime.utcnow().isoformat(), user_id))
        conn.commit()
        conn.close()

    @staticmethod
    def set_role(user_id, role):
        conn = _get_db()
        conn.execute('UPDATE users SET role=? WHERE id=?', (role, user_id))
        conn.commit()
        conn.close()

    @staticmethod
    def set_banned(user_id, banned):
        conn = _get_db()
        conn.execute('UPDATE users SET banned=? WHERE id=?', (int(banned), user_id))
        conn.commit()
        conn.close()

    @staticmethod
    def set_tier(user_id, tier):
        conn = _get_db()
        conn.execute('UPDATE users SET tier=? WHERE id=?', (tier, user_id))
        conn.commit()
        conn.close()


init_db()
