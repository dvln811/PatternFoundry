"""Pre-built CharacterSpec instances for all instruments."""
from .spec import CharacterSpec, RegimeSpec, DriftSpec, VolatilitySpec, WickSpec, VolumeSpec, GapSpec, EventSpec

# ── E-mini Futures ────────────────────────────────────────────────────────────

# ES: 40-60pt daily range on ~5500 price. Steady, institutional, less impulsive than NQ.
ES_CALM = CharacterSpec(
    name='ES (E-mini S&P)', price_range=(5200, 5800), tick=0.25, tick_value=12.50,
    initial_margin=12980, maintenance_margin=11800,
    regime=RegimeSpec(
        mean_duration={'chop': 30, 'trend_up': 35, 'trend_down': 35, 'impulse': 5, 'gap_hold': 1},
        transition={
            ('chop', 'trend_up'): 0.40, ('chop', 'trend_down'): 0.40, ('chop', 'impulse'): 0.20,
            ('trend_up', 'chop'): 0.35, ('trend_up', 'impulse'): 0.15, ('trend_up', 'trend_down'): 0.50,
            ('trend_down', 'chop'): 0.35, ('trend_down', 'impulse'): 0.15, ('trend_down', 'trend_up'): 0.50,
            ('impulse', 'chop'): 0.6, ('impulse', 'trend_up'): 0.2, ('impulse', 'trend_down'): 0.2,
        },
    ),
    drift=DriftSpec(chop_sigma=0.04, trend_sigma=0.12, trend_magnitude=0.20, impulse_magnitude=1.2, global_bias=0.01),
    volatility=VolatilitySpec(chop=0.8, trend=1.5, impulse=3.5),
    wick=WickSpec(chop_ratio=2.0, trend_ratio=0.5, impulse_ratio=0.3),
    volume=VolumeSpec(base=1000),
    gap=GapSpec(prob=0.0),
    event=EventSpec(wick_stab_prob=0.02),
)

# NQ: 200-400pt daily range on ~20000 price. More volatile, stronger trends, tech-driven momentum.
NQ_ACTIVE = CharacterSpec(
    name='NQ (E-mini Nasdaq)', price_range=(19000, 21000), tick=0.25, tick_value=5.00,
    initial_margin=17600, maintenance_margin=16000,
    regime=RegimeSpec(
        mean_duration={'chop': 20, 'trend_up': 40, 'trend_down': 40, 'impulse': 6, 'gap_hold': 1},
        transition={
            ('chop', 'trend_up'): 0.38, ('chop', 'trend_down'): 0.38, ('chop', 'impulse'): 0.24,
            ('trend_up', 'chop'): 0.30, ('trend_up', 'impulse'): 0.20, ('trend_up', 'trend_down'): 0.50,
            ('trend_down', 'chop'): 0.30, ('trend_down', 'impulse'): 0.20, ('trend_down', 'trend_up'): 0.50,
            ('impulse', 'chop'): 0.5, ('impulse', 'trend_up'): 0.25, ('impulse', 'trend_down'): 0.25,
        },
    ),
    drift=DriftSpec(chop_sigma=0.15, trend_sigma=0.5, trend_magnitude=0.8, impulse_magnitude=4.0, global_bias=0.02),
    volatility=VolatilitySpec(chop=3.0, trend=6.0, impulse=12.0),
    wick=WickSpec(chop_ratio=1.8, trend_ratio=0.6, impulse_ratio=0.3),
    volume=VolumeSpec(base=800),
    gap=GapSpec(prob=0.0),
    event=EventSpec(wick_stab_prob=0.04),
)

# CL: $1.50-$3.00 daily range on ~$75 price. Choppy with sudden impulse moves, news-driven.
CL_CHOPPY = CharacterSpec(
    name='CL (Crude Oil)', price_range=(70, 85), tick=0.01, tick_value=10.00,
    initial_margin=12000, maintenance_margin=10900,
    regime=RegimeSpec(
        mean_duration={'chop': 35, 'trend_up': 25, 'trend_down': 25, 'impulse': 4, 'gap_hold': 1},
        transition={
            ('chop', 'trend_up'): 0.30, ('chop', 'trend_down'): 0.30, ('chop', 'impulse'): 0.40,
            ('trend_up', 'chop'): 0.50, ('trend_up', 'impulse'): 0.30, ('trend_up', 'trend_down'): 0.20,
            ('trend_down', 'chop'): 0.50, ('trend_down', 'impulse'): 0.30, ('trend_down', 'trend_up'): 0.20,
            ('impulse', 'chop'): 0.7, ('impulse', 'trend_up'): 0.15, ('impulse', 'trend_down'): 0.15,
        },
    ),
    drift=DriftSpec(chop_sigma=0.003, trend_sigma=0.008, trend_magnitude=0.012, impulse_magnitude=0.06, global_bias=0.0),
    volatility=VolatilitySpec(chop=0.03, trend=0.06, impulse=0.15),
    wick=WickSpec(chop_ratio=1.5, trend_ratio=0.5, asymmetry=0.15),
    volume=VolumeSpec(base=600),
    gap=GapSpec(prob=0.08, min_size=0.003, max_size=0.015),
    event=EventSpec(wick_stab_prob=0.03),
)

# RTY: 20-40pt daily range on ~2100 price. Choppier than ES, less liquid, wider spreads.
RTY_RUSSELL = CharacterSpec(
    name='RTY (E-mini Russell)', price_range=(2000, 2200), tick=0.10, tick_value=5.00,
    initial_margin=6800, maintenance_margin=6200,
    regime=RegimeSpec(
        mean_duration={'chop': 25, 'trend_up': 30, 'trend_down': 30, 'impulse': 5, 'gap_hold': 1},
        transition={
            ('chop', 'trend_up'): 0.35, ('chop', 'trend_down'): 0.35, ('chop', 'impulse'): 0.30,
            ('trend_up', 'chop'): 0.40, ('trend_up', 'impulse'): 0.20, ('trend_up', 'trend_down'): 0.40,
            ('trend_down', 'chop'): 0.40, ('trend_down', 'impulse'): 0.20, ('trend_down', 'trend_up'): 0.40,
            ('impulse', 'chop'): 0.6, ('impulse', 'trend_up'): 0.2, ('impulse', 'trend_down'): 0.2,
        },
    ),
    drift=DriftSpec(chop_sigma=0.02, trend_sigma=0.06, trend_magnitude=0.09, impulse_magnitude=0.55, global_bias=0.0),
    volatility=VolatilitySpec(chop=0.4, trend=0.85, impulse=2.0),
    wick=WickSpec(chop_ratio=1.8, trend_ratio=0.6, impulse_ratio=0.3),
    volume=VolumeSpec(base=500),
    gap=GapSpec(prob=0.0),
    event=EventSpec(wick_stab_prob=0.03),
)

# ── Micro Futures (same price action as E-mini, different tick value) ─────────

MES_MICRO = CharacterSpec(
    name='MES (Micro S&P)', price_range=(5200, 5800), tick=0.25, tick_value=1.25,
    initial_margin=1265, maintenance_margin=1150,
    regime=ES_CALM.regime, drift=ES_CALM.drift, volatility=ES_CALM.volatility,
    wick=ES_CALM.wick, volume=ES_CALM.volume, gap=ES_CALM.gap, event=ES_CALM.event,
)

MNQ_MICRO = CharacterSpec(
    name='MNQ (Micro Nasdaq)', price_range=(19000, 21000), tick=0.25, tick_value=0.50,
    initial_margin=1760, maintenance_margin=1600,
    regime=NQ_ACTIVE.regime, drift=NQ_ACTIVE.drift, volatility=NQ_ACTIVE.volatility,
    wick=NQ_ACTIVE.wick, volume=NQ_ACTIVE.volume, gap=NQ_ACTIVE.gap, event=NQ_ACTIVE.event,
)

MCL_MICRO = CharacterSpec(
    name='MCL (Micro Crude)', price_range=(70, 85), tick=0.01, tick_value=1.00,
    initial_margin=1200, maintenance_margin=1090,
    regime=CL_CHOPPY.regime, drift=CL_CHOPPY.drift, volatility=CL_CHOPPY.volatility,
    wick=CL_CHOPPY.wick, volume=CL_CHOPPY.volume, gap=CL_CHOPPY.gap, event=CL_CHOPPY.event,
)

M2K_MICRO = CharacterSpec(
    name='M2K (Micro Russell)', price_range=(2000, 2200), tick=0.10, tick_value=0.50,
    initial_margin=680, maintenance_margin=620,
    regime=RTY_RUSSELL.regime, drift=RTY_RUSSELL.drift, volatility=RTY_RUSSELL.volatility,
    wick=RTY_RUSSELL.wick, volume=RTY_RUSSELL.volume, gap=RTY_RUSSELL.gap, event=RTY_RUSSELL.event,
)

# ── Stocks ────────────────────────────────────────────────────────────────────

# SPY: 0.8-1.2% daily range (~$4-6 on $550). Smoothest, tracks ES, institutional flows.
SPY_QUIET = CharacterSpec(
    name='SPY (S&P 500 ETF)', price_range=(540, 580), tick=0.01, tick_value=1.00,
    initial_margin=275, maintenance_margin=165,
    regime=RegimeSpec(
        mean_duration={'chop': 30, 'trend_up': 35, 'trend_down': 35, 'impulse': 4, 'gap_hold': 1},
        transition={
            ('chop', 'trend_up'): 0.42, ('chop', 'trend_down'): 0.42, ('chop', 'impulse'): 0.16,
            ('trend_up', 'chop'): 0.35, ('trend_up', 'impulse'): 0.15, ('trend_up', 'trend_down'): 0.50,
            ('trend_down', 'chop'): 0.35, ('trend_down', 'impulse'): 0.15, ('trend_down', 'trend_up'): 0.50,
            ('impulse', 'chop'): 0.7, ('impulse', 'trend_up'): 0.15, ('impulse', 'trend_down'): 0.15,
        },
    ),
    drift=DriftSpec(chop_sigma=0.005, trend_sigma=0.016, trend_magnitude=0.025, impulse_magnitude=0.12, global_bias=0.003),
    volatility=VolatilitySpec(chop=0.07, trend=0.16, impulse=0.35),
    wick=WickSpec(chop_ratio=2.0, trend_ratio=0.6),
    volume=VolumeSpec(base=5000),
    gap=GapSpec(prob=0.05, min_size=0.002, max_size=0.005),
    event=EventSpec(wick_stab_prob=0.005),
)

# AAPL: 1.5-2.5% daily range (~$3-5 on $210). Moderate vol, clear trends, earnings-driven gaps.
AAPL_STOCK = CharacterSpec(
    name='AAPL (Apple)', price_range=(200, 230), tick=0.01, tick_value=1.00,
    initial_margin=105, maintenance_margin=63,
    regime=RegimeSpec(
        mean_duration={'chop': 22, 'trend_up': 30, 'trend_down': 30, 'impulse': 5, 'gap_hold': 1},
        transition={
            ('chop', 'trend_up'): 0.38, ('chop', 'trend_down'): 0.38, ('chop', 'impulse'): 0.24,
            ('trend_up', 'chop'): 0.35, ('trend_up', 'impulse'): 0.20, ('trend_up', 'trend_down'): 0.45,
            ('trend_down', 'chop'): 0.35, ('trend_down', 'impulse'): 0.20, ('trend_down', 'trend_up'): 0.45,
            ('impulse', 'chop'): 0.7, ('impulse', 'trend_up'): 0.15, ('impulse', 'trend_down'): 0.15,
        },
    ),
    drift=DriftSpec(chop_sigma=0.003, trend_sigma=0.010, trend_magnitude=0.016, impulse_magnitude=0.08, global_bias=0.003),
    volatility=VolatilitySpec(chop=0.045, trend=0.11, impulse=0.25),
    wick=WickSpec(chop_ratio=2.0, trend_ratio=0.6),
    volume=VolumeSpec(base=4000),
    gap=GapSpec(prob=0.08, min_size=0.003, max_size=0.01),
    event=EventSpec(wick_stab_prob=0.01),
)

# MSFT: 1.2-2% daily range (~$5-8 on $430). Similar to AAPL but slightly less volatile.
MSFT_STOCK = CharacterSpec(
    name='MSFT (Microsoft)', price_range=(420, 460), tick=0.01, tick_value=1.00,
    initial_margin=220, maintenance_margin=132,
    regime=RegimeSpec(
        mean_duration={'chop': 25, 'trend_up': 32, 'trend_down': 32, 'impulse': 4, 'gap_hold': 1},
        transition={
            ('chop', 'trend_up'): 0.40, ('chop', 'trend_down'): 0.40, ('chop', 'impulse'): 0.20,
            ('trend_up', 'chop'): 0.38, ('trend_up', 'impulse'): 0.17, ('trend_up', 'trend_down'): 0.45,
            ('trend_down', 'chop'): 0.38, ('trend_down', 'impulse'): 0.17, ('trend_down', 'trend_up'): 0.45,
            ('impulse', 'chop'): 0.7, ('impulse', 'trend_up'): 0.15, ('impulse', 'trend_down'): 0.15,
        },
    ),
    drift=DriftSpec(chop_sigma=0.009, trend_sigma=0.028, trend_magnitude=0.045, impulse_magnitude=0.22, global_bias=0.007),
    volatility=VolatilitySpec(chop=0.14, trend=0.32, impulse=0.7),
    wick=WickSpec(chop_ratio=2.1, trend_ratio=0.6),
    volume=VolumeSpec(base=3500),
    gap=GapSpec(prob=0.06, min_size=0.002, max_size=0.008),
    event=EventSpec(wick_stab_prob=0.008),
)

# PLTR: 3-5% daily range (~$3-6 on $120). High beta, momentum-driven, retail favorite.
PLTR_STOCK = CharacterSpec(
    name='PLTR (Palantir)', price_range=(100, 140), tick=0.01, tick_value=1.00,
    initial_margin=60, maintenance_margin=36,
    regime=RegimeSpec(
        mean_duration={'chop': 15, 'trend_up': 25, 'trend_down': 25, 'impulse': 6, 'gap_hold': 1},
        transition={
            ('chop', 'trend_up'): 0.35, ('chop', 'trend_down'): 0.35, ('chop', 'impulse'): 0.30,
            ('trend_up', 'chop'): 0.25, ('trend_up', 'impulse'): 0.35, ('trend_up', 'trend_down'): 0.40,
            ('trend_down', 'chop'): 0.25, ('trend_down', 'impulse'): 0.35, ('trend_down', 'trend_up'): 0.40,
            ('impulse', 'chop'): 0.5, ('impulse', 'trend_up'): 0.25, ('impulse', 'trend_down'): 0.25,
        },
    ),
    drift=DriftSpec(chop_sigma=0.005, trend_sigma=0.016, trend_magnitude=0.022, impulse_magnitude=0.11, global_bias=0.002),
    volatility=VolatilitySpec(chop=0.06, trend=0.14, impulse=0.32),
    wick=WickSpec(chop_ratio=1.5, trend_ratio=0.5, impulse_ratio=0.3, asymmetry=0.15),
    volume=VolumeSpec(base=3000, spike_prob=0.1, spike_max=2.5),
    gap=GapSpec(prob=0.15, min_size=0.005, max_size=0.02),
    event=EventSpec(wick_stab_prob=0.03, wick_stab_magnitude=2.2),
)

# TSLA: 3-5% daily range (~$7-15 on $250). Highly volatile, strong trends, gap-prone.
TSLA_GAPPY = CharacterSpec(
    name='TSLA (Tesla)', price_range=(220, 280), tick=0.01, tick_value=1.00,
    initial_margin=120, maintenance_margin=72,
    regime=RegimeSpec(
        mean_duration={'chop': 18, 'trend_up': 28, 'trend_down': 28, 'impulse': 6, 'gap_hold': 1},
        transition={
            ('chop', 'trend_up'): 0.38, ('chop', 'trend_down'): 0.38, ('chop', 'impulse'): 0.24,
            ('trend_up', 'chop'): 0.25, ('trend_up', 'impulse'): 0.30, ('trend_up', 'trend_down'): 0.45,
            ('trend_down', 'chop'): 0.25, ('trend_down', 'impulse'): 0.30, ('trend_down', 'trend_up'): 0.45,
            ('impulse', 'chop'): 0.5, ('impulse', 'trend_up'): 0.25, ('impulse', 'trend_down'): 0.25,
        },
    ),
    drift=DriftSpec(chop_sigma=0.012, trend_sigma=0.04, trend_magnitude=0.055, impulse_magnitude=0.28, global_bias=0.0),
    volatility=VolatilitySpec(chop=0.14, trend=0.32, impulse=0.7),
    wick=WickSpec(chop_ratio=1.2, trend_ratio=0.4, impulse_ratio=0.25, asymmetry=0.2),
    volume=VolumeSpec(base=3000, spike_prob=0.12, spike_max=2.8),
    gap=GapSpec(prob=0.20, min_size=0.005, max_size=0.025, intraday_prob=0.005),
    event=EventSpec(wick_stab_prob=0.03, wick_stab_magnitude=2.5),
)

# GME: 4-8% daily range (~$1-2.50 on $28). Extreme volatility, retail-driven, impulse-heavy.
GME_RETAIL = CharacterSpec(
    name='GME (GameStop)', price_range=(22, 35), tick=0.01, tick_value=1.00,
    initial_margin=13, maintenance_margin=8,
    regime=RegimeSpec(
        mean_duration={'chop': 12, 'trend_up': 20, 'trend_down': 20, 'impulse': 6, 'gap_hold': 1},
        transition={
            ('chop', 'trend_up'): 0.30, ('chop', 'trend_down'): 0.30, ('chop', 'impulse'): 0.40,
            ('trend_up', 'chop'): 0.20, ('trend_up', 'impulse'): 0.45, ('trend_up', 'trend_down'): 0.35,
            ('trend_down', 'chop'): 0.20, ('trend_down', 'impulse'): 0.45, ('trend_down', 'trend_up'): 0.35,
            ('impulse', 'chop'): 0.4, ('impulse', 'trend_up'): 0.30, ('impulse', 'trend_down'): 0.30,
        },
    ),
    drift=DriftSpec(chop_sigma=0.003, trend_sigma=0.009, trend_magnitude=0.012, impulse_magnitude=0.05, global_bias=0.0),
    volatility=VolatilitySpec(chop=0.02, trend=0.045, impulse=0.12),
    wick=WickSpec(chop_ratio=1.5, trend_ratio=0.5, impulse_ratio=0.3, asymmetry=0.2),
    volume=VolumeSpec(base=2500, spike_prob=0.15, spike_max=3.0),
    gap=GapSpec(prob=0.25, min_size=0.01, max_size=0.05, intraday_prob=0.005),
    event=EventSpec(wick_stab_prob=0.04, wick_stab_magnitude=2.5),
)

CHARACTERS = {
    # E-mini futures
    'ES': ES_CALM, 'NQ': NQ_ACTIVE, 'CL': CL_CHOPPY, 'RTY': RTY_RUSSELL,
    # Micro futures
    'MES': MES_MICRO, 'MNQ': MNQ_MICRO, 'MCL': MCL_MICRO, 'M2K': M2K_MICRO,
    # Stocks
    'SPY': SPY_QUIET, 'AAPL': AAPL_STOCK, 'MSFT': MSFT_STOCK, 'PLTR': PLTR_STOCK,
    'TSLA': TSLA_GAPPY, 'GME': GME_RETAIL,
}
