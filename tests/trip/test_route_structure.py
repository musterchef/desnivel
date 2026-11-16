import pytest

from desnivel.settings import RouteStructureSettings
from desnivel.trip.route_structure import derive_route_episodes


SETTINGS = RouteStructureSettings(True, .2, .2, 400, 1)


def span(index, trend, start, end, delta):
    return {
        'index': index, 'source_kind': trend, 'trend': trend,
        'start_distance_m': start, 'end_distance_m': end, 'distance_m': end-start,
        'start_active_s': start, 'end_active_s': end, 'active_duration_s': end-start,
        'elevation_delta_m': delta, 'mean_slope_ratio': delta/(end-start),
    }


def test_small_recovered_reversal_is_merged_but_large_final_change_remains():
    episodes = derive_route_episodes([
        span(0, 'rising', 0, 200, 20), span(1, 'falling', 200, 250, -2),
        span(2, 'rising', 250, 500, 15), span(3, 'falling', 500, 900, -30),
    ], SETTINGS)
    assert [episode['trend'] for episode in episodes] == ['rising', 'falling']
    assert episodes[0]['span_indices'] == [0, 1, 2]
    assert episodes[0]['elevation_delta_m'] == 33
    assert episodes[0]['local_variations'] == [{
        'trend': 'falling', 'start_distance_m': 200, 'end_distance_m': 250,
        'distance_m': 50, 'elevation_delta_m': -2, 'span_indices': [1],
    }]


def test_reversal_requires_recovery_and_local_ratios():
    spans = [span(0, 'rising', 0, 200, 20), span(1, 'falling', 200, 250, -10),
             span(2, 'rising', 250, 500, 5)]
    assert len(derive_route_episodes(spans, SETTINGS)) == 3


@pytest.mark.parametrize('values', [
    (1, .2, .2, 400, 1), (True, 1, .2, 400, 1), (True, .2, 0, 400, 1),
])
def test_invalid_structure_settings_are_rejected(values):
    with pytest.raises(ValueError, match='route_structure|rapporti relativi'):
        RouteStructureSettings(*values)


def test_merging_can_be_disabled_without_losing_same_direction_continuity():
    settings = RouteStructureSettings(False, .2, .2, 400, 1)
    episodes = derive_route_episodes([
        span(0, 'rising', 0, 100, 10), span(1, 'rising', 100, 200, 10),
        span(2, 'falling', 200, 210, -1), span(3, 'rising', 210, 300, 10),
    ], settings)
    assert [episode['span_indices'] for episode in episodes] == [[0, 1], [2], [3]]


def test_absolute_distance_limit_preserves_a_perceptible_variation():
    episodes = derive_route_episodes([
        span(0, 'rising', 0, 2000, 200), span(1, 'falling', 2000, 2500, -20),
        span(2, 'rising', 2500, 4000, 100),
    ], SETTINGS)
    assert len(episodes) == 3
