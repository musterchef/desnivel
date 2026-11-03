"""Caricamento del meteo della tappa e cache persistente delle acquisizioni."""
from pathlib import Path
from tempfile import NamedTemporaryFile

from desnivel.trip.context import ContextSource, track_signature
from desnivel.trip.weather import WeatherFetcher


DEFAULT_CACHE = Path(__file__).resolve().parents[3]/'output'/'context'/'weather'


def prepare_weather_context(track, path=None, *, download=True, cache_dir=DEFAULT_CACHE):
    """Riusa il file esplicito o la cache; acquisisce soltanto il meteo assente."""
    explicit = path is not None
    path = Path(path) if explicit else Path(cache_dir)/f'era5-5000m-v1-{track_signature(track)}.json'
    if explicit or path.exists():
        source = ContextSource.load(path, track)
        print(f'Meteo caricato: {path}', flush=True)
        return source
    if not download:
        print('Meteo non in cache: verrà acquisito all’avvio senza --dry-run.', flush=True)
        return None
    print('Acquisizione del meteo storico lungo la tappa…', flush=True)
    source = WeatherFetcher().fetch(track)
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, suffix='.json', delete=False) as handle:
        temporary = Path(handle.name)
    try:
        source.save(temporary)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    print(f'Meteo salvato in cache: {path}', flush=True)
    return source
