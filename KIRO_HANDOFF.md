# Kiro Handoff - PatternFoundry Rebuild

## What This Is

PatternFoundry is a **clean-room rebuild** of a trading simulator concept.
It is being built from scratch, on personal time and resources, by Devlyn Napoli.

**Do not copy code from the reference repo.** Use it only to understand
what was built before - architecture, UI patterns, feature behavior - then
rewrite everything from scratch in this repo.

---

## Reference Repo (READ ONLY - do not copy code)

```
/media/devlyn/Leviathan/Projects/StrategyScreener
```

**The rule:** Understand the behavior, rewrite the implementation.

---

## Current State (as of 2026-06-03)

### Deployed & Live
- **Site:** https://patternfoundry.net (Fly.io, auto-deploys from GitHub on push to main)
- **Repo:** https://github.com/dvln811/PatternFoundry
- **Branch:** main
- **Auth:** Flask-Login + bcrypt, SQLite on persistent volume (`/data/users.db`)
- **Local dev:** `PF_LOCAL=1` skips auth (default)

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
| `/settings` | `settings.html` | Trading account settings (balance, reset) |
| `/docs` | `docs.html` | Documentation hub |
| `/docs/<section>` | `docs_*.html` | 7 doc sub-pages (getting-started, simulator, designer, indicators, orderbook, pricing, ironman) |
| `/login` | `auth_login.html` | Login |
| `/register` | `auth_register.html` | Registration |
| `/feedback` | `feedback.html` | User feedback form |
| `/admin` | `admin_hub.html` | Admin hub (Users, Feedback, Board, Marketing, Stats, Feature Ideas) |
| `/admin/users` | `admin_users.html` | User management |
| `/admin/feedback` | `admin_feedback.html` | View feedback submissions |
| `/board` | `board.html` | Kanban board (auto-syncs to server on Fly) |
| `/marketing` | `marketing.html` | Marketing plan |
| `/feature-ideas` | `feature_ideas.html` | Design docs for upcoming features |
| `/landing` | `landing.html` | Landing page preview (dev) |

### Key Features Working
- **Simulator:** Session generation, tick playback (0.25x-200x), trade execution (market/limit/stop-limit), draggable SL/TP, DOM with real order book, indicators (7 built-in + custom scripting), drawing tools (11 types + text + right-click property editor), session save/load, multi-timeframe, Close Session button (simulates remaining ticks), **persistent account balance** (rolls forward), **per-instrument commission** (1 tick/contract auto-scaled), **risk % display** in position window
- **Session Replay:** (`/simulator?replay=<id>`) Full simulator in review mode — loads stored session candles + regenerated history, buy/sell arrow markers, trade log populated, TF switching, indicators, drawing tools, drawings restored, loading overlay, Reset View + Close Review buttons. Sidebar trade/account/position/sessions panels hidden.
- **Trading Accounts:** Server-side persistent accounts with rolling balance, account reset (archives old + starts fresh), per-account session linking
- **Chart Designer:** CharacterSpec + MicroConfig sliders with help tooltips, generate + preview, tick engine glass-box view (play/pause, bid/ask/imbalance/hawkes/inst state), save custom characters
- **Custom Indicators:** Script editor with syntax highlighting, multi-line return support, `align()` helper, save/load, add from dropdown, legend with hide/edit period/remove
- **Dashboard:** Live Yahoo Finance tickers (5s refresh), chart, news feed, ticker add/remove
- **Auth:** Login/register/logout, first user = admin, avatar chip with dropdown
- **Admin:** Hub page, user management (ban/promote), feedback viewer, board, marketing, stats, feature ideas
- **Stats Page:** Account selector (active + archived), per-account stats cards, per-account equity curve (Chart.js line), aggregated equity curve (all accounts), scrollable session history with sticky header + replay links (▶), practice streak + calendar heatmap (with explanation label), Iron Man mode panel, purge archived accounts
- **Iron Man Mode:** Full simulator integration — auto-detects active run on simulator load, disables instrument selection (random built-in only), locks history to 3 months, uses Iron Man balance, auto-submits session on close, shows 🔥 badge, notifies on target/drawdown end. Server-side persistence (SQLite), start/forfeit/session-complete/status API, active run display with balance/days/drawdown/progress bar, past attempts history.
- **Session Persistence:** Per-trade data stored (direction, qty, entry/exit price+time, pnl, exit reason). Session candles (1-min OHLCV) stored. Session metadata (seed, hist_days, tick_size, tick_value) stored for procedural history regeneration. Drawings stored and restored on replay. Remaining ticks simulated on close for full session chart.
- **Board:** Kanban with drag-drop, auto-saves to server on Fly, upload/download sync buttons for local dev
- **Landing:** Hero + animated chart bg, comparison table, pricing tiers (faded) + early access card, screenshot lightbox, **OG/meta tags for social sharing**
- **Settings Page:** Trading account balance configuration, reset account button (commission removed — now auto-scaled)
- **SEO:** robots.txt (blocks internal pages, allows sitemap+robots publicly), sitemap.xml (landing + docs), meta/OG/Twitter tags, submitted to Google Search Console (pending indexing)
- **Deployment:** Dockerfile + fly.toml + GitHub Actions CI
- **Header Nav:** Consistent across all pages (Dashboard, Simulator, Chart Designer, Stats, Settings, Docs, Admin, avatar chip)
- **Button Style:** All buttons site-wide use border + text color on black/transparent field (no filled backgrounds)

### Data Generation Pipeline
1. `generators/` - v2 vectorized: CharacterSpec -> 9-stage pipeline -> session structure
2. `data_generator.py` - Legacy: simulate_session_candles (per-candle FVG state) + generate_tick_path (waypoint interpolation)
3. `tick_engine.py` - Microstructure: 4 agent types, Hawkes clustering, order book, liquidity pools
4. `order_book.py` - Simulated LOB: market maker refresh, institutional eating, retail noise
5. `/api/sim-session` - Combines history (5-min) + pre-market + RTH session + tick paths

### Per-Instrument Configuration
| Instrument | Tick Size | Tick Value | Commission (1 tick) |
|---|---|---|---|
| ES | 0.25 | $12.50 | $12.50/contract |
| NQ | 0.25 | $5.00 | $5.00/contract |
| CL | 0.01 | $10.00 | $10.00/contract |
| SPY | 0.01 | $1.00 | $1.00/share |
| TSLA | 0.01 | $1.00 | $1.00/share |
| GME | 0.01 | $1.00 | $1.00/share |

- `tick_value` stored in `CharacterSpec` (generators/spec.py field, generators/characters.py per-instrument)
- Commission = `tickValue * qty` (1 tick per contract round-trip, calculated client-side in closeTrade)
- Custom characters default to tick_value=12.50 if not specified in JSON

### Trading Account System
- **Table:** `trading_accounts` (user_id, starting_balance, balance, commission_per_contract, status, created_at, archived_at)
- **Behavior:** One active account per user. Balance rolls forward session to session. Commission field still in DB but no longer used (auto-scaled per instrument). Reset archives current and creates new.
- **Sessions table:** `sessions` (user_id, date, character, trades, wins, pnl, account_id, seed, hist_days, tick_size, tick_value, candles, drawings)
- **Trades table:** `trades` (session_id, direction, qty, entry_price, entry_time, exit_price, exit_time, pnl, exit_reason)
- **API:**
  - `GET /api/account` — get active account (auto-creates with $50k default if none)
  - `POST /api/account` — update balance
  - `POST /api/account/reset` — archive current, create new
  - `POST /api/account/update-balance` — persist balance after session
  - `GET /api/account/archived` — list archived accounts
  - `GET /api/account/<id>/sessions` — sessions for a specific account
  - `POST /api/account/purge-archived` — permanently delete archived accounts + their sessions + orphan NULL sessions
  - `GET /api/sessions` — all sessions (includes session id for replay links)
  - `GET /api/sessions?account_id=X` — sessions for specific account
  - `GET /api/sessions/<id>` — session detail (candles, trades, drawings, metadata for replay)
  - `POST /api/sessions` — save session (candles, trade_list, drawings, seed, hist_days, tick_size, tick_value)

### Iron Man Mode (Server-Side + Simulator Integration)
- **Tables:** `ironman_runs` (user, attempt, status, balance, peak, target/drawdown limits, day count) + `ironman_sessions` (day, character, seed, trades, wins, pnl, balance after)
- **API:**
  - `GET /api/ironman/status` - active run or history
  - `POST /api/ironman/start` - begin challenge
  - `POST /api/ironman/session-complete` - submit session (auto-checks drawdown/target)
  - `POST /api/ironman/forfeit` - end run voluntarily
- **End conditions:** drawdown breach (-20% from peak) or target reached (+10%)
- **Simulator integration:**
  - On load: checks `/api/ironman/status`, if active → enters Iron Man mode
  - Iron Man mode: 🔥 badge shown, instrument dropdown disabled (random built-in selected), history locked to 3 months (63 days), uses Iron Man run balance
  - On session close: auto-submits to `/api/ironman/session-complete`
  - On run end: badge hidden, dropdowns re-enabled, end message shown
- **Docs:** Full documentation page at `/docs/ironman`

### Session Replay System
- **Storage:** Session candles (1-min OHLCV JSON), per-trade data (trades table), drawings (JSON), metadata (seed, hist_days, tick_size, tick_value)
- **On close:** Remaining ticks simulated to completion, 1-min candles built from all ticks, drawings captured, everything POSTed to `/api/sessions`
- **Review mode:** `/simulator?replay=<session_id>` — detected via `REVIEW_MODE` const from query param
  - Loads session detail from `/api/sessions/<id>`
  - Regenerates historical candles from seed/instrument/hist_days via `/api/sim-session` call
  - Combines history + stored session candles
  - Sets up `window._historyBars`, `window._reviewSessionCandles`, `window._chartData`, `allTicks` for TF switching
  - Renders buy/sell arrow markers on chart
  - Restores drawings via `drawMgr.fromJSON()`
  - Populates trade log panel
  - Hides: sec-session, sec-account, sec-trade, sec-position, sec-sessions
  - Shows: Close Review button, Reset View button, loading overlay during load
  - TF switching uses `_reviewSessionCandles` directly (not synthetic ticks)
  - Indicators work since `window._chartData` is populated

### Board Sync
- **Server-side:** `/api/board/save` + `/api/board/load` with `X-Board-Key` auth
- **On Fly:** auto-saves every change, auto-loads from server on page load
- **Local:** manual Upload/Download buttons, key set via `BOARD_API_KEY` env var
- **Secret:** `BOARD_API_KEY` set on Fly.io (also in `restart_server.sh` for local dev)
- **CORS:** after_request handler adds headers for `/api/board*` paths

### Known Issues / TODO
- Off-hours background shading (LWC limitation - partially working)
- Google Search Console sitemap submission pending (may take 24-48hrs to index)
- Per-account stats on Stats page could have more granular views
- See `/feature-ideas` page for comprehensive roadmap

### Pricing Model (not yet enforced)
- Free: 3 sessions/day, ES only, 1 week history, basic tools
- Practice ($9.99/mo): Unlimited, all instruments, 6mo history, all tools
- Edge ($19.99/mo): Custom instruments, custom indicators, 2yr history, tick engine preview
- Currently: Early Access - all features free

---

## How to Start a Session

1. Read this file
2. Check `git log --oneline -5` to see recent work
3. Check `git status` for any in-progress changes
4. Run `bash restart_server.sh` to start the server (includes BOARD_API_KEY)
5. Ask the user what they want to work on

---

## Key Files

| File | Purpose |
|------|---------|
| `app.py` | Flask routes + API endpoints (auth, board, Iron Man, accounts, sessions, sim, designer) |
| `models.py` | User model + Iron Man + trading accounts + sessions + trades (SQLite + bcrypt) |
| `generators/spec.py` | CharacterSpec dataclass (includes tick_value field) |
| `generators/characters.py` | 6 built-in instruments with per-instrument tick/tick_value |
| `generators/` | v2 data generation (spec, characters, engines, orchestrator, sessions) |
| `data_generator.py` | Legacy generator + tick path decomposition |
| `tick_engine.py` | Agent-based microstructure tick simulation |
| `order_book.py` | Simulated limit order book |
| `static/indicators.js` | Client-side indicator math (7 indicators) |
| `static/custom-indicator.js` | Custom indicator execution engine + helpers |
| `static/canvas-overlay.js` | Drawing tools (14 types + text + property editor), `fromJSON()` for restore |
| `static/robots.txt` | SEO - crawler directives |
| `static/sitemap.xml` | SEO - page index for search engines |
| `templates/chart.html` | Simulator SPA (~2100 lines) — includes REVIEW_MODE, Iron Man integration, session save with candles/trades/drawings |
| `templates/chartdesigner.html` | Chart Designer SPA |
| `templates/dashboard.html` | Dashboard with live tickers |
| `templates/stats.html` | Stats + account selector + equity curves + Iron Man + replay links |
| `templates/settings.html` | Trading account balance configuration |
| `templates/docs_ironman.html` | Iron Man Mode documentation |
| `templates/feature_ideas.html` | Feature design docs |
| `templates/board.html` | Kanban board with sync |
| `templates/landing.html` | Public landing page (with SEO meta/OG tags) |
| `restart_server.sh` | Local dev server launcher (sets BOARD_API_KEY) |
| `fly.toml` | Fly.io deployment config |
| `.github/workflows/fly.yml` | GitHub Actions auto-deploy |
| `docs/` | Internal design docs (account tracking, simulator fixes, tick engine) |

---

## Environment

- **Fly secrets:** `BOARD_API_KEY` (for board sync auth)
- **Fly env:** `PF_LOCAL=0`, `PF_DB_PATH=/data/users.db`
- **Local:** `PF_LOCAL=1` (default, skips auth), `BOARD_API_KEY` set in restart_server.sh
- **Persistent volume:** `/data/` on Fly (users.db, boards/)
- **Public paths (no auth required):** `/login`, `/register`, `/static`, `/api/`, `/robots.txt`, `/sitemap.xml`

---

## Recent Work (2026-06-02 / 2026-06-03 sessions)

### Session 1 (2026-06-02)
1. Replaced LWC equity curve on Stats page with Chart.js line chart
2. Migrated session history from localStorage to server-side SQLite
3. Built persistent trading accounts (rolling balance, per-contract commission, archive/reset)
4. Created Settings page for account configuration
5. Redesigned Stats page (streak at top, account selector, dual equity curves, scrollable history, labeled heatmap)
6. Added risk % of account to position window in simulator
7. Fixed all button styles site-wide (border+text on black, no filled backgrounds)
8. Added basic SEO (meta/OG tags, robots.txt, sitemap.xml)

### Session 2 (2026-06-02 evening + 2026-06-03 morning)
1. Fixed robots.txt/sitemap.xml blocked by auth (added to public paths)
2. Submitted sitemap to Google Search Console (pending — GSC slow to index)
3. **Iron Man simulator integration** — auto-detect active run, random built-in instrument, auto-submit on close, 🔥 badge, disable character/history selection
4. Added Iron Man documentation page (`/docs/ironman`) + card on docs hub
5. Limited Iron Man random selection to built-in instruments only
6. Renamed "Character" → "Instrument" across stats/session UI
7. **Session Replay system** — per-trade persistence (trades table), session candle storage, simulate remaining ticks on close, replay viewer via `/simulator?replay=<id>`
8. Refactored replay to reuse full simulator (TF switching, indicators, drawings, crosshair all work)
9. Fixed review mode: TF switching, history regeneration, indicators, trade log, hide panels
10. Added loading overlay ("Restoring session…") during replay load
11. Save + restore drawings on session close/replay
12. Locked Iron Man history to 3 months (63 days)
13. **Fixed commission/tick_value bug** — added per-instrument `tick_value` to CharacterSpec (ES=$12.50, NQ=$5.00, CL=$10.00, stocks=$1.00), commission now auto-scales to 1 tick per contract
14. Removed commission field from Settings page (no longer user-configurable)

---

## Next Steps

- **Stats enhancements:** Profit factor, avg win/loss, largest win/loss, max consecutive, per-instrument breakdown, monthly P&L bar chart, drawdown chart, win rate over time, P&L distribution histogram
- **Chart Designer tick_value:** Add tick_value field to designer UI so custom characters get proper P&L calculation
- **Marketing:** Reddit/Discord presence, short demo video
- **Commission model expansion:** When needed — per-share fees for stocks, $0 commission option
- **Session history:** More detailed review — per-trade annotations, journal notes
- **Google Search Console:** Check back for sitemap indexing status
- **See board + /feature-ideas** for full roadmap

---

## Contact / Repo

- GitHub: https://github.com/dvln811/PatternFoundry
- Reference (read-only): /media/devlyn/Leviathan/Projects/StrategyScreener
- Owner: Devlyn Napoli (devlynnapoli@protonmail.com)
