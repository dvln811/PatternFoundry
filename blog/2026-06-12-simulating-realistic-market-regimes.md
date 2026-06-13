---
title: Simulating Realistic Market Regimes
date: 2026-06-12
author: PatternFoundry Engineering
excerpt: How we generate price sessions that feel like real markets instead of random noise.
---

Anyone who has tried to simulate market data knows the problem: a random walk looks nothing like a real chart. Real markets have structure. They trend, they chop, they consolidate, they break out. A naive stochastic process gives you Brownian motion, which has none of these characteristics.

This is the core engineering challenge behind PatternFoundry's session generator. We need price data that is statistically unique every time (so you cannot memorize the chart) but structurally realistic (so the skills you practice actually transfer to live trading).

## The Regime Problem

Real intraday price action moves through distinct behavioral modes:

- **Trend** - Directional movement with shallow pullbacks
- **Mean reversion** - Price oscillates around a level, each push away gets sold back
- **Breakout** - Compression followed by a rapid directional move
- **Fade** - A false breakout that traps one side and reverses

These modes don't follow a fixed schedule. A trending morning can become a choppy afternoon. A breakout can fail immediately. The transitions are what make markets hard to trade, and they are what a simulator needs to reproduce.

## Regime Switching with Random Durations

Our approach uses a regime state machine. At any point in the session, the generator is in one of several modes, each with its own parameter set for volatility, drift, and mean-reversion strength.

The key insight: regime durations should **not** be fixed. A fixed "trend for 30 bars then chop for 20 bars" pattern becomes learnable after a few sessions. Instead, we use a geometric distribution for regime duration. Each bar, there is a small probability of switching to a new regime. This means some trends last 10 bars and some last 80, which matches what you see in live markets.

```
duration ~ Geometric(p_switch)
```

The switch probability itself varies by regime type. Trends tend to persist longer than chop, which matches empirical observations of market microstructure.

## Avoiding Predictable Structure

Early versions of our generator had a subtle problem: sessions felt "scripted." Traders would notice that the big move always came at the same time, or that the morning was always choppy. This happened because we were using deterministic transition schedules.

The fix was threefold:

1. **Randomized starting regime** - Sessions can begin in any state, not always "opening range"
2. **Geometric duration distribution** - No fixed bar counts for any regime
3. **Removed time-of-day coupling** - Regime switches are not tied to clock time

The result is sessions where the structural behavior is realistic but unpredictable. You cannot learn to "wait for the 11am breakout" because it might come at 10:15 or 2:30 or not at all.

## Session Structure vs. Price Generation

We separate two concerns: macro session structure (when are the regimes, how does volatility envelope the day) and micro price generation (given a regime, what do individual candles look like).

The session structure layer handles:
- Pre-market vs. regular trading hours dampening
- Overnight gap placement
- Volatility scaling across the day

The price generation layer handles:
- OHLC candle construction within the current regime
- Wick ratios and body sizes appropriate to the regime
- Volume correlation with price movement

This separation means we can tune realism at both levels independently. If candles look right but the day structure feels off, we adjust the session layer without touching price generation.

## What This Means for Practice

The goal is not to predict real markets. It is to give traders an environment where their pattern recognition and execution skills get genuine exercise. A session should feel like "a plausible day in ES" without being any specific historical day.

When the regime transitions are properly randomized, traders cannot shortcut the practice. They have to actually read the tape, identify what mode the market is in, and adapt. That is the skill that transfers to live trading.
