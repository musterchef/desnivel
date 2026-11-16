from dataclasses import replace
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from desnivel.trip.analysis import analyze_track
from desnivel.settings import DEFAULT_CONFIG
from desnivel.trip.loader import load_track
from desnivel.trip.loader._travel import select_travel
from desnivel.trip.metrics import MetricName, build_metric_samples


def source(metres, times, elevation=None):
    n = len(metres)
    return {'lat': 45+np.asarray(metres, dtype=float)/111195., 'lon': np.full(n, 7.),
            'ele': np.asarray(elevation if elevation is not None else [100.]*n),
            't_unix': np.asarray(times, dtype=float), 'source_index': np.arange(1, n+1),
            'segment_index': np.ones(n, dtype=int)}


def write_gpx(tmp_path, raw):
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    points = ''.join(f'<trkpt lat="{lat}" lon="{lon}"><ele>{ele}</ele>'
                     f'<time>{(start+timedelta(seconds=float(t))).isoformat()}</time></trkpt>'
                     for lat, lon, ele, t in zip(raw['lat'], raw['lon'], raw['ele'], raw['t_unix']))
    path = tmp_path/'travel.gpx'
    path.write_text(f'<gpx xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>{points}</trkseg></trk></gpx>')
    return path


def test_missing_hour_is_not_resampled_and_does_not_invent_distance_or_slope(tmp_path):
    raw = source([0, 10, 1010, 1020], [0, 1, 3601, 3602], [100, 100, 500, 500])
    track = load_track(write_gpx(tmp_path, raw))
    assert track.duration_s == 2
    assert len(track.segments) == 2
    assert track.n_samples == 22
    assert track.samples['cum_dist_m'][-1] == pytest.approx(20, abs=.01)
    assert set(track.samples['ele']) == {100, 500}
    assert track.metadata['travel_selection']['observed_duration_s'] == 2
    gap, = track.metadata['travel_selection']['interruptions']
    assert gap['reason'] == 'recording_gap' and gap['duration_s'] == 3600
    config = {'sample_distance_m': 5, 'slope_window_m': 10, 'min_zone_distance_m': 5,
              'bands': [{'name': 'descent', 'from_slope_ratio': None},
                        {'name': 'level', 'from_slope_ratio': -.02},
                        {'name': 'ascent', 'from_slope_ratio': .02}]}
    analysis = analyze_track(track, config)
    assert {z['kind'] for z in analysis['zones']} == {'level'}
    assert all(z['elevation_delta_m'] == 0 for z in analysis['zones'])
    assert {p['travel_segment_index'] for p in analysis['profile']} == {0, 1}
    samples = build_metric_samples(track)
    assert [s.value for s in samples if s.name == MetricName.SLOPE_RATIO] == [0, 0]
    assert all(s.value == pytest.approx(36, abs=.01) for s in samples if s.name == MetricName.SPEED_KMH)


def test_recorded_hour_on_a_bench_is_excluded_before_channel_derivation(tmp_path, monkeypatch):
    from desnivel.trip.loader import track_loader
    positions = list(range(0, 101, 10))+[100]*3600+list(range(120, 321, 20))
    raw = source(positions, range(len(positions)))
    calls = []
    original = track_loader.derive_channels
    def derive(block, config):
        calls.append(len(block['lat']))
        return original(block, config)
    monkeypatch.setattr(track_loader, 'derive_channels', derive)
    track = load_track(write_gpx(tmp_path, raw))
    assert len(calls) == 2 and sum(calls) < 30
    assert track.duration_s < 30 and track.n_samples < 302
    assert any(g['reason'] == 'stationary' and g['duration_s'] >= 3600
               for g in track.metadata['travel_selection']['interruptions'])
    assert track.samples['cum_dist_m'][-1] == pytest.approx(320, abs=.01)


def test_walking_with_a_bike_is_kept_and_interrupted_sampling_at_rest_is_detected():
    raw = source(np.arange(181)*.5, np.arange(181))
    spans, selection = select_travel(raw, DEFAULT_CONFIG.gpx)
    assert spans == [(0, 181)] and selection['interruptions'] == []
    raw = source([0, 10, 10, 10, 20], [0, 1, 20, 40, 41])
    spans, selection = select_travel(raw, DEFAULT_CONFIG.gpx)
    assert spans == [(0, 2), (3, 5)]
    assert selection['interruptions'][0]['reason'] == 'sampling_pause'
    assert selection['interruptions'][0]['duration_s'] == 39


def test_slow_motion_is_not_a_pause_without_an_interruption_in_sampling():
    for cadence in (1, 5, 10):
        times = np.arange(0, 601, cadence)
        spans, result = select_travel(source(times*.3, times), DEFAULT_CONFIG.gpx)
        assert spans == [(0, len(times))]
        assert result['interruptions'] == []
        assert result['pause_inference']['pause_gap_threshold_s'] == max(8, cadence*3)


def test_a_sampling_gap_at_normal_travelling_speed_is_not_called_a_pause():
    times = [0, 1, 2, 12, 13]
    spans, result = select_travel(source(np.array(times)*5, times), DEFAULT_CONFIG.gpx)
    assert spans == [(0, 5)] and result['interruptions'] == []


def test_fit_timer_remains_authoritative_for_the_same_sparse_gps_samples():
    raw = source([0, 10, 10, 10, 20], [0, 1, 20, 40, 41])
    spans, result = select_travel(raw, DEFAULT_CONFIG.gpx, timer_intervals=[[0, 41]])
    assert spans == [(0, 5)]
    assert result['pause_inference'] == {}


def test_a_track_with_only_a_long_stop_is_not_used_as_a_journey():
    with pytest.raises(ValueError, match='nessun tratto'):
        select_travel(source([0]*121, range(121)), DEFAULT_CONFIG.gpx)


def test_missing_times_do_not_become_synthetic_travel():
    raw = source([0, 5, 10], [np.nan, np.nan, np.nan])
    with pytest.raises(ValueError, match='nessun tratto'):
        select_travel(raw, DEFAULT_CONFIG.gpx)


def test_clock_discontinuity_separates_segments_without_inventing_source_duration():
    spans, selection = select_travel(source([0, 10, 20, 30], [0, 1, 0, 1]), DEFAULT_CONFIG.gpx)
    assert spans == [(0, 2), (2, 4)]
    assert selection['source_duration_s'] is None
    assert selection['observed_duration_s'] == 2


def test_sparse_recording_cadence_can_be_configured_explicitly():
    raw = source([0, 100, 200], [0, 60, 120])
    with pytest.raises(ValueError, match='nessun tratto'):
        select_travel(raw, DEFAULT_CONFIG.gpx)
    spans, selection = select_travel(raw, replace(DEFAULT_CONFIG.gpx, recording_gap_s=120))
    assert spans == [(0, 3)] and selection['observed_duration_s'] == 120


def test_metric_window_crossing_a_join_does_not_mix_two_elevations(tmp_path):
    raw = source([0, 15, 1015, 1030], [0, 1.5, 3601.5, 3603], [100, 100, 500, 500])
    track = load_track(write_gpx(tmp_path, raw))
    samples = build_metric_samples(track)
    assert [s.elapsed_s for s in samples if s.name == MetricName.SPEED_KMH] == [1, 3]
    assert all(s.value == 0 for s in samples if s.name == MetricName.SLOPE_RATIO)
