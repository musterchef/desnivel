from copy import deepcopy
import json
from pathlib import Path

import pytest

from desnivel.music.sequence.adaptation import pulse, targets
from desnivel.music.sequence.settings import validate_music
from desnivel.music.automation import AdaptiveContext
from desnivel.adapters.snake_control import validate_paths


@pytest.fixture
def music():
    return json.loads((Path(__file__).resolve().parents[3]/'presets/snake.json').read_text())['music']


@pytest.mark.parametrize('path,value', [
    (('roles','melody','parameters','activity'), 1.1),
    (('roles','melody','parameters','velocity'), True),
    (('roles','melody','parameters','octave'), .5),
    (('roles','melody','pulse','fastest'), '64n'),
    (('roles','melody','response','activity'), float('nan')),
    (('roles','melody','response','unknown'), 0),
    (('adaptation','transition_beats'), 0),
    (('roles','melody','pulse','fastest'), '2n'),
    (('roles','melody','pulse','slowest'), '32n'),
    (('roles','melody','pulse','intense_threshold'), .1),
    (('phrasing','accents'), []),
    (('phrasing','accents'), [2]),
    (('phrasing','length_accent'), -1),
])
def test_invalid_recipes_report_the_configuration_path(music, path, value):
    target = music
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError, match='music'):
        validate_music(music)


def test_misspelled_fields_identify_both_missing_and_unknown_names(music):
    parameters = music['roles']['melody']['parameters']
    parameters['activty'] = parameters.pop('activity')
    with pytest.raises(ValueError) as error:
        validate_music(music)
    assert str(error.value) == ('music.roles.melody.parameters: campi mancanti: activity; '
                                'campi sconosciuti: activty')


@pytest.mark.parametrize('paths', [[], [0], [15], [True], [1,1], '1'])
def test_invalid_device_paths_are_rejected(paths):
    with pytest.raises(ValueError, match='paths'):
        validate_paths(paths)


def test_recipe_keeps_role_responses_and_missing_context_neutral(music):
    original = deepcopy(music)
    validate_music(music)
    for role, spec in music['roles'].items():
        base = spec['parameters']
        neutral = targets(role, AdaptiveContext(), 4, music)
        assert {name: target.value for name,target in neutral.items()} == {
            name:base[name] for name in neutral}
        assert pulse(AdaptiveContext(), spec['pulse']) == spec['pulse']['slowest']
    assert music == original


def test_role_pulse_ranges_can_be_changed_without_affecting_other_roles(music):
    settings = music['roles']['melody']['pulse']
    assert pulse(AdaptiveContext(intensity=1.), settings) == '16n'
    settings.update(fastest='32n', slowest='2n')
    validate_music(music)
    assert pulse(AdaptiveContext(intensity=.5), settings) == '8n'
    assert pulse(AdaptiveContext(intensity=1.), settings) == '32n'
    assert pulse(AdaptiveContext(intensity=0.), settings) == '2n'
    assert music['roles']['bass_line']['pulse'] == dict(slowest='4n', fastest='16n')


@pytest.mark.parametrize('intensity,expected', [(0.,'2n'), (.24,'4n'), (.5,'8n'), (.76,'16n'), (1.,'32n')])
def test_pulse_is_selected_directly_from_intensity_across_the_allowed_subdivisions(intensity, expected):
    assert pulse(AdaptiveContext(intensity=intensity), dict(slowest='2n',fastest='32n')) == expected


def test_equal_pulse_limits_keep_a_fixed_subdivision(music):
    settings = music['roles']['melody']['pulse']
    settings.update(slowest='8n',fastest='8n')
    validate_music(music)
    for intensity in (0.,.5,1.):
        assert pulse(AdaptiveContext(intensity=intensity), settings) == '8n'
