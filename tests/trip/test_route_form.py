"""Forma neutra della tappa, senza decisioni musicali o percentuali fisse."""
import numpy as np
import pytest

from desnivel.trip.route_form import describe_route_form
from desnivel.trip.track import Track
from desnivel.settings import RouteStructureSettings


SETTINGS = RouteStructureSettings(True, .2, .2, 400, 1)


def track():
    distance = np.arange(0, 601, 100, dtype=float)
    return Track('test', np.array([0., 10., 25., 45., 70., 100., 135.]),
                 {'cum_dist_m': distance, 'ele': np.array([100., 110., 120., 120., 110., 105., 115.])})


def section(index, kind, start, end, delta):
    return {'index': index, 'kind': kind, 'start_distance_m': start, 'end_distance_m': end,
            'elevation_delta_m': delta, 'mean_slope_ratio': delta/(end-start)}


def test_route_form_preserves_spans_and_derives_turning_events_from_the_profile():
    form = describe_route_form(track(), [
        section(0, 'ascent', 0, 200, 20),
        section(1, 'descent', 200, 500, -15),
        section(2, 'ascent', 500, 600, 10),
    ], SETTINGS)
    assert [span['trend'] for span in form['spans']] == ['rising', 'falling', 'rising']
    assert [event['type'] for event in form['events']] == [
        'departure', 'summit', 'valley', 'arrival'
    ]
    assert form['spans'][0]['active_duration_s'] == 25
    assert form['spans'][1]['active_duration_s'] == 75
    assert form['events'][1]['at_distance_m'] == 200
    assert form['events'][1]['at_active_s'] == 25


def test_level_and_observation_gaps_are_explicit_without_inventing_summits():
    form = describe_route_form(track(), [
        section(0, 'up', 0, 200, 20),
        section(1, 'flat', 200, 300, 0),
        section(2, 'down', 400, 500, -10),
    ], SETTINGS)
    assert [event['type'] for event in form['events']] == [
        'departure', 'profile_change', 'observation_gap', 'arrival'
    ]


@pytest.mark.parametrize('sections', [[], [section(0, 'bad', -1, 100, 1)],
                                       [section(0, 'bad', 0, 700, 1)]])
def test_route_form_rejects_missing_or_invalid_spans(sections):
    with pytest.raises(ValueError):
        describe_route_form(track(), sections, SETTINGS)
