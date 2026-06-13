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

## Recent Work (2026-06-12 session 10)

1. **TF switch crash fix (root cause)** — `rebucketHistory()` was returning array by reference when tf<=60. `buildAllCandles()` then mutated `_historyBars` by pushing played candles. Next TF switch = duplicate timestamps = "Value is null" crash. Fixed with `.slice()`.
2. **Per-account delete** — DELETE `/api/account/<id>` endpoint. Cascades to sessions + trades. Small × button on each account row in Stats Account Details.
3. **Limit order fix** — Trigger logic was using stop-order logic for limits (backwards). Now: buy limit triggers when price drops to entry, sell limit when price rises. Also fixed `isMarket` check to be directionally correct.
4. **CSV export (trades)** — GET `/api/account/<id>/export`. One row per trade: date, instrument, direction, qty, entry/exit price, pnl, exit_reason, tick_size, tick_value.
5. **CSV export (1m candles)** — GET `/api/account/<id>/export-candles`. One row per candle per session for regime analysis.
6. **Duplicate seed bug found & fixed** — Seed field was auto-populating after load, causing re-send of same seed on next session = identical price data. Fixed: seed now shows as placeholder only, not field value. Also added `sessionSeed` variable so seed still saves correctly for replay.
7. **Session balance bug fixed** — `loadSession()` now fetches fresh balance from server before creating account object. Was using stale page-load value.
8. **Start/End Balance columns** — Added to session history table in Account Details. Running cumulative from account starting_balance.
9. **6 mini analytics charts** — Replaced DD chart with 2x3 grid: Rolling Win Rate (10-trade), Rolling Expectancy, R-Multiple per trade, DD Duration, P/L Distribution histogram, Cumulative R.
10. **Landing page audit** — Fixed: removed crypto/forex references, updated to 14 instruments, removed fake "thousands of traders" claim, fixed comparison table, reworked promo card ("Limited Offer" framing).
11. **Blog engine** — Markdown files rendered at `/blog`. Admin editor at `/admin/blog` with toolbar (H2/H3/Bold/Italic/Code/Link/Img/Quote/List), image upload, live preview, post CRUD. Storage on Fly persistent volume (`/data/blog`). Blog images served from `/blog/images/`.
12. **Public routes** — `/blog` and `/docs` no longer require login.
13. **Blog editor features** — Excerpt field, auto-generate slug button.

---

## Current State (as of 2026-06-13)

### Blog Engine
- **Editor:** `/admin/blog` — full WYSIWYG-ish markdown editor with toolbar, image upload, live preview
- **Storage:** `/data/blog/` on Fly persistent volume (local: `blog/` dir)
- **Images:** Upload via editor, stored in `/data/blog/images/` (local: `static/blog/`), served at `/blog/images/<filename>`
- **Posts:** YAML front matter (title, date, author, excerpt) + markdown body
- **Pending posts on marketing board (Backlog):**
  - Agent-Based Order Flow Simulation
  - Why Random Walks Don't Look Like Markets
  - Building a Simulated Limit Order Book
  - The Problem with Backtesting on Historical Data
- **This Week:** Re-upload "Simulating Realistic Market Regimes" via editor with screenshots (chop_trend.png, transition.png, reg_vol_sliders.png in `tmp/`). Back-date to 2026-05-12.

### Marketing Status
- **Reddit:** ~42 karma. Strategy deprioritized (mod friction, not the right channel for Devlyn's style). May still post value post at 50 karma but not primary focus.
- **Primary channels going forward:** X (Twitter), AlternativeTo (7-day account age needed), Product Hunt, SEO blog posts, Google Ads ($50/mo budget identified).
- **AlternativeTo:** Account created, nearing 7-day age requirement for submission.
- **Blog for SEO:** Engine built, first post screenshots ready, 4 more posts outlined.

### Data/Research
- **Account 17 (1:1 ORB):** Clean, 25 sessions, no duplicates. 58.8% WR, +$3,722 net. Good for analysis.
- **Account 18 (2:1 ORB):** Had duplicate seed issues (8 duplicate pairs). Needs re-run with fresh sessions.
- **Export files in `tmp/`:** orb_retest_trades.csv, orb_retest_candles.csv, account_17_trades.csv, account_17_candles.csv, account_18_candles.csv, chop_trend.png, transition.png, reg_vol_sliders.png, ORB_1-1.png, ORB_2-1.png

---

## Next Steps

- **Blog posts** — Upload regime post via editor (This Week on marketing board). Then write remaining 4 posts from backlog prompts.
- **X (Twitter)** — Start posting: screenshots, data findings, hot takes on practice/sim trading. No gatekeeping, no mods.
- **AlternativeTo** — Submit once 7-day age hits.
- **Google Ads** — Set up targeting for long-tail keywords ("futures trading simulator free", "practice day trading"). $50/mo budget.
- **Re-run account 18** — 25 fresh sessions with 2:1 ORB for clean comparison data.
- **Remaining features:** Chart Designer tick_value/margin fields for custom chars, partial position exits (peel off).
- **Tooltip audit** — Replace ALL remaining `title=""` attributes with `data-tip`.
- **See marketing board + /feature-ideas** for full roadmap

---

## Contact / Repo

- GitHub: https://github.com/dvln811/PatternFoundry
- Reference (read-only): /media/devlyn/Leviathan/Projects/StrategyScreener
- Owner: Devlyn Napoli (devlynnapoli@protonmail.com)
