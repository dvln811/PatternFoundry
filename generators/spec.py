"""CharacterSpec: composable blueprint for synthetic market data generation."""
from dataclasses import dataclass, field


@dataclass
class RegimeSpec:
    states: tuple = ('chop', 'trend_up', 'trend_down')
    mean_duration: dict = field(default_factory=lambda: {
        'chop': 25, 'trend_up': 20, 'trend_down': 20, 'impulse': 3, 'gap_hold': 1,
    })
    transition: dict = field(default_factory=lambda: {
        ('chop', 'trend_up'): 0.4, ('chop', 'trend_down'): 0.4, ('chop', 'impulse'): 0.2,
        ('trend_up', 'chop'): 0.7, ('trend_up', 'impulse'): 0.3,
        ('trend_down', 'chop'): 0.7, ('trend_down', 'impulse'): 0.3,
        ('impulse', 'chop'): 1.0,
        ('gap_hold', 'chop'): 0.5, ('gap_hold', 'trend_up'): 0.25, ('gap_hold', 'trend_down'): 0.25,
    })


@dataclass
class DriftSpec:
    chop_sigma: float = 0.05
    trend_sigma: float = 0.15
    trend_magnitude: float = 0.3
    impulse_magnitude: float = 1.5
    global_bias: float = 0.0


@dataclass
class VolatilitySpec:
    chop: float = 1.0
    trend: float = 2.0
    impulse: float = 4.0
    gap_hold: float = 1.5


@dataclass
class WickSpec:
    chop_ratio: float = 2.0
    trend_ratio: float = 0.6
    impulse_ratio: float = 0.4
    gap_hold_ratio: float = 0.3
    asymmetry: float = 0.3


@dataclass
class VolumeSpec:
    base: int = 1000
    candles_per_session: int = 390
    tod_open_mult: float = 2.2
    tod_midday_mult: float = 0.8
    tod_close_mult: float = 1.3
    spike_prob: float = 0.10
    spike_decay: float = 0.85
    spike_min: float = 1.5
    spike_max: float = 2.5


@dataclass
class GapSpec:
    prob: float = 0.0
    min_size: float = 0.005
    max_size: float = 0.02
    bias: float = 0.0
    intraday_prob: float = 0.0


@dataclass
class EventSpec:
    wick_stab_prob: float = 0.02
    wick_stab_magnitude: float = 3.0
    fvg_bias: float = 0.0


@dataclass
class CharacterSpec:
    name: str = 'Generic'
    price_range: tuple = (5000.0, 7000.0)
    tick: float = 0.25
    tick_value: float = 12.50
    regime: RegimeSpec = field(default_factory=RegimeSpec)
    drift: DriftSpec = field(default_factory=DriftSpec)
    volatility: VolatilitySpec = field(default_factory=VolatilitySpec)
    wick: WickSpec = field(default_factory=WickSpec)
    volume: VolumeSpec = field(default_factory=VolumeSpec)
    gap: GapSpec = field(default_factory=GapSpec)
    event: EventSpec = field(default_factory=EventSpec)

    # Back-compat properties
    @property
    def vol_chop(self): return self.volatility.chop
    @property
    def vol_trend(self): return self.volatility.trend
    @property
    def drift_bias(self): return self.drift.global_bias
    @property
    def wick_ratio_chop(self): return self.wick.chop_ratio
    @property
    def volume_base(self): return self.volume.base
    @property
    def trend_duration(self): return int(self.regime.mean_duration.get('trend_up', 20))
    @property
    def gap_prob(self): return self.gap.prob
