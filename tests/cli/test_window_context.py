import json

import numpy as np
import pytest

from desnivel.cli.window_context import WindowContext
from desnivel.music.timeline import allocate_timeline
from desnivel.trip.local_context import LocalProfile
from desnivel.trip.track import Track, TrackSegment


def analysis():
    return dict(total_distance_m=200., config=dict(sample_distance_m=50, slope_window_m=100),
                zones=[dict(index=0, start_distance_m=0), dict(index=1, start_distance_m=100)],
                windows=[dict(start_distance_m=i*50, end_distance_m=(i+1)*50,
                              slope_ratio=.01 if i < 2 else .03, zone_index=int(i >= 2),
                              travel_segment_index=int(i >= 2)) for i in range(4)])


def track():
    return Track('test', np.array([0., 10., 10., 20.]),
                 {'cum_dist_m': np.array([0., 100., 100., 200.])}, segments=(
                     TrackSegment(0, 2, 100, 110, 0, 1),
                     TrackSegment(2, 4, 1000, 1010, 2, 3)))


def test_profile_measures_weighted_slope_and_persistence_without_crossing_recording_gap():
    profile = LocalProfile(analysis())
    current = profile.describe(75, 125)
    assert current['slope_ratio'] == pytest.approx(.02)
    assert current['coverage_ratio'] == 1
    assert current['zone_indices'] == [0, 1]
    assert current['zone_persistence_m'] == 0  # Il centro è all'ingresso della seconda zona.
    assert current['slope_change_ratio'] is None
    assert profile.describe(125, 150)['slope_change_ratio'] == pytest.approx(0)
    assert profile.describe(0, 25)['slope_change_ratio'] is None
    assert profile.describe(0, 0)['slope_ratio'] is None


def test_linear_projection_uses_lead_bpm_and_replay_speed_with_separate_source_parts():
    context = WindowContext(track(), analysis())
    value = context.linear(elapsed_s=8, live_beat=0, start_beat=2, length_beats=4, bpm=120, speed=1)
    assert value['start_active_s'] == 9 and value['end_active_s'] == 11
    assert [(p['source_start_unix'], p['source_end_unix']) for p in value['parts']] == [(109, 110), (1000, 1001)]
    assert [(p['start_distance_m'], p['end_distance_m']) for p in value['parts']] == [(90, 100), (100, 110)]
    assert value['profile']['slope_change_ratio'] is None
    faster = context.linear(elapsed_s=8, live_beat=0, start_beat=2, length_beats=4, bpm=240, speed=2)
    assert faster['parts'] == value['parts']
    assert faster['profile'] == value['profile']
    json.dumps(value, allow_nan=False)


def test_allocated_projection_is_shared_by_report_and_runtime_and_preserves_boundaries():
    context = WindowContext(track(), analysis())
    timeline = allocate_timeline([100, 100], target_beats=16, window_beats=4)
    sections = [dict(start_distance_m=0, end_distance_m=100), dict(start_distance_m=100, end_distance_m=200)]
    windows = [context.allocated(timeline, sections, i) for i in range(4)]
    assert [(w['start_distance_m'], w['end_distance_m']) for w in windows] == [(0, 50), (50, 100), (100, 150), (150, 200)]
    assert timeline.position(1, 1) == (0, 1)
    assert timeline.position(2) == (1, 0)
    assert windows[1]['parts'][0]['source_end_unix'] == 110
    assert windows[2]['parts'][0]['source_start_unix'] == 1000


def test_unavailable_tempo_profile_and_end_of_trip_are_explicit():
    context = WindowContext(track())
    args = dict(elapsed_s=0, live_beat=0, start_beat=4, length_beats=4, bpm=None, speed=1)
    assert context.linear(**args)['reason'] == 'tempo_unavailable'
    value = context.linear(**{**args, 'bpm': 120})
    assert value['profile'] == dict(status='unavailable', reason='analysis_not_configured')
    value = context.linear(**{**args, 'bpm': 120, 'elapsed_s': 17})
    assert value['truncated_at_finish'] and value['parts'][-1]['end_active_s'] == 20
    assert context.linear(**{**args, 'bpm': 120, 'elapsed_s': 20})['status'] == 'unavailable'
    with pytest.raises(ValueError):
        context.linear(**{**args, 'bpm': 0})
