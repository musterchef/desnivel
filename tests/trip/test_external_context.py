from copy import deepcopy
from dataclasses import replace
import json

import numpy as np
import pytest

from desnivel.cli.window_context import WindowContext
from desnivel.trip.context import ContextSource, route_intervals, track_signature
from desnivel.trip.surface import SurfaceFetcher
from desnivel.trip.track import Track, TrackSegment
from desnivel.trip.weather import WeatherFetcher


def track():
    return Track('test', np.array([0., 10., 10., 20.]),
                 {'lat': np.array([44., 44.001, 45., 45.001]), 'lon': np.array([9., 9., 10., 10.]),
                  'cum_dist_m': np.array([0., 100., 100., 200.])}, segments=(
                    TrackSegment(0, 2, 3600, 3610, 0, 1), TrackSegment(2, 4, 7200, 7210, 2, 3)))


def data():
    return dict(version=1, source='example', track_signature=track_signature(track()), axis='time',
                units={'wind': 'km/h', 'surface': 'category'}, provenance={'provider': 'fixture'},
                records=[dict(segment=0, start=0, end=10, values={'wind': 20., 'surface': 'asphalt'}, details={}),
                         dict(segment=1, start=10, end=20, values={'wind': None, 'surface': 'gravel'}, details={})])


def test_generic_context_keeps_gaps_channel_coverage_and_category_shares(tmp_path):
    source = ContextSource(data())
    window = WindowContext(track()).linear(elapsed_s=8, live_beat=0, start_beat=0,
                                         length_beats=4, bpm=60, speed=1)
    result = source.describe(window['parts'])
    assert result['channels']['wind'] == dict(unit='km/h', coverage_ratio=.5, value=20., status='partial')
    assert result['channels']['surface']['categories'] == {'asphalt': .5, 'gravel': .5}
    assert [r['segment'] for r in result['records']] == [0, 1]
    assert source.describe([])['channels']['wind']['status'] == 'unavailable'
    path = tmp_path/'context.json'
    source.save(path)
    assert ContextSource.load(path, track()).data == source.data
    changed = replace(track(), segments=(replace(track().segments[0], source_start_unix=3500), *track().segments[1:]))
    with pytest.raises(ValueError, match='traccia'):
        ContextSource.load(path, changed)
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize('mutation', ['overlap', 'nan', 'mixed'])
def test_invalid_external_data_is_rejected(mutation):
    definition = data()
    if mutation == 'overlap':
        definition['records'].append(deepcopy(definition['records'][0]))
    elif mutation == 'nan':
        definition['records'][0]['values']['wind'] = float('nan')
    else:
        definition['records'][1]['values']['wind'] = 'calm'
    with pytest.raises(ValueError):
        ContextSource(definition)


def test_route_sampling_keeps_original_positions_and_source_times_without_crossing_gaps():
    intervals = route_intervals(track(), distance_step_m=50, hourly=True)
    assert [r['segment'] for r in intervals] == [0, 0, 1, 1]
    assert [r['source_unix'] for r in intervals] == [3602.5, 3607.5, 7202.5, 7207.5]
    assert intervals[0]['latitude'] == pytest.approx(44.00025)
    assert intervals[2]['latitude'] == pytest.approx(45.00025)
    with pytest.raises(ValueError, match='riferimenti'):
        route_intervals(replace(track(), segments=()), distance_step_m=50)


def weather_response():
    return dict(hourly_units={'wind_speed_10m': 'km/h', 'precipitation': 'mm'},
                hourly={'time': [0, 3600, 7200, 10800], 'wind_speed_10m': [0., 20., 40., 60.],
                        'precipitation': [0., 0., 2., 0.]})


def test_weather_uses_local_hourly_accumulation_and_previous_hour_at_same_location():
    requests = []
    def request(url, params):
        requests.append(params)
        return [weather_response() for _ in params['latitude'].split(',')]
    source = WeatherFetcher(request).fetch(track(), distance_step_m=1000)
    assert source.data['axis'] == 'time'
    assert source.data['records'][0]['values']['wind_speed_kmh'] == pytest.approx(20+20*5/3600)
    assert source.data['records'][0]['values']['precipitation_change_mm'] == 2
    assert source.data['records'][1]['values']['precipitation_change_mm'] == -2
    assert requests[0]['timezone'] == 'UTC'
    assert requests[0]['models'] == 'era5'
    assert len(requests[0]['latitude'].split(',')) == 2
    assert 'acquisitions' not in source.describe([])['provenance']


def test_weather_nulls_and_missing_time_coverage_are_not_zero_and_bad_units_fail():
    response = weather_response()
    response['hourly']['wind_speed_10m'][1] = None
    values = WeatherFetcher._values(response, 3605)
    assert values['wind_speed_kmh'] is None
    assert values['precipitation_change_mm'] == 2
    assert all(v is None for v in WeatherFetcher._values(response, 20000).values())
    response['hourly_units']['precipitation'] = 'inch'
    with pytest.raises(ValueError, match='unità'):
        WeatherFetcher._values(response, 3605)


def way(ident, latitude=44., surface='asphalt'):
    return dict(type='way', id=ident, tags={'highway': 'residential', **({'surface': surface} if surface else {})},
                geometry=[{'lat': latitude, 'lon': 8.99}, {'lat': latitude, 'lon': 9.01}])


def test_surface_matches_polylines_and_preserves_unknown_and_ambiguous_roads():
    value, details = SurfaceFetcher.match(44., 9., [way(1)])
    assert value == 'asphalt' and details['distance_m'] == pytest.approx(0)
    # Una strada senza tag più vicina non deve essere scavalcata da una asfaltata.
    assert SurfaceFetcher.match(44., 9., [way(1, surface=None), way(2, 44.00015)])[0] is None
    assert SurfaceFetcher.match(44., 9., [way(1), way(2, 44.00001, 'gravel')])[1]['status'] == 'ambiguous'
    assert SurfaceFetcher.match(45., 9., [way(1)])[1]['status'] == 'no_road_within_radius'


def test_surface_fetcher_uses_generic_distance_context_and_keeps_attribution():
    requests = []
    def request(url, params, **kwargs):
        requests.append((params, kwargs))
        return {'elements': [way(1, 44.0005)]}
    source = SurfaceFetcher(request).fetch(track(), distance_step_m=100)
    assert source.data['axis'] == 'distance'
    assert source.data['records'][0]['values']['surface'] == 'asphalt'
    assert source.data['records'][1]['values']['surface'] is None
    assert source.data['provenance']['historical'] is False
    assert 'ODbL' in source.data['provenance']['attribution']
    assert requests[0][1] == {'post': True}
