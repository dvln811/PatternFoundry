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

## Current State (as of 2026-06-02)

### Deployed & Live
- **Site:** https://patternfoundry.net (Fly.io, auto-deploys from GitHub on push to main)
- **Repo:** https://github.com/dvln811/PatternFoundry
- **Branch:** main
- **Auth:** Flask-Login + bcrypt, SQLite on persistent volume (`/data/users.db`)
- **Local dev:** `PF_LOCAL=1` skips auth (default)

### Architecture
- **Backend:** Python/Flask, gunicorn in production
- **Frontend:** Vanilla JS, LightweightCharts v4.2
- **Data generation:** `generators/` package (v2 vectorized pipeline) + `data_generator.py` (legacy tick paths)
- **Tick engine:** `tick_engine.py` (agent-based microstructure) + `order_book.py` (simulated LOB)
- **User model:** `models.py` (SQLite, bcrypt, Flask-Login, Iron Man tables)
- **Deployment:** Dockerfile + fly.toml + GitHub Actions CI (push to main = auto-deploy)

### Pages Built
| Route | Template | Purpose |
|-------|----------|---------|
| `/` | `landing.html` (unauth) / `dashboard.html` (auth) | Landing page / Dashboard |
| `/simulator` | `chart.html` | Live trading simulator |
| `/chartdesigner` | `chartdesigner.html` | Instrument designer + tick engine preview |
| `/stats` | `stats.html` | Performance stats, equity curve, streaks, Iron Man |
| `/docs` | `docs.html` | Documentation hub |
| `/docs/<section>` | `docs_*.html` | 6 doc sub-pages |
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
- **Simulator:** Session generation, tick playback (0.25x-200x), trade execution (market/limit/stop-limit), draggable SL/TP, DOM with real order book, indicators (7 built-in + custom scripting), drawing tools (11 types + text + right-click property editor), session save/load, multi-timeframe, **Close Session button** (records stats, disables play/trading)
- **Chart Designer:** CharacterSpec + MicroConfig sliders with help tooltips, generate + preview, tick engine glass-box view (play/pause, bid/ask/imbalance/hawkes/inst state), save custom characters
- **Custom Indicators:** Script editor with syntax highlighting, multi-line return support, `align()` helper, save/load, add from dropdown, legend with hide/edit period/remove
- **Dashboard:** Live Yahoo Finance tickers (5s refresh), chart, news feed, ticker add/remove
- **Auth:** Login/register/logout, first user = admin, avatar chip with dropdown
- **Admin:** Hub page, user management (ban/promote), feedback viewer, board, marketing, stats, feature ideas
- **Stats Page:** Session history table, equity curve (LWC area chart), practice streak + calendar heatmap, Iron Man mode panel
- **Iron Man Mode:** Server-side persistence (SQLite), start/forfeit/session-complete/status API, active run display with balance/days/drawdown/progress bar, past attempts history
- **Board:** Kanban with drag-drop, auto-saves to server on Fly, upload/download sync buttons for local dev
- **Landing:** Hero + animated chart bg, comparison table, pricing tiers (faded) + early access card, screenshot lightbox
- **Deployment:** Dockerfile + fly.toml + GitHub Actions CI
- **Header Nav:** Consistent across all 16+ pages (Dashboard, Simulator, Chart Designer, Stats, Docs, Admin, Feedback, avatar chip)

### Data Generation Pipeline
1. `generators/` - v2 vectorized: CharacterSpec -> 9-stage pipeline -> session structure
2. `data_generator.py` - Legacy: simulate_session_candles (per-candle FVG state) + generate_tick_path (waypoint interpolation)
3. `tick_engine.py` - Microstructure: 4 agent types, Hawkes clustering, order book, liquidity pools
4. `order_book.py` - Simulated LOB: market maker refresh, institutional eating, retail noise
5. `/api/sim-session` - Combines history (5-min) + pre-market + RTH session + tick paths

### Iron Man Mode (Server-Side)
- **Tables:** `ironman_runs` (user, attempt, status, balance, peak, target/drawdown limits, day count) + `ironman_sessions` (day, character, seed, trades, wins, pnl, balance after)
- **API:**
  - `GET /api/ironman/status` - active run or history
  - `POST /api/ironman/start` - begin challenge
  - `POST /api/ironman/session-complete` - submit session (auto-checks drawdown/target)
  - `POST /api/ironman/forfeit` - end run voluntarily
- **End conditions:** drawdown breach (-20% from peak) or target reached (+10%)
- **TODO:** Wire simulator to auto-detect active run, disable character selection, auto-submit on close. Add configurable starting balance ($5k/$10k/$25k/$50k).

### Session Stats Tracking
- **Close Session button** in simulator playback bar - lets user end session early (hit trade limit, daily loss, etc.)
- On close: stops play, closes open position, saves to `pf_session_history` localStorage, disables play/trading buttons
- On session complete (all ticks): also saves stats
- Guard against double-save with `sessionClosed` flag
- **TODO:** Migrate session history to server-side (SQLite) for cross-device persistence

### Board Sync
- **Server-side:** `/api/board/save` + `/api/board/load` with `X-Board-Key` auth
- **On Fly:** auto-saves every change, auto-loads from server on page load
- **Local:** manual Upload/Download buttons, key set via `BOARD_API_KEY` env var
- **Secret:** `BOARD_API_KEY` set on Fly.io (also in `restart_server.sh` for local dev)
- **CORS:** after_request handler adds headers for `/api/board*` paths

### Known Issues / TODO
- Off-hours background shading (LWC limitation - partially working)
- Account tracking metrics discussion (see `docs/ACCOUNT_TRACKING_DISCUSSION.md`)
- Iron Man simulator integration (auto-detect, random character, auto-submit)
- Session history server-side migration
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
| `app.py` | Flask routes + API endpoints (auth, board, Iron Man, sim, designer) |
| `models.py` | User model + Iron Man tables (SQLite + bcrypt) |
| `generators/` | v2 data generation (spec, characters, engines, orchestrator, sessions) |
| `data_generator.py` | Legacy generator + tick path decomposition |
| `tick_engine.py` | Agent-based microstructure tick simulation |
| `order_book.py` | Simulated limit order book |
| `static/indicators.js` | Client-side indicator math (7 indicators) |
| `static/custom-indicator.js` | Custom indicator execution engine + helpers |
| `static/canvas-overlay.js` | Drawing tools (14 types + text + property editor) |
| `templates/chart.html` | Simulator SPA (~1950 lines) |
| `templates/chartdesigner.html` | Chart Designer SPA |
| `templates/dashboard.html` | Dashboard with live tickers |
| `templates/stats.html` | Stats + Iron Man UI |
| `templates/feature_ideas.html` | Feature design docs |
| `templates/board.html` | Kanban board with sync |
| `templates/landing.html` | Public landing page |
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

---

## Contact / Repo

- GitHub: https://github.com/dvln811/PatternFoundry
- Reference (read-only): /media/devlyn/Leviathan/Projects/StrategyScreener
- Owner: Devlyn Napoli (devlynnapoli@protonmail.com)
