"""Pre-built CharacterSpec instances for all instruments."""
from .spec import CharacterSpec, RegimeSpec, DriftSpec, VolatilitySpec, WickSpec, VolumeSpec, GapSpec, EventSpec

# ── E-mini Futures ────────────────────────────────────────────────────────────

ES_CALM = CharacterSpec(
    name='ES (E-mini S&P)', price_range=(5000, 7000), tick=0.25, tick_value=12.50,
    initial_margin=12980, maintenance_margin=11800,
    regime=RegimeSpec(mean_duration={'chop': 25, 'trend_up': 20, 'trend_down': 20, 'impulse': 3, 'gap_hold': 1}),
    drift=DriftSpec(chop_sigma=0.05, trend_sigma=0.15, trend_magnitude=0.25, impulse_magnitude=1.5, global_bias=0.02),
    volatility=VolatilitySpec(chop=1.0, trend=2.0, impulse=4.0),
    wick=WickSpec(chop_ratio=2.0, trend_ratio=0.5, impulse_ratio=0.3),
    volume=VolumeSpec(base=1000),
    gap=GapSpec(prob=0.0),
    event=EventSpec(wick_stab_prob=0.02),
)

NQ_ACTIVE = CharacterSpec(
    name='NQ (E-mini Nasdaq)', price_range=(18000, 22000), tick=0.25, tick_value=5.00,
    initial_margin=17600, maintenance_margin=16000,
    regime=RegimeSpec(
        mean_duration={'chop': 15, 'trend_up': 18, 'trend_down': 18, 'impulse': 4, 'gap_hold': 1},
        transition={
            ('chop', 'trend_up'): 0.35, ('chop', 'trend_down'): 0.35, ('chop', 'impulse'): 0.3,
            ('trend_up', 'chop'): 0.55, ('trend_up', 'impulse'): 0.45,
            ('trend_down', 'chop'): 0.55, ('trend_down', 'impulse'): 0.45,
            ('impulse', 'chop'): 1.0,
        },
    ),
    drift=DriftSpec(chop_sigma=0.1, trend_sigma=0.3, trend_magnitude=0.5, impulse_magnitude=3.0, global_bias=0.03),
    volatility=VolatilitySpec(chop=2.5, trend=5.0, impulse=10.0),
    wick=WickSpec(chop_ratio=1.8, trend_ratio=1.0),
    volume=VolumeSpec(base=800),
    gap=GapSpec(prob=0.0),
    event=EventSpec(wick_stab_prob=0.04),
)

CL_CHOPPY = CharacterSpec(
    name='CL (Crude Oil)', price_range=(70, 90), tick=0.01, tick_value=10.00,
    initial_margin=12000, maintenance_margin=10900,
    regime=RegimeSpec(
        mean_duration={'chop': 30, 'trend_up': 10, 'trend_down': 10, 'impulse': 2, 'gap_hold': 1},
        transition={
            ('chop', 'trend_up'): 0.3, ('chop', 'trend_down'): 0.3, ('chop', 'impulse'): 0.4,
            ('trend_up', 'chop'): 0.8, ('trend_up', 'impulse'): 0.2,
            ('trend_down', 'chop'): 0.8, ('trend_down', 'impulse'): 0.2,
            ('impulse', 'chop'): 1.0,
        },
    ),
    drift=DriftSpec(chop_sigma=0.015, trend_sigma=0.04, trend_magnitude=0.05, impulse_magnitude=0.2, global_bias=0.0),
    volatility=VolatilitySpec(chop=0.15, trend=0.3, impulse=0.6),
    wick=WickSpec(chop_ratio=1.5, trend_ratio=0.5, asymmetry=0.15),
    volume=VolumeSpec(base=600),
    gap=GapSpec(prob=0.08, min_size=0.003, max_size=0.015),
    event=EventSpec(wick_stab_prob=0.03),
)

RTY_RUSSELL = CharacterSpec(
    name='RTY (E-mini Russell)', price_range=(2000, 2300), tick=0.10, tick_value=5.00,
    initial_margin=6800, maintenance_margin=6200,
    regime=RegimeSpec(
        mean_duration={'chop': 18, 'trend_up': 15, 'trend_down': 15, 'impulse': 3, 'gap_hold': 1},
        transition={
            ('chop', 'trend_up'): 0.35, ('chop', 'trend_down'): 0.35, ('chop', 'impulse'): 0.3,
            ('trend_up', 'chop'): 0.6, ('trend_up', 'impulse'): 0.4,
            ('trend_down', 'chop'): 0.6, ('trend_down', 'impulse'): 0.4,
            ('impulse', 'chop'): 1.0,
        },
    ),
    drift=DriftSpec(chop_sigma=0.08, trend_sigma=0.2, trend_magnitude=0.35, impulse_magnitude=2.0, global_bias=0.0),
    volatility=VolatilitySpec(chop=1.8, trend=3.5, impulse=7.0),
    wick=WickSpec(chop_ratio=1.8, trend_ratio=0.6, impulse_ratio=0.3),
    volume=VolumeSpec(base=500),
    gap=GapSpec(prob=0.0),
    event=EventSpec(wick_stab_prob=0.03),
)

# ── Micro Futures (1/10th of E-mini, same price/tick but smaller tick_value) ──

MES_MICRO = CharacterSpec(
    name='MES (Micro S&P)', price_range=(5000, 7000), tick=0.25, tick_value=1.25,
    initial_margin=1265, maintenance_margin=1150,
    regime=ES_CALM.regime, drift=ES_CALM.drift, volatility=ES_CALM.volatility,
    wick=ES_CALM.wick, volume=ES_CALM.volume, gap=ES_CALM.gap, event=ES_CALM.event,
)

MNQ_MICRO = CharacterSpec(
    name='MNQ (Micro Nasdaq)', price_range=(18000, 22000), tick=0.25, tick_value=0.50,
    initial_margin=1760, maintenance_margin=1600,
    regime=NQ_ACTIVE.regime, drift=NQ_ACTIVE.drift, volatility=NQ_ACTIVE.volatility,
    wick=NQ_ACTIVE.wick, volume=NQ_ACTIVE.volume, gap=NQ_ACTIVE.gap, event=NQ_ACTIVE.event,
)

MCL_MICRO = CharacterSpec(
    name='MCL (Micro Crude)', price_range=(70, 90), tick=0.01, tick_value=1.00,
    initial_margin=1200, maintenance_margin=1090,
    regime=CL_CHOPPY.regime, drift=CL_CHOPPY.drift, volatility=CL_CHOPPY.volatility,
    wick=CL_CHOPPY.wick, volume=CL_CHOPPY.volume, gap=CL_CHOPPY.gap, event=CL_CHOPPY.event,
)

M2K_MICRO = CharacterSpec(
    name='M2K (Micro Russell)', price_range=(2000, 2300), tick=0.10, tick_value=0.50,
    initial_margin=680, maintenance_margin=620,
    regime=RTY_RUSSELL.regime, drift=RTY_RUSSELL.drift, volatility=RTY_RUSSELL.volatility,
    wick=RTY_RUSSELL.wick, volume=RTY_RUSSELL.volume, gap=RTY_RUSSELL.gap, event=RTY_RUSSELL.event,
)

# ── Stocks (Reg T: ~50% initial, ~30% maintenance of share price) ─────────────

SPY_QUIET = CharacterSpec(
    name='SPY (S&P 500 ETF)', price_range=(520, 580), tick=0.01, tick_value=1.00,
    initial_margin=275, maintenance_margin=165,
    regime=RegimeSpec(
        mean_duration={'chop': 30, 'trend_up': 25, 'trend_down': 25, 'impulse': 2, 'gap_hold': 1},
        transition={
            ('chop', 'trend_up'): 0.45, ('chop', 'trend_down'): 0.45, ('chop', 'impulse'): 0.1,
            ('trend_up', 'chop'): 0.9, ('trend_up', 'impulse'): 0.1,
            ('trend_down', 'chop'): 0.9, ('trend_down', 'impulse'): 0.1,
            ('impulse', 'chop'): 1.0,
        },
    ),
    drift=DriftSpec(chop_sigma=0.01, trend_sigma=0.025, trend_magnitude=0.04, impulse_magnitude=0.2, global_bias=0.008),
    volatility=VolatilitySpec(chop=0.15, trend=0.35, impulse=0.8),
    wick=WickSpec(chop_ratio=2.2, trend_ratio=0.7),
    volume=VolumeSpec(base=5000),
    gap=GapSpec(prob=0.05, min_size=0.002, max_size=0.005),
    event=EventSpec(wick_stab_prob=0.005),
)

AAPL_STOCK = CharacterSpec(
    name='AAPL (Apple)', price_range=(195, 230), tick=0.01, tick_value=1.00,
    initial_margin=105, maintenance_margin=63,
    regime=RegimeSpec(
        mean_duration={'chop': 25, 'trend_up': 22, 'trend_down': 22, 'impulse': 3, 'gap_hold': 1},
        transition={
            ('chop', 'trend_up'): 0.4, ('chop', 'trend_down'): 0.4, ('chop', 'impulse'): 0.2,
            ('trend_up', 'chop'): 0.75, ('trend_up', 'impulse'): 0.25,
            ('trend_down', 'chop'): 0.75, ('trend_down', 'impulse'): 0.25,
            ('impulse', 'chop'): 1.0,
        },
    ),
    drift=DriftSpec(chop_sigma=0.012, trend_sigma=0.03, trend_magnitude=0.05, impulse_magnitude=0.25, global_bias=0.01),
    volatility=VolatilitySpec(chop=0.18, trend=0.4, impulse=0.9),
    wick=WickSpec(chop_ratio=2.0, trend_ratio=0.6),
    volume=VolumeSpec(base=4000),
    gap=GapSpec(prob=0.08, min_size=0.003, max_size=0.01),
    event=EventSpec(wick_stab_prob=0.01),
)

MSFT_STOCK = CharacterSpec(
    name='MSFT (Microsoft)', price_range=(410, 460), tick=0.01, tick_value=1.00,
    initial_margin=220, maintenance_margin=132,
    regime=RegimeSpec(
        mean_duration={'chop': 28, 'trend_up': 22, 'trend_down': 22, 'impulse': 2, 'gap_hold': 1},
        transition={
            ('chop', 'trend_up'): 0.42, ('chop', 'trend_down'): 0.42, ('chop', 'impulse'): 0.16,
            ('trend_up', 'chop'): 0.8, ('trend_up', 'impulse'): 0.2,
            ('trend_down', 'chop'): 0.8, ('trend_down', 'impulse'): 0.2,
            ('impulse', 'chop'): 1.0,
        },
    ),
    drift=DriftSpec(chop_sigma=0.01, trend_sigma=0.028, trend_magnitude=0.045, impulse_magnitude=0.22, global_bias=0.01),
    volatility=VolatilitySpec(chop=0.16, trend=0.38, impulse=0.85),
    wick=WickSpec(chop_ratio=2.1, trend_ratio=0.65),
    volume=VolumeSpec(base=3500),
    gap=GapSpec(prob=0.06, min_size=0.002, max_size=0.008),
    event=EventSpec(wick_stab_prob=0.008),
)

PLTR_STOCK = CharacterSpec(
    name='PLTR (Palantir)', price_range=(100, 140), tick=0.01, tick_value=1.00,
    initial_margin=60, maintenance_margin=36,
    regime=RegimeSpec(
        mean_duration={'chop': 12, 'trend_up': 12, 'trend_down': 12, 'impulse': 4, 'gap_hold': 1},
        transition={
            ('chop', 'trend_up'): 0.35, ('chop', 'trend_down'): 0.35, ('chop', 'impulse'): 0.3,
            ('trend_up', 'chop'): 0.5, ('trend_up', 'impulse'): 0.5,
            ('trend_down', 'chop'): 0.5, ('trend_down', 'impulse'): 0.5,
            ('impulse', 'chop'): 0.7, ('impulse', 'trend_up'): 0.15, ('impulse', 'trend_down'): 0.15,
        },
    ),
    drift=DriftSpec(chop_sigma=0.02, trend_sigma=0.06, trend_magnitude=0.07, impulse_magnitude=0.35, global_bias=0.005),
    volatility=VolatilitySpec(chop=0.22, trend=0.5, impulse=1.1),
    wick=WickSpec(chop_ratio=1.5, trend_ratio=0.5, impulse_ratio=0.3, asymmetry=0.15),
    volume=VolumeSpec(base=3000, spike_prob=0.1, spike_max=2.5),
    gap=GapSpec(prob=0.15, min_size=0.005, max_size=0.02),
    event=EventSpec(wick_stab_prob=0.03, wick_stab_magnitude=2.2),
)

TSLA_GAPPY = CharacterSpec(
    name='TSLA (Tesla)', price_range=(200, 280), tick=0.01, tick_value=1.00,
    initial_margin=120, maintenance_margin=72,
    regime=RegimeSpec(
        mean_duration={'chop': 20, 'trend_up': 15, 'trend_down': 15, 'impulse': 4, 'gap_hold': 1},
        transition={
            ('chop', 'trend_up'): 0.4, ('chop', 'trend_down'): 0.4, ('chop', 'impulse'): 0.2,
            ('trend_up', 'chop'): 0.7, ('trend_up', 'impulse'): 0.3,
            ('trend_down', 'chop'): 0.7, ('trend_down', 'impulse'): 0.3,
            ('impulse', 'chop'): 0.85, ('impulse', 'trend_up'): 0.075, ('impulse', 'trend_down'): 0.075,
        },
    ),
    drift=DriftSpec(chop_sigma=0.03, trend_sigma=0.08, trend_magnitude=0.08, impulse_magnitude=0.4, global_bias=0.0),
    volatility=VolatilitySpec(chop=0.2, trend=0.45, impulse=0.9),
    wick=WickSpec(chop_ratio=1.2, trend_ratio=0.4, impulse_ratio=0.25, asymmetry=0.2),
    volume=VolumeSpec(base=3000, spike_prob=0.12, spike_max=2.8),
    gap=GapSpec(prob=0.25, min_size=0.005, max_size=0.025, intraday_prob=0.005),
    event=EventSpec(wick_stab_prob=0.03, wick_stab_magnitude=2.5),
)

GME_RETAIL = CharacterSpec(
    name='GME (GameStop)', price_range=(18, 35), tick=0.01, tick_value=1.00,
    initial_margin=13, maintenance_margin=8,
    regime=RegimeSpec(
        mean_duration={'chop': 10, 'trend_up': 8, 'trend_down': 8, 'impulse': 4, 'gap_hold': 1},
        transition={
            ('chop', 'trend_up'): 0.3, ('chop', 'trend_down'): 0.3, ('chop', 'impulse'): 0.4,
            ('trend_up', 'chop'): 0.4, ('trend_up', 'impulse'): 0.6,
            ('trend_down', 'chop'): 0.4, ('trend_down', 'impulse'): 0.6,
            ('impulse', 'chop'): 0.65, ('impulse', 'trend_up'): 0.175, ('impulse', 'trend_down'): 0.175,
        },
    ),
    drift=DriftSpec(chop_sigma=0.008, trend_sigma=0.02, trend_magnitude=0.02, impulse_magnitude=0.08, global_bias=0.0),
    volatility=VolatilitySpec(chop=0.04, trend=0.09, impulse=0.25),
    wick=WickSpec(chop_ratio=1.5, trend_ratio=0.5, impulse_ratio=0.3, asymmetry=0.2),
    volume=VolumeSpec(base=2500, spike_prob=0.15, spike_max=3.0),
    gap=GapSpec(prob=0.30, min_size=0.01, max_size=0.05, intraday_prob=0.005),
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
