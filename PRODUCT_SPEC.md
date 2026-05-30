# PatternFoundry — Product Spec v1.0

> *Forge your trading edge. Practice live sessions on demand.*

---

## The Problem

Retail traders can't practice the way athletes practice.

- **Replay tools** (TradingSim, Multicharts) replay the same historical tape — you memorize it.
- **Paper trading** is gated to market hours. You can't practice at 9pm.
- **Backtesting** tells you what happened, not how you'd have reacted in the moment.

The result: traders fund live accounts before they're ready, and pay expensive tuition in real losses.

---

## The Product

**PatternFoundry is a live trading simulator that generates fresh, realistic market sessions on demand.**

Every session is synthetic — procedurally generated to feel like a real RTH session — so you never memorize the tape. You can practice at 2am on a Tuesday. You can run the same setup 50 times in an afternoon.

### Core loop

1. **Generate** a fresh session (ES, NQ, GC, CL — configurable)
2. **Trade it live** — price ticks forward in real time, you manage entries/exits
3. **Review** your trades on the completed chart
4. **Repeat** with a new session

### What makes it different

| Feature | PatternFoundry | TradingSim | Paper Trading |
|---|---|---|---|
| Available 24/7 | ✅ | ✅ | ❌ |
| Fresh tape every time | ✅ | ❌ | ✅ |
| Realistic session structure | ✅ | ✅ | ✅ |
| Free to start | ✅ | ❌ | ✅ |
| No brokerage required | ✅ | ✅ | ❌ |

---

## MVP Feature Set

### Chart Designer
- Candlestick chart with configurable timeframe (1m, 5m, 15m)
- Drawing tools: horizontal levels, trend lines, rectangles, FIB
- Indicators: VWAP, EMA, SMA
- Session structure visible (RTH open/close, lunch, power hour)

### Live Simulator
- Price ticks forward at configurable speed (1x, 5x, 10x, real-time)
- Place long/short entries with stop and target
- Drag stop/target lines on the chart
- P&L tracking per trade and per session
- Session save/load

### Session Generation
- Procedurally generated OHLCV data
- Realistic RTH session structure (open volatility, midday chop, close)
- Configurable instrument character (trending, ranging, volatile)
- Seed-deterministic (same seed = same session, for review)

---

## What's NOT in v1

- Pattern scanning (future)
- Monte Carlo simulation (future)
- Multi-timeframe (future)
- Live market data (future)
- Social/leaderboards (never)

---

## Pricing (provisional)

| Tier | Price | Limits |
|---|---|---|
| Free | $0 | 5 sessions/day, 1 instrument |
| Practice | $9/mo | Unlimited sessions, all instruments |
| Edge | $19/mo | + Pattern scanning when available |

---

## Tech Stack

- **Backend:** Python / Flask
- **Frontend:** Vanilla JS, LightweightCharts (TradingView library)
- **Data:** Procedurally generated (no exchange fees, no API keys)
- **Auth:** Flask-Login, email/password, bcrypt
- **Deploy:** Fly.io

---

## North Star Metric

**Sessions completed per week per active user.**

A user who runs 3+ sessions/week is getting real practice value. That's the retention signal that matters.

---

*Spec written 2026-05-30. PatternFoundry is a clean-room rebuild, written from scratch on personal time and resources.*
