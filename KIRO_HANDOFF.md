# Kiro Handoff — PatternFoundry Rebuild

## What This Is

PatternFoundry is a **clean-room rebuild** of a trading simulator concept.
It is being built from scratch, on personal time and resources, by Devlyn Napoli.

**Do not copy code from the reference repo.** Use it only to understand
what was built before — architecture, UI patterns, feature behavior — then
rewrite everything from scratch in this repo.

---

## Reference Repo (READ ONLY — do not copy code)

```
/media/devlyn/Leviathan/Projects/StrategyScreener
```

This is the prior implementation. You may read it to understand:
- How the chart designer and simulator worked
- What the UI looked like (templates/)
- How candle generation worked (data_generator.py, generators/)
- How Flask routes were structured (app.py)

**The rule:** Understand the behavior, rewrite the implementation.

---

## Current State of This Repo

- Fresh repo, no code yet
- GitHub: https://github.com/dvln811/PatternFoundry
- Branch: main

---

## What to Build First

Read `PRODUCT_SPEC.md` in this directory. The MVP is:

1. **Candle generator** — procedural OHLCV, RTH session structure, seed-deterministic
2. **Chart designer** — LightweightCharts, drawing tools, indicators
3. **Live simulator** — tick playback, entry/exit management, P&L tracking
4. **Auth** — Flask-Login, email/password, bcrypt, SQLite
5. **Landing page** — simple, honest, no green screenshots

Start with the candle generator and Flask skeleton. Get a chart rendering
before touching the simulator.

---

## Key Decisions Already Made

- **Stack:** Python/Flask backend, vanilla JS frontend, LightweightCharts
- **No pattern scanner in v1** — simulator only
- **Synthetic data only** — no live market feeds, no API keys needed
- **Deploy target:** Fly.io (same as reference repo)
- **Pricing:** Free (5 sessions/day) / Practice $9/mo / Edge $19/mo

---

## Design Language

- Dark theme: background `#0d0d0d`, surface `#111`, border `#222`
- Accent: orange `#f97316`
- Up candles: `#4caf82`, Down candles: `#ef5350`
- Font: Inter, system-ui fallback
- Logo: orange cauldron (🧪 emoji works as placeholder)

The reference repo has the actual logo at:
`/media/devlyn/Leviathan/Projects/StrategyScreener/static/patternFoundryLogo.png`

You may use this logo — it was created for this product concept.

---

## What NOT to Do

- Do not copy any `.py` files from the reference repo
- Do not copy any `.html` / `.js` files from the reference repo
- Do not copy benchmark fixtures or sketch exports
- Do not reference Transamerica in any commit, comment, or doc
- Do not add pattern scanning until the simulator is solid and shipping

---

## How to Start a Session

1. Read this file
2. Read `PRODUCT_SPEC.md`
3. Check `git log --oneline -10` to see what's been built
4. Check `git status` for any in-progress work
5. Ask the user what they want to work on, or propose the next logical step

---

## Contact / Repo

- GitHub: https://github.com/dvln811/PatternFoundry
- Reference (read-only): https://github.com/dvln811/strategy-screener
- Owner: Devlyn Napoli (devlynnapoli@protonmail.com)
