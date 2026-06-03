"""Pre-built CharacterSpec instances for 6 instruments."""
from .spec import CharacterSpec, RegimeSpec, DriftSpec, VolatilitySpec, WickSpec, VolumeSpec, GapSpec, EventSpec

ES_CALM = CharacterSpec(
    name='ES (calm futures)', price_range=(5000, 7000), tick=0.25, tick_value=12.50,
    regime=RegimeSpec(mean_duration={'chop': 25, 'trend_up': 20, 'trend_down': 20, 'impulse': 3, 'gap_hold': 1}),
    drift=DriftSpec(chop_sigma=0.05, trend_sigma=0.15, trend_magnitude=0.25, impulse_magnitude=1.5, global_bias=0.02),
    volatility=VolatilitySpec(chop=1.0, trend=2.0, impulse=4.0),
    wick=WickSpec(chop_ratio=2.0, trend_ratio=0.5, impulse_ratio=0.3),
    volume=VolumeSpec(base=1000),
    gap=GapSpec(prob=0.0),
    event=EventSpec(wick_stab_prob=0.02),
)

NQ_ACTIVE = CharacterSpec(
    name='NQ (active)', price_range=(18000, 22000), tick=0.25, tick_value=5.00,
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

SPY_QUIET = CharacterSpec(
    name='SPY (quiet)', price_range=(520, 580), tick=0.01, tick_value=1.00,
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

TSLA_GAPPY = CharacterSpec(
    name='TSLA (gappy)', price_range=(200, 280), tick=0.01, tick_value=1.00,
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
    name='GME (high-beta retail)', price_range=(18, 35), tick=0.01, tick_value=1.00,
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

CL_CHOPPY = CharacterSpec(
    name='CL (choppy)', price_range=(70, 90), tick=0.01, tick_value=10.00,
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

CHARACTERS = {
    'ES': ES_CALM, 'NQ': NQ_ACTIVE, 'SPY': SPY_QUIET,
    'TSLA': TSLA_GAPPY, 'GME': GME_RETAIL, 'CL': CL_CHOPPY,
}
