"""
tick_engine.py — Agent-based market microstructure tick generator (v2).

Simulates realistic intraday price action via:
- Simulated limit order book with bid/ask depth
- 4 agent types: Market Makers, Institutional, Retail, Momentum
- Hawkes-style self-exciting order flow (trades cluster in time)
- Price impact from order flow imbalance
- Liquidity pools (support/resistance magnets)
- Mean-reversion at micro scale, trending at macro scale

Replaces the simple waypoint interpolation in generate_tick_path().
"""
import numpy as np
from dataclasses import dataclass, field


@dataclass
class MicroConfig:
    """Tunable parameters for the microstructure simulation."""
    tick_size: float = 0.25
    seconds_per_candle: int = 60

    # LOB shape
    lob_levels: int = 10              # depth levels each side
    lob_base_size: int = 50           # base lots per level
    lob_size_decay: float = 0.85      # size decays away from mid

    # Agent mix (probabilities per second of acting)
    mm_rate: float = 0.3              # market maker refresh rate
    inst_rate: float = 0.02           # institutional order rate
    retail_rate: float = 0.08         # retail noise rate
    momentum_rate: float = 0.04       # momentum chaser rate

    # Institutional behavior
    inst_size_min: int = 20
    inst_size_max: int = 200
    inst_persistence: float = 0.92    # probability of continuing same direction

    # Hawkes self-excitation
    hawkes_base: float = 0.15         # base intensity
    hawkes_alpha: float = 0.6         # excitation jump per event
    hawkes_beta: float = 3.0          # decay rate

    # Liquidity pools
    pool_strength: float = 0.3        # attraction toward pools
    pool_count: int = 3               # number of S/R levels per session

    # Micro mean-reversion
    mean_rev_strength: float = 0.002  # pull toward VWAP

    # Spread dynamics
    spread_base: float = 1.0          # in ticks
    spread_vol_mult: float = 2.0      # widens with volatility


# Per-instrument microstructure defaults
MICRO_DEFAULTS = {
    'ES': MicroConfig(
        tick_size=0.25, spread_base=1.0, spread_vol_mult=1.5,
        inst_rate=0.015, inst_size_min=10, inst_size_max=80, inst_persistence=0.90,
        retail_rate=0.06, momentum_rate=0.03,
        hawkes_base=0.12, hawkes_alpha=0.4, hawkes_beta=3.5,
        pool_strength=0.25, pool_count=3, mean_rev_strength=0.003,
    ),
    'NQ': MicroConfig(
        tick_size=0.25, spread_base=1.0, spread_vol_mult=2.0,
        inst_rate=0.025, inst_size_min=15, inst_size_max=150, inst_persistence=0.88,
        retail_rate=0.08, momentum_rate=0.06,
        hawkes_base=0.18, hawkes_alpha=0.7, hawkes_beta=2.5,
        pool_strength=0.30, pool_count=4, mean_rev_strength=0.002,
    ),
    'SPY': MicroConfig(
        tick_size=0.01, spread_base=1.0, spread_vol_mult=1.0,
        inst_rate=0.01, inst_size_min=50, inst_size_max=500, inst_persistence=0.93,
        retail_rate=0.10, momentum_rate=0.02,
        hawkes_base=0.10, hawkes_alpha=0.3, hawkes_beta=4.0,
        pool_strength=0.20, pool_count=2, mean_rev_strength=0.004,
    ),
    'TSLA': MicroConfig(
        tick_size=0.01, spread_base=2.0, spread_vol_mult=3.0,
        inst_rate=0.03, inst_size_min=20, inst_size_max=200, inst_persistence=0.94,
        retail_rate=0.12, momentum_rate=0.07,
        hawkes_base=0.20, hawkes_alpha=0.8, hawkes_beta=2.0,
        pool_strength=0.35, pool_count=5, mean_rev_strength=0.001,
    ),
    'GME': MicroConfig(
        tick_size=0.01, spread_base=3.0, spread_vol_mult=4.0,
        inst_rate=0.01, inst_size_min=10, inst_size_max=100, inst_persistence=0.70,
        retail_rate=0.20, momentum_rate=0.10,
        hawkes_base=0.25, hawkes_alpha=1.0, hawkes_beta=1.5,
        pool_strength=0.40, pool_count=4, mean_rev_strength=0.001,
    ),
    'CL': MicroConfig(
        tick_size=0.01, spread_base=1.5, spread_vol_mult=2.5,
        inst_rate=0.02, inst_size_min=10, inst_size_max=100, inst_persistence=0.85,
        retail_rate=0.05, momentum_rate=0.04,
        hawkes_base=0.14, hawkes_alpha=0.5, hawkes_beta=3.0,
        pool_strength=0.30, pool_count=3, mean_rev_strength=0.003,
    ),
}


def generate_microstructure_ticks(candles: list, config: MicroConfig = None) -> list:
    """
    Given a list of OHLCV candle dicts (from simulate_session_candles),
    generate second-by-second ticks with realistic microstructure.

    Returns list of {time, price, volume, bid, ask, imbalance}.
    """
    if config is None:
        config = MicroConfig()

    tick = config.tick_size
    spc = config.seconds_per_candle
    snap = lambda p: round(round(p / tick) * tick, 6)

    all_ticks = []
    rng = np.random.default_rng()

    # Session-level liquidity pools (S/R levels)
    prices_arr = np.array([c['open'] for c in candles] + [candles[-1]['close']])
    price_range = prices_arr.max() - prices_arr.min()
    mid_price = (prices_arr.max() + prices_arr.min()) / 2
    pools = mid_price + rng.uniform(-0.4, 0.4, config.pool_count) * price_range

    # Institutional state
    inst_direction = rng.choice([-1, 1])
    inst_remaining = 0

    # Hawkes intensity state
    hawkes_intensity = config.hawkes_base

    # Running VWAP for mean-reversion
    cum_pv = 0.0
    cum_vol = 0

    for ci, candle in enumerate(candles):
        o, h, l, c = candle['open'], candle['high'], candle['low'], candle['close']
        vol = candle.get('volume', 500)
        base_ts = candle['time'] if isinstance(candle.get('time'), int) else int(candle['Timestamp'].timestamp())

        # Target: price must go from O to C, touching H and L
        # We simulate freely but constrain endpoints
        price = o
        candle_ticks = []

        # Determine when H and L are hit
        bullish = c >= o
        if bullish:
            low_frac = rng.uniform(0.1, 0.4)
            high_frac = rng.uniform(max(low_frac + 0.1, 0.5), 0.9)
        else:
            high_frac = rng.uniform(0.1, 0.4)
            low_frac = rng.uniform(max(high_frac + 0.1, 0.5), 0.9)

        low_sec = int(low_frac * spc)
        high_sec = int(high_frac * spc)

        # Build LOB state
        spread = max(tick, tick * config.spread_base)
        bid = snap(price - spread / 2)
        ask = snap(price + spread / 2)

        # Per-second simulation
        vol_per_sec = max(1, vol // spc)
        order_imbalance = 0.0

        for s in range(spc):
            t = base_ts + s
            frac = s / spc

            # Target price for this second (smooth path toward waypoints)
            if bullish:
                if s <= low_sec:
                    target = o + (l - o) * (s / max(low_sec, 1))
                elif s <= high_sec:
                    target = l + (h - l) * ((s - low_sec) / max(high_sec - low_sec, 1))
                else:
                    target = h + (c - h) * ((s - high_sec) / max(spc - high_sec, 1))
            else:
                if s <= high_sec:
                    target = o + (h - o) * (s / max(high_sec, 1))
                elif s <= low_sec:
                    target = h + (l - h) * ((s - high_sec) / max(low_sec - high_sec, 1))
                else:
                    target = l + (c - l) * ((s - low_sec) / max(spc - low_sec, 1))

            # --- Agent actions ---

            # Hawkes decay
            hawkes_intensity = config.hawkes_base + (hawkes_intensity - config.hawkes_base) * np.exp(-config.hawkes_beta / spc)

            # Market maker: tighten/widen spread based on volatility
            local_vol = abs(price - target) / (price + 1e-8)
            spread = tick * config.spread_base * (1 + config.spread_vol_mult * local_vol * 100)
            spread = max(tick, min(spread, tick * 8))

            # Institutional flow
            if inst_remaining > 0:
                inst_remaining -= 1
                order_imbalance += inst_direction * rng.uniform(0.5, 1.5)
                hawkes_intensity += config.hawkes_alpha * 0.3
            elif rng.random() < config.inst_rate / spc:
                # New institutional order
                if rng.random() < config.inst_persistence:
                    pass  # keep direction
                else:
                    inst_direction *= -1
                inst_remaining = rng.integers(config.inst_size_min, config.inst_size_max)
                order_imbalance += inst_direction * 2.0
                hawkes_intensity += config.hawkes_alpha

            # Retail noise
            if rng.random() < config.retail_rate * hawkes_intensity:
                retail_dir = rng.choice([-1, 1])
                order_imbalance += retail_dir * rng.uniform(0.2, 0.8)
                hawkes_intensity += config.hawkes_alpha * 0.1

            # Momentum chasers (follow recent direction)
            if rng.random() < config.momentum_rate / spc and len(candle_ticks) > 5:
                recent = [ct['price'] for ct in candle_ticks[-5:]]
                mom_dir = 1 if recent[-1] > recent[0] else -1
                order_imbalance += mom_dir * rng.uniform(0.3, 1.0)
                hawkes_intensity += config.hawkes_alpha * 0.2

            # --- Price formation ---

            # Base move: toward target (ensures OHLC constraint)
            target_pull = (target - price) * 0.15

            # Order flow impact
            impact = order_imbalance * tick * 0.05

            # Liquidity pool attraction
            pool_pull = 0.0
            for pool in pools:
                dist = pool - price
                if abs(dist) < price_range * 0.1:
                    pool_pull += config.pool_strength * dist * tick / (abs(dist) + tick)

            # VWAP mean-reversion
            vwap = cum_pv / max(cum_vol, 1)
            mr_pull = config.mean_rev_strength * (vwap - price) if cum_vol > 0 else 0

            # Noise
            noise = rng.normal(0, tick * 0.3)

            # Combine
            dp = target_pull + impact + pool_pull * 0.01 + mr_pull + noise
            price = snap(price + dp)

            # Clamp to candle range
            price = max(l, min(h, price))

            # Update LOB
            bid = snap(price - spread / 2)
            ask = snap(price + spread / 2)

            # Volume for this tick
            vol_mult = 1.0 + hawkes_intensity
            if frac < 0.1 or frac > 0.9:
                vol_mult *= 1.8  # U-shaped volume
            tick_vol = max(1, int(vol_per_sec * vol_mult * rng.uniform(0.5, 1.5)))

            # Update VWAP
            cum_pv += price * tick_vol
            cum_vol += tick_vol

            # Decay order imbalance
            order_imbalance *= 0.85

            candle_ticks.append({
                'time': t,
                'price': float(price),
                'volume': tick_vol,
                'bid': float(bid),
                'ask': float(ask),
                'imbalance': round(float(order_imbalance), 2),
            })

        # Force last tick to close price
        if candle_ticks:
            candle_ticks[-1]['price'] = float(snap(c))

        all_ticks.extend(candle_ticks)

    return all_ticks


def generate_tick_path_v2(ohlc_df, tick_size=0.25, seconds_per_candle=60, config=None):
    """
    Drop-in replacement for data_generator.generate_tick_path().
    Uses agent-based microstructure simulation.

    Input: DataFrame with Open, High, Low, Close, Volume, Timestamp columns.
    Output: list of {time, price, volume} dicts (compatible with existing frontend).
    """
    if config is None:
        config = MicroConfig(tick_size=tick_size, seconds_per_candle=seconds_per_candle)

    candles = []
    for _, row in ohlc_df.iterrows():
        candles.append({
            'time': int(row['Timestamp'].timestamp()),
            'open': float(row['Open']),
            'high': float(row['High']),
            'low': float(row['Low']),
            'close': float(row['Close']),
            'volume': int(row['Volume']),
        })

    raw_ticks = generate_microstructure_ticks(candles, config)

    # Return simplified format for frontend compatibility
    return [{'time': t['time'], 'price': t['price'], 'volume': t['volume']} for t in raw_ticks]
