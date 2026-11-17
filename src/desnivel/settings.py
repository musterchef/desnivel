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
class AnalysisBand:
    name: str
    from_slope_ratio: float | None


@dataclass(frozen=True)
class AnalysisSettings:
    sample_distance_m: float
    slope_window_m: float
    min_zone_distance_m: float
    bands: tuple[AnalysisBand, ...]

    def as_dict(self):
        return {
            'sample_distance_m': self.sample_distance_m,
            'slope_window_m': self.slope_window_m,
            'min_zone_distance_m': self.min_zone_distance_m,
            'bands': [{'name': band.name, 'from_slope_ratio': band.from_slope_ratio}
                      for band in self.bands],
        }


@dataclass(frozen=True)
class GroupingSettings:
    families: tuple[tuple[str, tuple[str, ...]], ...]

    def as_dict(self):
        return {'families': {name: list(bands) for name, bands in self.families}}


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
    analysis: AnalysisSettings
    grouping: GroupingSettings
    route_structure: RouteStructureSettings


@dataclass(frozen=True)
class TransportSettings:
    osc: OscConfig


@dataclass(frozen=True)
class WeatherContextSettings:
    distance_step_m: float
    batch_size: int
    cache_dir: str


@dataclass(frozen=True)
class SurfaceContextSettings:
    distance_step_m: float
    match_radius_m: float
    ambiguity_m: float
    batch_size: int
    bbox_padding_degrees: float


@dataclass(frozen=True)
class ContextSettings:
    weather: WeatherContextSettings
    surface: SurfaceContextSettings


@dataclass(frozen=True)
class NetworkSettings:
    context_timeout_s: float
    strava_timeout_s: float
    strava_page_size: int


@dataclass(frozen=True)
class Settings:
    trip: TripSettings
    transport: TransportSettings
    context: ContextSettings
    network: NetworkSettings

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


def _analysis_settings(section):
    expected = {'sample_distance_m', 'slope_window_m', 'min_zone_distance_m', 'bands'}
    if not isinstance(section, dict) or set(section) != expected:
        raise ValueError(f'trip.analysis richiede {sorted(expected)}')
    bands = section['bands']
    if not isinstance(bands, list) or not bands:
        raise ValueError('trip.analysis.bands deve contenere almeno una fascia')
    parsed, names, previous = [], set(), -math.inf
    for index, band in enumerate(bands):
        required = {'name'} if index == 0 else {'name', 'from_slope_ratio'}
        if not isinstance(band, dict) or set(band) != required:
            raise ValueError('la prima fascia richiede name; le successive anche from_slope_ratio')
        name = band['name']
        lower = band.get('from_slope_ratio')
        if not isinstance(name, str) or not name or name in names:
            raise ValueError('i nomi delle fasce devono essere non vuoti e distinti')
        if index and (type(lower) not in (int, float)
                      or not math.isfinite(lower) or lower <= previous):
            raise ValueError('le soglie delle fasce devono essere finite e strettamente crescenti')
        names.add(name)
        if index:
            previous = lower
        parsed.append(AnalysisBand(name, lower))
    settings = AnalysisSettings(
        sample_distance_m=section['sample_distance_m'],
        slope_window_m=section['slope_window_m'],
        min_zone_distance_m=section['min_zone_distance_m'],
        bands=tuple(parsed),
    )
    _positive(settings, ('sample_distance_m', 'slope_window_m', 'min_zone_distance_m'),
              'trip.analysis')
    return settings


def _grouping_settings(section, analysis):
    if not isinstance(section, dict) or set(section) != {'families'}:
        raise ValueError('trip.grouping richiede soltanto families')
    families = section['families']
    if not isinstance(families, dict) or not families:
        raise ValueError('trip.grouping.families deve contenere almeno una famiglia')
    parsed, assigned = [], set()
    for name, bands in families.items():
        if (not isinstance(name, str) or not name or not isinstance(bands, list) or not bands
                or any(not isinstance(band, str) or not band for band in bands)
                or len(set(bands)) != len(bands)):
            raise ValueError('ogni famiglia richiede un nome e fasce non vuote e distinte')
        overlap = assigned.intersection(bands)
        if overlap:
            raise ValueError(f'fasce assegnate a più famiglie: {sorted(overlap)}')
        assigned.update(bands)
        parsed.append((name, tuple(bands)))
    available = {band.name for band in analysis.bands}
    if assigned != available:
        raise ValueError(f'fasce senza famiglia: {sorted(available-assigned)}; '
                         f'fasce sconosciute: {sorted(assigned-available)}')
    return GroupingSettings(tuple(parsed))


def _validate_external_settings(settings):
    weather = settings.context.weather
    surface = settings.context.surface
    network = settings.network
    _positive(weather, ('distance_step_m', 'batch_size'), 'context.weather')
    if type(weather.batch_size) is not int:
        raise ValueError('context.weather.batch_size deve essere un intero positivo')
    if not isinstance(weather.cache_dir, str) or not weather.cache_dir:
        raise ValueError('context.weather.cache_dir deve essere una stringa non vuota')
    _positive(surface, ('distance_step_m', 'match_radius_m', 'ambiguity_m',
                        'batch_size', 'bbox_padding_degrees'), 'context.surface')
    if type(surface.batch_size) is not int:
        raise ValueError('context.surface.batch_size deve essere un intero positivo')
    if surface.ambiguity_m > surface.match_radius_m:
        raise ValueError('context.surface.ambiguity_m non può superare match_radius_m')
    _positive(network, ('context_timeout_s', 'strava_timeout_s', 'strava_page_size'), 'network')
    if type(network.strava_page_size) is not int or network.strava_page_size > 200:
        raise ValueError('network.strava_page_size deve essere un intero tra 1 e 200')


def load_settings(path=DEFAULT_SETTINGS_PATH):
    """Legge e valida un file TOML senza valori sostitutivi impliciti."""
    data = tomllib.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or set(data) != {'trip', 'transport', 'context', 'network'}:
        raise ValueError('le impostazioni richiedono trip, transport, context e network')
    trip = data['trip']
    transport = data['transport']
    context = data['context']
    if not isinstance(trip, dict) or set(trip) != {
            'timing', 'gpx', 'quality', 'analysis', 'grouping', 'route_structure'}:
        raise ValueError('trip richiede timing, gpx, quality, analysis, grouping e route_structure')
    if not isinstance(transport, dict) or set(transport) != {'osc'}:
        raise ValueError('transport richiede soltanto la sezione osc')
    if not isinstance(context, dict) or set(context) != {'weather', 'surface'}:
        raise ValueError('context richiede weather e surface')
    analysis = _analysis_settings(trip['analysis'])
    settings = Settings(
        trip=TripSettings(
            timing=_require_fields(trip['timing'], TimingConfig, 'trip.timing'),
            gpx=_require_fields(trip['gpx'], GpxConfig, 'trip.gpx'),
            quality=_require_fields(trip['quality'], QualitySettings, 'trip.quality'),
            analysis=analysis,
            grouping=_grouping_settings(trip['grouping'], analysis),
            route_structure=_require_fields(
                trip['route_structure'], RouteStructureSettings, 'trip.route_structure'),
        ),
        transport=TransportSettings(
            osc=_require_fields(transport['osc'], OscConfig, 'transport.osc'),
        ),
        context=ContextSettings(
            weather=_require_fields(context['weather'], WeatherContextSettings, 'context.weather'),
            surface=_require_fields(context['surface'], SurfaceContextSettings, 'context.surface'),
        ),
        network=_require_fields(data['network'], NetworkSettings, 'network'),
    )
    _validate_config(settings.config)
    _validate_external_settings(settings)
    return settings


DEFAULT_SETTINGS = load_settings()
DEFAULT_CONFIG = DEFAULT_SETTINGS.config
