"""Caricamento tipizzato delle impostazioni applicative Desnivel."""
from __future__ import annotations

from dataclasses import dataclass, fields
import math
from pathlib import Path

from desnivel.trip.config import Config, GpxConfig, OscConfig, TimingConfig

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.9–3.10
    import tomli as tomllib


DEFAULT_SETTINGS_PATH = Path('settings/desnivel.toml')


def _require_fields(section, model, name):
    expected = {field.name for field in fields(model)}
    if not isinstance(section, dict) or set(section) != expected:
        raise ValueError(f'{name} richiede {sorted(expected)}')
    return model(**section)


def _positive(instance, names, section):
    for name in names:
        value = getattr(instance, name)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f'{section}.{name} deve essere positivo e finito')


@dataclass(frozen=True)
class QualitySettings:
    top_count: int
    neighbor_points: int
    group_gap_s: float
    context_s: float
    sampling_gap_s: float
    gap_distance_m: float
    stationary_duration_s: float
    stationary_radius_m: float
    resume_distance_m: float

    def __post_init__(self):
        if type(self.top_count) is not int or self.top_count < 1:
            raise ValueError('trip.quality.top_count deve essere un intero positivo')
        if type(self.neighbor_points) is not int or self.neighbor_points < 0:
            raise ValueError('trip.quality.neighbor_points deve essere un intero non negativo')
        _positive(self, (field.name for field in fields(self)
                         if field.name not in {'top_count', 'neighbor_points'}), 'trip.quality')


@dataclass(frozen=True)
class RouteStructureSettings:
    merge_reversals: bool
    max_relative_elevation: float
    max_relative_distance: float
    max_reversal_distance_m: float
    min_recovery_ratio: float

    def __post_init__(self):
        if type(self.merge_reversals) is not bool:
            raise ValueError('trip.route_structure.merge_reversals deve essere booleano')
        _positive(self, ('max_relative_elevation', 'max_relative_distance',
                         'max_reversal_distance_m', 'min_recovery_ratio'), 'trip.route_structure')
        if self.max_relative_elevation >= 1 or self.max_relative_distance >= 1:
            raise ValueError('i rapporti relativi della forma devono essere minori di 1')


@dataclass(frozen=True)
class TripSettings:
    timing: TimingConfig
    gpx: GpxConfig
    quality: QualitySettings
    route_structure: RouteStructureSettings


@dataclass(frozen=True)
class TransportSettings:
    osc: OscConfig


@dataclass(frozen=True)
class Settings:
    trip: TripSettings
    transport: TransportSettings

    @property
    def config(self):
        return Config(timing=self.trip.timing, gpx=self.trip.gpx, osc=self.transport.osc)


def _validate_config(config):
    _positive(config.timing, ('internal_rate_hz',), 'trip.timing')
    _positive(config.gpx, (field.name for field in fields(config.gpx)
                           if not field.name.startswith('effort_weight_')), 'trip.gpx')
    for name in ('effort_weight_speed', 'effort_weight_slope'):
        value = getattr(config.gpx, name)
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError(f'trip.gpx.{name} deve essere non negativo e finito')
    if type(config.gpx.raw_median_window) is not int or config.gpx.raw_median_window % 2 != 1:
        raise ValueError('trip.gpx.raw_median_window deve essere un intero positivo dispari')
    if (type(config.gpx.spike_max_removed_points) is not int
            or not 1 <= config.gpx.spike_max_removed_points <= 10):
        raise ValueError('trip.gpx.spike_max_removed_points deve essere un intero tra 1 e 10')
    if config.gpx.spike_min_detour_ratio >= 1:
        raise ValueError('trip.gpx.spike_min_detour_ratio deve essere minore di 1')
    if config.gpx.pause_gap_factor <= 1:
        raise ValueError('trip.gpx.pause_gap_factor deve essere maggiore di 1')
    if not math.isclose(config.gpx.effort_weight_speed + config.gpx.effort_weight_slope, 1.0):
        raise ValueError('i pesi trip.gpx.effort devono sommare a 1')
    if not isinstance(config.osc.host, str) or not config.osc.host:
        raise ValueError('transport.osc.host deve essere una stringa non vuota')
    if type(config.osc.port) is not int or not 1 <= config.osc.port <= 65535:
        raise ValueError('transport.osc.port deve essere un intero tra 1 e 65535')
    _positive(config.osc, ('trip_metrics_rate_hz',), 'transport.osc')


def load_settings(path=DEFAULT_SETTINGS_PATH):
    """Legge e valida un file TOML senza valori sostitutivi impliciti."""
    data = tomllib.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or set(data) != {'trip', 'transport'}:
        raise ValueError('le impostazioni richiedono le sezioni trip e transport')
    trip = data['trip']
    transport = data['transport']
    if not isinstance(trip, dict) or set(trip) != {'timing', 'gpx', 'quality', 'route_structure'}:
        raise ValueError('trip richiede timing, gpx, quality e route_structure')
    if not isinstance(transport, dict) or set(transport) != {'osc'}:
        raise ValueError('transport richiede soltanto la sezione osc')
    settings = Settings(
        trip=TripSettings(
            timing=_require_fields(trip['timing'], TimingConfig, 'trip.timing'),
            gpx=_require_fields(trip['gpx'], GpxConfig, 'trip.gpx'),
            quality=_require_fields(trip['quality'], QualitySettings, 'trip.quality'),
            route_structure=_require_fields(
                trip['route_structure'], RouteStructureSettings, 'trip.route_structure'),
        ),
        transport=TransportSettings(
            osc=_require_fields(transport['osc'], OscConfig, 'transport.osc'),
        ),
    )
    _validate_config(settings.config)
    return settings


DEFAULT_SETTINGS = load_settings()
DEFAULT_CONFIG = DEFAULT_SETTINGS.config
