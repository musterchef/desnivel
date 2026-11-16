"""Caricamento tipizzato delle impostazioni applicative Desnivel."""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.9–3.10
    import tomli as tomllib


DEFAULT_SETTINGS_PATH = Path('settings/desnivel.toml')


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
        for name in ('max_relative_elevation', 'max_relative_distance',
                     'max_reversal_distance_m', 'min_recovery_ratio'):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError(f'trip.route_structure.{name} deve essere positivo e finito')
        if self.max_relative_elevation >= 1 or self.max_relative_distance >= 1:
            raise ValueError('i rapporti relativi della forma devono essere minori di 1')


@dataclass(frozen=True)
class Settings:
    route_structure: RouteStructureSettings


def load_settings(path=DEFAULT_SETTINGS_PATH):
    """Legge e valida un file TOML senza valori sostitutivi impliciti."""
    data = tomllib.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or set(data) != {'trip'}:
        raise ValueError('le impostazioni richiedono soltanto la sezione trip')
    trip = data['trip']
    if not isinstance(trip, dict) or set(trip) != {'route_structure'}:
        raise ValueError('trip richiede soltanto la sezione route_structure')
    values = trip['route_structure']
    expected = {field for field in RouteStructureSettings.__dataclass_fields__}
    if not isinstance(values, dict) or set(values) != expected:
        raise ValueError(f'trip.route_structure richiede {sorted(expected)}')
    return Settings(RouteStructureSettings(**values))
