# Kiro Handoff - PatternFoundry Rebuild

## What This Is

PatternFoundry is a **clean-room rebuild** of a trading simulator concept.
It is being built from scratch, on personal time and resources, by Devlyn Napoli.

**Do not copy code from the reference repo.** Use it only to understand
what was built before - architecture, UI patterns, feature behavior - then
rewrite everything from scratch in this repo.

---

## WORKFLOW RULES

1. **Commit and push automatically after completing each task/change.** Use `GIT_TERMINAL_PROMPT=0 git push` to avoid interactive prompt hangs. Do not wait for user confirmation.
2. Read this file at the start of every session.
3. Check `git log --oneline -5` and `git status` before starting.
4. Ask the user what they want to work on.

---

## Reference Repo (READ ONLY - do not copy code)

```
/media/devlyn/Leviathan/Projects/StrategyScreener
```

**The rule:** Understand the behavior, rewrite the implementation.

---

## Current State (as of 2026-06-04)

### Deployed & Live
- **Site:** https://patternfoundry.net (Fly.io, auto-deploys from GitHub on push to main)
- **Repo:** https://github.com/dvln811/PatternFoundry
- **Branch:** main
- **Auth:** Flask-Login + bcrypt, SQLite on persistent volume (`/data/users.db`)
- **Local dev:** `PF_LOCAL=1` skips auth (default)
- **Git push:** Use `GIT_TERMINAL_PROMPT=0 git push` (credentials in `~/.git-credentials`, credential.helper=store)

### Architecture
- **Backend:** Python/Flask, gunicorn in production
- **Frontend:** Vanilla JS, LightweightCharts v4.2 (simulator/designer), Chart.js (stats)
- **Data generation:** `generators/` package (v2 vectorized pipeline) + `data_generator.py` (legacy tick paths)
- **Tick engine:** `tick_engine.py` (agent-based microstructure) + `order_book.py` (simulated LOB)
- **User model:** `models.py` (SQLite, bcrypt, Flask-Login, Iron Man + trading accounts + sessions + trades)
- **Deployment:** Dockerfile + fly.toml + GitHub Actions CI (push to main = auto-deploy)
- **SEO:** robots.txt, sitemap.xml, OG/meta tags on landing page

### Pages Built
| Route | Template | Purpose |
|-------|----------|---------|
| `/` | `landing.html` (unauth) / `dashboard.html` (auth) | Landing page / Dashboard |
| `/simulator` | `chart.html` | Live trading simulator + Session Review mode (`?replay=<id>`) |
| `/chartdesigner` | `chartdesigner.html` | Instrument designer + tick engine preview |
| `/stats` | `stats.html` | Performance stats, equity curves, account selector, streaks, Iron Man |
| `/settings` | `settings.html` | Trading account settings (reset only — no mid-account edits) |
| `/docs` | `docs.html` | Documentation hub |
| `/docs/<section>` | `docs_*.html` | 7 doc sub-pages |
| `/login` | `auth_login.html` | Login |
| `/register` | `auth_register.html` | Registration |
| `/feedback` | `feedback.html` | User feedback form |
| `/admin` | `admin_hub.html` | Admin hub |
| `/admin/users` | `admin_users.html` | User management + Nuke Stats button |
| `/admin/feedback` | `admin_feedback.html` | View feedback submissions |
| `/board` | `board.html` | Kanban board (auto-syncs to server on Fly) |
| `/marketing` | `marketing.html` | Marketing plan (strategy, channels, launch sequence) |
| `/marketing/board` | `marketing_board.html` | Marketing Kanban board (5 cols, channel-based cards) |
| `/feature-ideas` | `feature_ideas.html` | Design docs for upcoming features |

### Instruments (14 total)
| Symbol | Name | Tick | Tick Value | Initial Margin | Maintenance |
|--------|------|------|-----------|----------------|-------------|
| ES | E-mini S&P | 0.25 | $12.50 | $12,980 | $11,800 |
| NQ | E-mini Nasdaq | 0.25 | $5.00 | $17,600 | $16,000 |
| CL | Crude Oil | 0.01 | $10.00 | $12,000 | $10,900 |
| RTY | E-mini Russell | 0.10 | $5.00 | $6,800 | $6,200 |
| MES | Micro S&P | 0.25 | $1.25 | $1,265 | $1,150 |
| MNQ | Micro Nasdaq | 0.25 | $0.50 | $1,760 | $1,600 |
| MCL | Micro Crude | 0.01 | $1.00 | $1,200 | $1,090 |
| M2K | Micro Russell | 0.10 | $0.50 | $680 | $620 |
| SPY | S&P 500 ETF | 0.01 | $1.00 | $275/sh | $165/sh |
| AAPL | Apple | 0.01 | $1.00 | $105/sh | $63/sh |
| MSFT | Microsoft | 0.01 | $1.00 | $220/sh | $132/sh |
| PLTR | Palantir | 0.01 | $1.00 | $60/sh | $36/sh |
| TSLA | Tesla | 0.01 | $1.00 | $120/sh | $72/sh |
| GME | GameStop | 0.01 | $1.00 | $13/sh | $8/sh |

- Defined in `generators/characters.py` + `generators/spec.py`
- Commission = `tickValue * qty` (1 tick per contract round-trip, calculated client-side)
- Custom characters default to tick_value=12.50 if not specified

### Margin System
- **Initial margin** checked on order confirm: `qty × initial_margin > balance` → order rejected with message
- **Maintenance margin** checked every tick: if equity (balance + unrealized P&L) < `qty × maintenance_margin` → auto-liquidate with "Margin Call" message
- Values stored in CharacterSpec, passed to client via `/api/sim-session` response

### Key Features Working
- **Simulator:** Session generation, tick playback (0.25x-200x), trade execution (market/limit/stop-limit), draggable SL/TP, DOM with real order book, indicators (7 built-in + custom scripting), drawing tools (13 types + text + right-click property editor + **lock button**), session save/load, multi-timeframe, Close Session button, persistent account balance, per-instrument commission, risk % display, **margin system** (initial check + maintenance auto-liquidation), **hotkeys** (Space=play/pause, +/-=speed, B=buy, S=sell)
- **Session Replay:** Full simulator in review mode — loads stored session candles + regenerated history, trade markers, TF switching, indicators, drawings restored
- **Trading Accounts:** Server-side persistent, rolling balance, reset archives (empty accounts auto-deleted on reset), per-account session linking. Settings page: reset only (no mid-account balance edits)
- **Chart Designer:** All 14 instruments as presets (grouped: E-mini, Micro, Stocks), CharacterSpec + MicroConfig sliders, generate + preview, tick engine glass-box view, save custom characters
- **Iron Man Mode:** Configurable start params (balance, drawdown%, target%, max_sessions). Presets: Micro $5k, Standard $10k, Full $50k, Hardcore. Margin-filtered random instrument selection (only picks instruments the balance can afford). `ironman_run_id` on sessions table links replay sessions to specific runs. End conditions: drawdown breach, target reached, max sessions reached, forfeit.
- **Stats Page:** 3-tab layout (Overview / Account Details / Iron Man). Overview: EQ curve + quick stats sidebar, 12-month P&L grid, month calendar, top instruments, session distribution, recent sessions, streak + heatmap. Account Details: simplified account rows (Status/Balance/Date) + Starting/P&L cards, 8 stat cards, equity curve, drawdown, instrument breakdown, session history. Iron Man: configurable presets, active run progress, past attempts, aggregate metrics.
- **Admin:** Nuke Stats button on Users page (wipes all user data — sessions, trades, Iron Man, accounts). Works for all users including admin's own account.
- **Dashboard:** Live Yahoo Finance tickers, chart, news feed. Sidebar: real stats (sessions, trades, win rate, P/L, best day, streak) + recent sessions.
- **Auth:** Login/register/logout, first user = admin
- **Board/Landing/Docs/SEO:** All working. Landing has 3-col screenshot grid. Docs: 8 pages (getting started, simulator, designer, indicators, orderbook, pricing, ironman, stats).

### Data Generation Pipeline
1. `generators/` - v2 vectorized: CharacterSpec -> 9-stage pipeline -> session structure
2. `data_generator.py` - Legacy: simulate_session_candles + generate_tick_path
3. `tick_engine.py` - Microstructure: 4 agent types, Hawkes clustering, order book, liquidity pools
4. `order_book.py` - Simulated LOB
5. `/api/sim-session` - Full 24hr history via `apply_session_structure` (288 bars/day) + pre-market + RTH session + tick paths

### Trading Account System
- **Table:** `trading_accounts` (user_id, starting_balance, balance, commission_per_contract, status, created_at, archived_at)
- **Behavior:** One active account per user. Balance rolls forward. Reset: if account has sessions → archive; if empty → delete. New account created with specified starting balance.
- **Sessions table:** `sessions` (user_id, date, character, trades, wins, pnl, account_id, seed, hist_days, tick_size, tick_value, candles, drawings, ironman_run_id)
- **Iron Man sessions:** Saved with `account_id=NULL` + `ironman_run_id` set. Does NOT update regular account balance.
- **Trades table:** `trades` (session_id, direction, qty, entry_price, entry_time, exit_price, exit_time, pnl, exit_reason)

### Iron Man Mode
- **Tables:** `ironman_runs` (user, attempt, status, start_balance, balance, peak_balance, target_pct, drawdown_limit_pct, max_sessions, day_count, started_at, ended_at, end_reason) + `ironman_sessions` (run_id, day_num, character, seed, trades, wins, losses, pnl, balance_after)
- **API:**
  - `GET /api/ironman/status` - active run + sessions, or history of past runs
  - `POST /api/ironman/start` - accepts `{balance, target_pct, drawdown_pct, max_sessions}`
  - `POST /api/ironman/session-complete` - submit session (auto-checks drawdown/target/max_sessions)
  - `POST /api/ironman/forfeit` - end run voluntarily
- **End conditions:** drawdown breach, target reached, max_sessions reached, forfeit
- **Simulator integration:**
  - On load: checks status, if active → enters Iron Man mode
  - Instrument selection: filters `_characterList` by `initial_margin <= balance`, random pick
  - History locked to 3 months (63 days)
  - On session close: saves to `/api/sessions` with `ironman:true` + `ironman_run_id`, submits to `/api/ironman/session-complete`, does NOT update regular account balance
- **Stats page:** Configurable start with presets + custom fields, past attempts history table

---

## Key Files

| File | Purpose |
|------|---------|
| `app.py` | Flask routes + API endpoints |
| `models.py` | DB models + migrations (SQLite) |
| `generators/spec.py` | CharacterSpec dataclass (tick_value, initial_margin, maintenance_margin) |
| `generators/characters.py` | 14 built-in instruments |
| `data_generator.py` | Legacy generator + tick path decomposition |
| `tick_engine.py` | Agent-based microstructure tick simulation |
| `order_book.py` | Simulated limit order book |
| `static/canvas-overlay.js` | Drawing tools (14 types + text + property editor + lock) |
| `static/indicators.js` | Client-side indicator math (7 indicators) |
| `static/custom-indicator.js` | Custom indicator execution engine |
| `templates/chart.html` | Simulator SPA (~2200 lines) |
| `templates/chartdesigner.html` | Chart Designer SPA (14 presets) |
| `templates/marketing_board.html` | Marketing Kanban board (5 cols, channel-based) |
| `templates/stats.html` | Stats + Iron Man config |
| `templates/settings.html` | Account reset only |
| `templates/admin_users.html` | User management + nuke button |
| `restart_server.sh` | Local dev server launcher |
| `fly.toml` | Fly.io deployment config |
| `.github/workflows/fly.yml` | GitHub Actions auto-deploy |

---

## Environment

- **Fly secrets:** `BOARD_API_KEY`
- **Fly env:** `PF_LOCAL=0`, `PF_DB_PATH=/data/users.db`
- **Local:** `PF_LOCAL=1` (default, skips auth), `BOARD_API_KEY` set in restart_server.sh
- **Persistent volume:** `/data/` on Fly (users.db, boards/)
- **Git credentials:** `~/.git-credentials` (credential.helper=store). Always use `GIT_TERMINAL_PROMPT=0` on push.

---

## Recent Work (2026-06-04 session 6)

1. **Off-hours shading fix (backend)** — `/api/sim-session` now uses `apply_session_structure()` with `tf_seconds=300` to generate full 24hr candles (288/day) instead of RTH-only (78/day). Off-hours bars have dampened body/volume. History has proper overnight/london/pre-market candles for shading.
2. **Off-hours shading fix (frontend)** — Both `chart.html` and `chartdesigner.html` now use `logicalToCoordinate(index)` instead of `timeToCoordinate(timestamp)` for reliable off-hours shading across all bars regardless of scroll position.
3. **Chart Designer tick playback performance** — Rewrote `startTickPlayback()` to batch ticks per frame (speed/10 per 16ms frame) with single `candleSeries.update()` per frame. Cached DOM refs for debug panel. Removed full `renderCandles()`/`setData()` per tick.
4. **Chart Designer TF bucketing** — Tick candles now bucket to selected TF using `Math.floor(time/tf)*tf` (same as simulator's `getCandleTime`). Tracks `window._displayCandle` at TF level. Fixes issue where 30-min TF showed per-minute bars during playback.
5. **Chart Designer: history truncated at RTH** — `character_generate()` now truncates output at last RTH boundary so generated history stops at 09:29. Tick engine handles RTH playback.
6. **Chart Designer: tick-preview no dampening** — `/api/character/tick-preview` no longer uses `apply_session_structure`. Generates raw candles stamped as RTH (09:30+) with full volatility. Tick engine gets undampened data.
7. **Chart Designer: tick timestamp anchoring** — Frontend anchors `_lastHistTime` to 09:29 so tick candles start at 09:30 (proper RTH timestamps in the shading).
8. **Chart Designer: shading throttle removed** — `drawOffHoursShading` called directly on visible range change (no 200ms throttle), matching simulator behavior.
9. **Marketing Board** — New `/marketing/board` page: 5-column Kanban (Backlog, This Week, Next Week, Ongoing, Done), channel-based badges (twitter/reddit/discord/content/youtube/product), seeded with 20 actionable marketing cards. API: `/api/marketing-board/save` + `/api/marketing-board/load`.
10. **Marketing Plan rewrite** — `/marketing` completely rewritten: positioning ("the driving range for traders"), target audience (prop firm candidates, futures beginners), channel strategy with cadence, content angles, rules of engagement, 6-week launch sequence, competitive landscape, success metrics, monetization path.

---

## Next Steps

- **MARKETING EXECUTION** — Follow the 6-week launch plan. See `/marketing/board` for actionable tasks. Week 1: screenshots, create accounts, lurk.
- **Chart Designer tick_value:** Add tick_value/margin fields to designer UI for custom characters
- **Session history:** Per-trade annotations, journal notes
- **See board + /feature-ideas** for full roadmap

---

## Contact / Repo

- GitHub: https://github.com/dvln811/PatternFoundry
- Reference (read-only): /media/devlyn/Leviathan/Projects/StrategyScreener
- Owner: Devlyn Napoli (devlynnapoli@protonmail.com)
