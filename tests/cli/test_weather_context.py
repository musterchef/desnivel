from pathlib import Path
from urllib.error import URLError

import numpy as np
import pytest

from desnivel.cli.weather_context import prepare_weather_context
from desnivel.trip.context import ContextSource, track_signature
from desnivel.trip.track import Track, TrackSegment


def track():
    return Track('test', np.array([0., 10.]),
                 {'lat': np.array([44., 44.001]), 'lon': np.array([9., 9.001]),
                  'cum_dist_m': np.array([0., 100.])}, segments=(TrackSegment(0, 2, 3600, 3610, 0, 1),))


def source():
    return ContextSource(dict(version=1, source='weather', track_signature=track_signature(track()), axis='time',
        units={'wind_speed_kmh': 'km/h', 'precipitation_mm': 'mm', 'precipitation_change_mm': 'mm'},
        provenance={'provider': 'fixture'}, records=[dict(segment=0, start=0, end=10,
            values={'wind_speed_kmh': 20., 'precipitation_mm': 0., 'precipitation_change_mm': 0.}, details={})]))


def test_automatic_weather_downloads_once_then_reuses_cache_without_network(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr('desnivel.cli.weather_context.WeatherFetcher.fetch',
                        lambda self, track: calls.append(track) or source())
    assert prepare_weather_context(track(), cache_dir=tmp_path).data == source().data
    assert len(calls) == 1
    assert len(list(tmp_path.glob('*.json'))) == 1
    assert prepare_weather_context(track(), cache_dir=tmp_path).data == source().data
    assert len(calls) == 1


def test_explicit_file_is_loaded_and_missing_or_invalid_file_is_not_replaced(tmp_path, monkeypatch):
    monkeypatch.setattr('desnivel.cli.weather_context.WeatherFetcher.fetch',
                        lambda *_: pytest.fail('nessun download per un file esplicito'))
    path = tmp_path/'chosen.json'
    with pytest.raises(FileNotFoundError):
        prepare_weather_context(track(), path, cache_dir=tmp_path)
    source().save(path)
    assert prepare_weather_context(track(), path).data == source().data
    path.write_text('{}')
    with pytest.raises(ValueError):
        prepare_weather_context(track(), path)


def test_dry_run_does_not_download_and_failed_request_does_not_create_cache(tmp_path, monkeypatch):
    def fail(*_):
        raise URLError('offline')
    monkeypatch.setattr('desnivel.cli.weather_context.WeatherFetcher.fetch', fail)
    assert prepare_weather_context(track(), download=False, cache_dir=tmp_path) is None
    assert not list(tmp_path.iterdir())
    with pytest.raises(URLError):
        prepare_weather_context(track(), cache_dir=tmp_path)
    assert not list(tmp_path.iterdir())
