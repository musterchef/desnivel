"""Verifica delle zone geometriche e della persistenza dei cambi."""
import json
from pathlib import Path

import numpy as np
import pytest

from desnivel.trip.analysis import analyze_track
from desnivel.trip.track import Track


CONFIG = {
    'sample_distance_m': 100, 'slope_window_m': 100, 'min_zone_distance_m': 300,
    'bands': [{'name': 'descent', 'from_slope_ratio': None},
              {'name': 'level', 'from_slope_ratio': -.01},
              {'name': 'climb', 'from_slope_ratio': .01},
              {'name': 'steep_climb', 'from_slope_ratio': .06}],
}


def track_for(slopes):
    distance = np.arange(len(slopes)+1, dtype=float)*100
    return Track('test', np.arange(len(distance), dtype=float),
                 {'cum_dist_m': distance, 'ele': 200+np.r_[0, np.cumsum(slopes)*100]})


def test_persistent_changes_follow_terrain_and_cover_entire_track():
    result = analyze_track(track_for([0]*3+[.04]*4+[.08]*3+[-.04]*4), CONFIG)
    zones = result['zones']
    assert [z['kind'] for z in zones] == ['level', 'climb', 'steep_climb', 'descent']
    assert [z['start_distance_m'] for z in zones] == [0, 300, 700, 1000]
    assert [z['end_distance_m'] for z in zones] == [300, 700, 1000, 1400]
    assert zones[-1]['until_progress'] == 1
    assert zones[1]['elevation_delta_m'] == pytest.approx(16)
    assert zones[1]['mean_slope_ratio'] == pytest.approx(.04)
    assert len(result['windows']) == 14


def test_brief_change_and_unconfirmed_tail_remain_visible_in_evidence():
    result = analyze_track(track_for([0]*3+[.08]+[0]*3+[-.04]*2), CONFIG)
    assert [z['kind'] for z in result['zones']] == ['level']
    assert result['windows'][3]['observed_kind'] == 'steep_climb'
    assert result['windows'][-1]['observed_kind'] == 'descent'
    assert all(w['zone_index'] == 0 for w in result['windows'])
    assert result['zones'][0]['matching_distance_ratio'] == pytest.approx(6/9)


def test_wider_observation_window_smooths_a_short_elevation_peak():
    track = track_for([0]*3+[.08, -.08]+[0]*3)
    narrow = analyze_track(track, CONFIG)
    wide = analyze_track(track, {**CONFIG, 'slope_window_m': 800})
    assert max(abs(w['slope_ratio']) for w in narrow['windows']) == pytest.approx(.08)
    assert max(abs(w['slope_ratio']) for w in wide['windows']) < .02


def test_thresholds_and_names_come_from_configuration():
    config = {**CONFIG, 'bands': [{'name': 'below', 'from_slope_ratio': None},
                                 {'name': 'above', 'from_slope_ratio': .03}]}
    assert analyze_track(track_for([.04]*4), config)['zones'][0]['kind'] == 'above'
    config['bands'][1]['from_slope_ratio'] = .05
    assert analyze_track(track_for([.04]*4), config)['zones'][0]['kind'] == 'below'


def test_short_route_and_partial_last_window_are_preserved():
    track = Track('short', np.array([0., 1.]),
                  {'cum_dist_m': np.array([50., 175.]), 'ele': np.array([100., 105.])})
    result = analyze_track(track, CONFIG)
    assert result['total_distance_m'] == 125
    assert result['windows'][-1]['end_distance_m'] == 125
    assert len(result['zones']) == 1


def test_stationary_points_use_last_elevation_at_same_distance():
    track = Track('stops', np.arange(4.),
                  {'cum_dist_m': np.array([0., 100., 100., 200.]),
                   'ele': np.array([100., 100., 102., 104.])})
    result = analyze_track(track, CONFIG)
    assert [w['slope_ratio'] for w in result['windows']] == pytest.approx([.02, .02])


@pytest.mark.parametrize('samples', [
    {'cum_dist_m': np.array([0., 100.])},
    {'cum_dist_m': np.array([0., 100.]), 'ele': np.array([0., np.nan])},
    {'cum_dist_m': np.array([100., 0.]), 'ele': np.array([0., 10.])},
    {'cum_dist_m': np.array([0., 0.]), 'ele': np.array([0., 10.])},
])
def test_unavailable_or_invalid_geometry_is_rejected(samples):
    with pytest.raises(ValueError):
        analyze_track(Track('invalid', np.array([0., 1.]), samples), CONFIG)


@pytest.mark.parametrize('changes', [
    {'sample_distance_m': 0}, {'min_zone_distance_m': float('nan')},
    {'slope_window_m': True}, {'bands': []},
    {'bands': [{'name': 'x', 'from_slope_ratio': 0}]},
    {'bands': [{'name': 'x', 'from_slope_ratio': None}, {'name': 'x', 'from_slope_ratio': 1}]},
    {'bands': [{'name': 'x', 'from_slope_ratio': None},
               {'name': 'y', 'from_slope_ratio': 1}, {'name': 'z', 'from_slope_ratio': 0}]},
])
def test_invalid_configuration_is_rejected(changes):
    with pytest.raises(ValueError):
        analyze_track(track_for([0]*4), {**CONFIG, **changes})


def test_cli_writes_reproducible_analysis_without_music(tmp_path, capsys):
    from desnivel.cli.analyze_trip import main

    root = Path(__file__).resolve().parents[2]
    output = tmp_path/'analysis.json'
    args = ['--gpx', str(root/'gpx/tappa05_Firenze_San_Gimignano.gpx'),
            '--settings', str(root/'settings/desnivel.toml'), '--output', str(output)]
    assert main(args) == 0
    first = output.read_text()
    assert main(args) == 0
    assert output.read_text() == first
    result = json.loads(first)
    assert result['zones'][-1]['until_progress'] == 1
    assert result['total_distance_m'] > 1000
    assert 'Pendenza media' in capsys.readouterr().out


@pytest.mark.parametrize('slopes, expected_starts, expected_kinds', [
    ([0]+[.04]*3, [0, 100], ['level', 'climb']),
    ([0]*2+[.04]*2+[.08]*2+[.04]*3, [0, 600], ['level', 'climb']),
    ([0]*3+[.04]*2+[0]+[.04]*3, [0, 600], ['level', 'climb']),
    ([0]*3+[.04]*3+[.08]*2+[.04]*3, [0, 300], ['level', 'climb']),
    ([0]*3+[.04]*3+[-.04]*3+[.04]*3, [0, 300, 600, 900],
     ['level', 'climb', 'descent', 'climb']),
])
def test_persistence_keeps_candidate_resets_and_short_initial_zones(
        slopes, expected_starts, expected_kinds):
    zones = analyze_track(track_for(slopes), CONFIG)['zones']
    assert [z['start_distance_m'] for z in zones] == expected_starts
    assert [z['kind'] for z in zones] == expected_kinds


def test_confirmation_counts_actual_distance_of_partial_last_interval():
    track = Track('partial', np.arange(4.),
                  {'cum_dist_m': np.array([0., 100., 200., 225.]),
                   'ele': np.array([100., 100., 104., 105.])})
    confirmed = analyze_track(track, {**CONFIG, 'min_zone_distance_m': 125})
    assert [z['start_distance_m'] for z in confirmed['zones']] == [0, 100]
    unconfirmed = analyze_track(track, {**CONFIG, 'min_zone_distance_m': 126})
    assert len(unconfirmed['zones']) == 1


def test_many_alternating_zones_preserve_boundaries_and_perfect_matching():
    count = 4000
    slopes = np.where(np.arange(count) % 2, -.04, .04)
    result = analyze_track(track_for(slopes), {**CONFIG, 'min_zone_distance_m': 100})
    assert len(result['zones']) == count
    assert [z['start_distance_m'] for z in result['zones']] == list(range(0, count*100, 100))
    assert all(z['matching_distance_ratio'] == 1 for z in result['zones'])
    assert [w['zone_index'] for w in result['windows']] == list(range(count))


def test_sub_resolution_slope_window_is_rejected_instead_of_classifying_nan():
    with pytest.raises(ValueError, match='non rappresentabili'):
        analyze_track(track_for([.04]*4), {**CONFIG, 'slope_window_m': 1e-20})


def test_overflowing_distance_extent_is_rejected():
    track = Track('overflow', np.array([0., 1.]),
                  {'cum_dist_m': np.array([-1e308, 1e308]), 'ele': np.array([0., 1.])})
    with pytest.raises(ValueError, match='estensione'):
        analyze_track(track, CONFIG)


def test_decimal_step_does_not_duplicate_the_final_boundary():
    track = Track('decimal', np.array([0., 1.]),
                  {'cum_dist_m': np.array([0., 561.6]), 'ele': np.array([100., 110.])})
    result = analyze_track(track, {**CONFIG, 'sample_distance_m': .3})
    assert len(result['windows']) == 1872
    assert all(w['end_distance_m'] > w['start_distance_m'] for w in result['windows'])
    assert result['windows'][-1]['end_distance_m'] == 561.6
    assert all(a['distance_m'] < b['distance_m'] for a, b in zip(result['profile'], result['profile'][1:]))


def test_tiny_route_still_has_a_single_interval_when_step_exceeds_its_length():
    track = Track('tiny', np.array([0., 1.]),
                  {'cum_dist_m': np.array([0., 1e-300]), 'ele': np.array([100., 100.])})
    result = analyze_track(track, {**CONFIG, 'sample_distance_m': 1e300})
    assert len(result['windows']) == len(result['zones']) == 1
    assert result['windows'][0]['end_distance_m'] == 1e-300
    assert result['zones'][0]['mean_slope_ratio'] == 0


@pytest.mark.parametrize('config', [None, [], {**CONFIG, 'bands': [None]}])
def test_malformed_config_has_an_explicit_validation_error(config):
    with pytest.raises(ValueError):
        analyze_track(track_for([0]*4), config)
