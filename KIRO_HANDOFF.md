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
5. **NO M-DASHES (—) IN REPLIES.** Use commas, periods, or rewrite the sentence instead.
6. **Add 1-2 misspelled words in Reddit replies.** Makes it look human/casual, not AI-generated.

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
| `/marketing/scripts` | `marketing_scripts.html` | Copy-paste post scripts (Reddit, X, HN, SEO) |
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
| `templates/marketing_scripts.html` | Copy-paste marketing scripts (Reddit replies, value posts, X threads, HN) |
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

## Recent Work (2026-06-08 session 8)

1. **Reddit account active** — Created under neutral username (not brand-linked). Avatar built (trading-adjacent SVG/PNG). Bio intentionally blank for now (add in week 2-3). Account age gate on r/futurestrading (3 days), active on r/daytrading. Multiple helpful replies posted, gaining karma organically.
2. **Session date reassignment** — Users can change the display date of any session via date picker in stats history. API: `POST /api/sessions/<id>/date`. Calendar + monthly P&L update live on change.
3. **Stats bugs fixed** — Best Day card sign, monthly P&L UTC timezone off-by-one, calendar not refreshing on date change.
4. **FLAT tag for zero-trade sessions** — Orange tag for sessions closed with no trades. Previously these were silently discarded; now they save properly.
5. **Risk % position sizing** — Risk % input auto-calculates qty from account balance, SL distance, and tick value. Capped at max margin allowance. Minimum 1 contract.
6. **Intraday margin (25%)** — Both initial and maintenance margin checks now use 25% of listed values (intraday rate, matching Tradovate-style).
7. **Tier system** — First 50 registrations auto-get 'edge' tier (lifetime free). Admin panel: Grant Edge / Mark Test / Set Free buttons. Landing page updated: "First 50 Users Get Lifetime Free Access."
8. **SEO landing page** — `/free-trading-simulator` targeting "free futures trading simulator" keyword. Comparison table vs paid tools, feature grid, CTAs. Added to sitemap.
9. **Sticky headers** — All pages except simulator/designer now have sticky nav header (always visible in screenshots).
10. **SL/TP exit reason fix** — Exit reason now determined by price position relative to entry (not variable name), preventing "TP Hit" labels on losing trades when lines are dragged.
11. **Drawing color persistence** — Saved in localStorage, restored across sessions.
12. **Hotkeys [ ]** — `[` = 1x speed, `]` = max speed.
13. **INSTRUMENT CHARACTER OVERHAUL** — All 14 instruments completely recalibrated:
    - Counter-trend flip reduced 35% → 18% (trends actually trend now)
    - Mean-reversion tether reduced 0.0005 → 0.0001
    - Longer trend durations (30-40 bars), trend-to-trend transitions added
    - All instruments now produce realistic daily ranges (NQ ~230pts, ES ~55pts, CL ~$2.20, etc.)
14. **Docs: Instrument Presets Reference** — `/docs/presets` page documenting all settings for every instrument with rationale and tuning guide.
15. **TF switch candle compression fix** — After switching timeframes, currentCandle is initialized from last bucket to prevent data loss.
16. **Indicator performance fix** — `buildAllCandles()` now incremental (maintains running array) instead of rebuilding from all ticks every 5 ticks. Massive improvement for long history sessions.

---

## Next Steps

- **VALUE POST (READY TO DRAFT)** — ORB comparison data complete: 2:1 target = -16% (28% WR), 1:1 target = +7.4% (59% WR). Screenshots in `tmp/ORB_2-1.png` and `tmp/ORB_1-1.png`. Consider re-running 2:1 data with updated instrument characters for apples-to-apples comparison.
- **Reddit strategy** — Continue daily 2-3 replies across r/daytrading (r/futurestrading unlocks after 3-day age). Build to 50+ karma before value post.
- **AlternativeTo submission** — Account created, submit on weekday (paused on weekends). Listing copy ready in chat history.
- **HN Show HN** — Target week 3. Post script exists in `/marketing/scripts`.
- **Remaining features:** Chart Designer tick_value/margin fields for custom chars, partial position exits (peel off), session journal/annotations, export data button.
- **Usage note:** At 70% monthly usage on June 8th. Be efficient with context in future sessions.
- **See board + /feature-ideas** for full roadmap

---

## Contact / Repo

- GitHub: https://github.com/dvln811/PatternFoundry
- Reference (read-only): /media/devlyn/Leviathan/Projects/StrategyScreener
- Owner: Devlyn Napoli (devlynnapoli@protonmail.com)
