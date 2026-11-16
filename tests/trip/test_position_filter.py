from dataclasses import replace
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from desnivel.settings import DEFAULT_CONFIG
from desnivel.trip.loader import load_track
from desnivel.trip.loader._filter import filter_position_spikes
from desnivel.trip.metrics import MetricName, build_metric_samples
from desnivel.trip.track import Track


def source(metres, times=None):
    n = len(metres)
    return {'lat': 45+np.asarray(metres)/111195., 'lon': np.full(n, 7.),
            'ele': np.full(n, 100.), 't_unix': np.asarray(times if times is not None else range(n), dtype=float),
            'source_index': np.arange(1, n+1), 'segment_index': np.ones(n, dtype=int)}


def test_short_excursion_is_removed_and_original_time_and_neighbors_are_preserved():
    raw = source([0, 5, 500, 500, 20, 25])
    copy = {key: values.copy() for key, values in raw.items()}
    filtered, valid, report = filter_position_spikes(raw, DEFAULT_CONFIG.gpx)
    assert filtered['source_index'].tolist() == [1, 2, 5, 6]
    assert filtered['t_unix'].tolist() == [0, 1, 4, 5]
    assert valid.all()
    reconnection, = report['reconnections']
    assert reconnection['removed_source_indices'] == [3, 4]
    assert reconnection['duration_s'] == 3
    assert reconnection['reconnected_speed_kmh'] == pytest.approx(18, abs=.01)
    assert report['unresolved_intervals'] == []
    for key in raw:
        np.testing.assert_equal(raw[key], copy[key])


def test_persistent_position_step_is_not_repaired_by_erasing_more_points():
    raw = source([0, 5, 500, 505, 510, 515])
    filtered, valid, report = filter_position_spikes(raw, DEFAULT_CONFIG.gpx)
    assert filtered['source_index'].tolist() == list(range(1, 7))
    assert valid.tolist() == [True, True, False, True, True, True]
    assert report['removed_points'] == 0
    assert report['unresolved_intervals'][0]['reason'] == 'above_speed_limit'


def test_normal_fast_movement_and_turns_are_unchanged():
    raw = source([0, 18, 0, 18, 36])  # 64,8 km/h, compreso il ritorno.
    filtered, valid, report = filter_position_spikes(raw, DEFAULT_CONFIG.gpx)
    assert valid.all() and report['removed_points'] == 0
    for key in raw:
        np.testing.assert_equal(filtered[key], raw[key])


@pytest.mark.parametrize('settings', [{'spike_max_removed_points': 1}, {'spike_max_gap_s': 2}])
def test_local_limits_prevent_reconnection_across_a_long_or_large_gap(settings):
    raw = source([0, 5, 500, 500, 20, 25])
    _, _, report = filter_position_spikes(raw, replace(DEFAULT_CONFIG.gpx, **settings))
    assert report['removed_points'] == 0
    assert len(report['unresolved_intervals']) == 2


def test_segments_and_missing_times_cannot_be_bridged():
    raw = source([0, 5, 500, 500, 20, 25])
    raw['segment_index'][3:] = 2
    raw['t_unix'][2] = np.nan
    _, valid, report = filter_position_spikes(raw, DEFAULT_CONFIG.gpx)
    assert report['removed_points'] == 0 and not valid.all()


def test_sparse_return_excursion_can_be_checked_without_erasing_a_stop():
    raw = source([0, 0, 0, 120, 35, 35], [0, 1, 2, 41, 44, 45])
    filtered, valid, report = filter_position_spikes(raw, DEFAULT_CONFIG.gpx)
    assert report['reconnections'][0]['removed_source_indices'] == [4]
    assert report['reconnections'][0]['duration_s'] == 42
    assert filtered['t_unix'].tolist() == [0, 1, 2, 44, 45]
    assert filtered['lat'][:3].tolist() == raw['lat'][:3].tolist()
    assert valid.all()
    _, _, limited = filter_position_spikes(raw, replace(DEFAULT_CONFIG.gpx, spike_max_gap_s=30))
    assert limited['removed_points'] == 0


def test_long_stationary_period_and_regular_restart_are_preserved():
    raw = source([0, 0, 0, 0, 5, 10], [0, 20, 40, 60, 61, 62])
    filtered, valid, report = filter_position_spikes(raw, DEFAULT_CONFIG.gpx)
    assert valid.all() and report['removed_points'] == 0
    for key in raw:
        np.testing.assert_equal(filtered[key], raw[key])


def test_loader_marks_only_the_unresolved_interval_without_clamping_or_spreading_nan(tmp_path):
    raw = source([0, 5, 500, 505, 510])
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    points = ''.join(f'<trkpt lat="{lat}" lon="7"><ele>100</ele>'
                     f'<time>{(start+timedelta(seconds=i)).isoformat()}</time></trkpt>'
                     for i, lat in enumerate(raw['lat']))
    path = tmp_path/'jump.gpx'
    path.write_text(f'<gpx xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>{points}</trkseg></trk></gpx>')
    track = load_track(path)
    missing = (track.t > 1) & (track.t <= 2)
    assert np.isnan(track.samples['speed_kmh'][missing]).all()
    assert np.isfinite(track.samples['speed_kmh'][~missing]).all()
    assert np.nanmax(track.samples['speed_kmh']) < 70
    assert track.metadata['unavailable_motion_intervals'] == [[1, 2]]
    assert track.duration_s == 4


def test_metrics_do_not_recreate_speed_from_unresolved_cumulative_distance():
    track = Track('gap', np.array([0., 1., 2., 3.]),
                  {'cum_dist_m': np.array([0., 10., 500., 510.]), 'ele': np.full(4, 100.)},
                  {'unavailable_motion_intervals': [[1., 2.]]})
    samples = build_metric_samples(track)
    assert [s.elapsed_s for s in samples if s.name == MetricName.SPEED_KMH] == [1, 3]
    assert all(s.value == pytest.approx(36) for s in samples if s.name == MetricName.SPEED_KMH)
    assert not any(s.elapsed_s == 2 and s.name in (MetricName.DISTANCE_DELTA_M, MetricName.SLOPE_RATIO,
                                                MetricName.EFFORT_ESTIMATE) for s in samples)
    assert any(s.elapsed_s == 2 and s.name == MetricName.DISTANCE_TOTAL_M for s in samples)
