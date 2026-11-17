"""Profilo GPX, tavolozza, materiale, override e generazione multivoce."""
import json
from pathlib import Path

import numpy as np
import pytest

from desnivel.adapters.voice_device import VoiceDeviceBridge
from desnivel.cli.ensemble_runtime import EnsembleRuntime
from desnivel.cli.trip_direction import prepare_trip_config
from desnivel.music.harmony import choose_context, pitch_classes, validate_palettes
from desnivel.music.patterns import SCALES
from desnivel.trip.loader import load_track
from desnivel.trip.track import Track
from desnivel.trip.profile import describe_profile


DIRECTION = Path('presets/direzione-viaggio.json')


def config():
    session = json.loads(Path('tests/fixtures/transport_runtime_session.json').read_text())
    session['generators']['percussion'] = json.loads(Path('tests/fixtures/percussion_phrase.json').read_text())
    session['voices']['voice_04'] = {
        'name': 'Drums', 'generator': 'percussion', 'destination': 'device_04',
        'dependencies': ['voice_01'], 'optional_dependencies': ['voice_02'],
    }
    session['rhythm_voice'] = 'voice_04'
    session['generators']['motif']['settings']['groove_follow'] = .3
    session['generators']['accompaniment']['settings']['groove_follow'] = .7
    return session


def track(stage='test', amplitude=1.):
    slopes = np.array([0., .02, -.02, .08, .08, -.06, 0., -.01]*5)*amplitude
    distances = np.arange(len(slopes)+1)*100.
    return Track(stage, np.arange(len(distances), dtype=float),
                 {'cum_dist_m': distances, 'ele': 100+np.r_[0., np.cumsum(slopes)*100]})


@pytest.fixture
def direction(tmp_path):
    data = json.loads(DIRECTION.read_text())
    path = tmp_path/'direction.json'
    path.write_text(json.dumps(data))
    return path


def test_same_geometry_is_reproducible_and_independent_of_the_stage_name():
    original = config()
    a = prepare_trip_config(track(), original, DIRECTION)
    b = prepare_trip_config(track('renamed'), original, DIRECTION)
    assert a['sections'] == b['sections']
    assert a['generators'] == b['generators']
    assert a['trip_music']['motif_degrees'] == b['trip_music']['motif_degrees']
    assert original == config()
    assert len(a['trip_music']['motif_degrees']) == 8
    assert a['generators']['motif']['degrees'] != original['generators']['motif']['degrees']
    states = [(s['root'], s['scale']) for s in a['sections']]
    assert len(set(states)) > 1
    assert all(len(pitch_classes(*x) & pitch_classes(*y)) >= 3 for x, y in zip(states, states[1:]))


@pytest.mark.parametrize('filename,palette', [
    ('tappa04_Levanto_La_Spezia.gpx', 'steep'),
    ('tappa05_Firenze_San_Gimignano.gpx', 'rolling'),
    ('tappa10_San_Nicola_Manfredi_San_Severo.gpx', 'gentle'),
])
def test_real_stages_select_distinct_palettes_and_use_the_resolved_material(filename, palette):
    source = load_track(Path('gpx')/filename)
    resolved = prepare_trip_config(source, config(), DIRECTION)
    assert resolved['trip_music']['palette'] == palette
    bridge = VoiceDeviceBridge({}, lambda *args: None, clock=lambda: 0.)
    runtime = EnsembleRuntime(source, resolved, bridge, clock=lambda: 0.)
    assert runtime.registry['voice_01'].generator.generate.degrees == tuple(resolved['trip_music']['motif_degrees'])
    runtime.session.set_parameter('voice_01', 'development', 0)
    phrases = runtime.session.plan(0, 0, 4)
    context = runtime.session.director.context_at(0)
    expected = [context.root+SCALES[context.scale][d % len(SCALES[context.scale])]
                +12*(d//len(SCALES[context.scale])) for d in resolved['trip_music']['motif_degrees'][:4]]
    # step_beats può essere diverso nell'assetto della prima macrosezione.
    assert phrases['voice_01'].notes[0].pitch == expected[0]
    assert phrases['voice_03'].notes[0].pitch == context.root+12
    assert (context.root, context.scale) != (57, 'minor')
    assert runtime.snapshot()['trip_music']['palette'] == palette
    assert runtime.snapshot()['section']['direction']['sources']['root'] == 'profile'
    json.dumps(runtime.snapshot(), allow_nan=False)
    for i, section in enumerate(resolved['sections'][1:], start=1):
        runtime.session.plan(section['from_progress'], i*4, 4)


def test_overrides_apply_to_palette_harmony_and_material_with_stage_priority(direction):
    data = json.loads(direction.read_text())
    data['automatic_music']['override'] = {'palette': 'gentle', 'root': 48, 'scale': 'major', 'motif_degrees': [0, 2, 4]}
    data['automatic_music']['stage_overrides'] = {'test': {'palette': 'steep', 'root': 62, 'scale': 'phrygian', 'motif_degrees': [0, 1, 3, 2]}}
    data['families']['level']['root'] = 60
    direction.write_text(json.dumps(data))
    resolved = prepare_trip_config(track(), config(), direction)
    assert resolved['trip_music']['palette'] == 'steep'
    assert resolved['generators']['motif']['degrees'] == [0, 1, 3, 2]
    assert all((s['root'], s['scale']) == (62, 'phrygian') for s in resolved['sections'])
    assert all(s['direction']['sources'] == {'root': 'stage_override', 'scale': 'stage_override'} for s in resolved['sections'])
    runtime = EnsembleRuntime(track(), resolved, VoiceDeviceBridge({}, lambda *args: None))
    phrase = runtime.session.plan(0, 0, 4)
    assert phrase['voice_01'].notes[0].pitch == 62
    assert phrase['voice_03'].notes[0].pitch == 74
    runtime.session.set_presence_multiplier('voice_01', 0)
    phrase = runtime.session.plan(0, 4, 4)
    assert not phrase['voice_01'].notes
    assert phrase['voice_02'].notes[0].pitch % 12 == 62 % 12
    other = prepare_trip_config(track('other'), config(), direction)
    assert other['trip_music']['palette'] == 'gentle'
    assert all((s['root'], s['scale']) == (48, 'major') for s in other['sections'])
    assert other['generators']['motif']['degrees'] == [0, 2, 4]


def test_family_override_does_not_leak_to_other_families(direction):
    data = json.loads(direction.read_text())
    data['families']['level'].update(root=60, scale='lydian')
    direction.write_text(json.dumps(data))
    result = prepare_trip_config(track(), config(), direction)
    assert any(s['name'] != 'level' for s in result['sections'])
    for section in result['sections']:
        if section['name'] == 'level':
            assert section['root'] == 60 and section['scale'] == 'lydian'
            assert section['direction']['sources']['root'] == 'family'
        else:
            assert section['root'] == section['direction']['automatic_root']
            assert section['scale'] == section['direction']['automatic_scale']


@pytest.mark.parametrize('problem', ['palette', 'root', 'scale', 'motif', 'field', 'target', 'threshold', 'states', 'null'])
def test_invalid_policy_fails_explicitly_before_runtime(direction, problem):
    data = json.loads(direction.read_text())
    automatic = data['automatic_music']
    if problem == 'palette':
        automatic['override'] = {'palette': 'missing'}
    elif problem == 'root':
        automatic['override'] = {'root': 128}
    elif problem == 'scale':
        automatic['stage_overrides'] = {'unused': {'scale': 'missing'}}
    elif problem == 'motif':
        automatic['override'] = {'motif_degrees': []}
    elif problem == 'field':
        automatic['override'] = {'seed': 4}
    elif problem == 'target':
        automatic['motif']['generators'] = ['accompaniment']
    elif problem == 'threshold':
        automatic['palettes'][0]['from_mean_absolute_slope_ratio'] = .1
    elif problem == 'states':
        automatic['palettes'][0]['states'][1]['scale'] = 'chromatic'
        automatic['palettes'][0]['states'][1]['intensity'] = 0
    else:
        data['automatic_music'] = None
    direction.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        prepare_trip_config(track(), config(), direction)


def test_hysteresis_keeps_small_changes_but_allows_a_clear_new_context():
    settings = json.loads(DIRECTION.read_text())['automatic_music']
    validate_palettes(settings['palettes'], settings['switch_margin'])
    palette = settings['palettes'][1]
    a = choose_context(palette, .5, None, .15)
    b = choose_context(palette, .3, a, .15)
    assert b == a
    c = choose_context(palette, 0, b, .15)
    assert c['id'] == 'home'


def test_flat_profile_has_defined_material_and_distance_weighting():
    analysis = {'total_distance_m': 100., 'windows': [
        {'start_distance_m': 0., 'end_distance_m': 25., 'elevation_m': 10., 'slope_ratio': .04},
        {'start_distance_m': 25., 'end_distance_m': 100., 'elevation_m': 10., 'slope_ratio': 0.},
    ]}
    profile = describe_profile(analysis)
    assert profile['mean_absolute_slope_ratio'] == pytest.approx(.01)
    assert profile['shape_normalized'] == [.5]*8


def test_default_direction_and_explicit_manual_sections_are_both_operational(tmp_path, capsys):
    from desnivel.cli.ensemble import main
    session = config()
    session['direction'] = str(DIRECTION.resolve())
    path = tmp_path/'session.json'
    path.write_text(json.dumps(session))
    args = ['--gpx', 'gpx/tappa05_Firenze_San_Gimignano.gpx', '--config', str(path), '--dry-run']
    assert main(args) == 0
    automatic = capsys.readouterr().out
    assert 'Direzione GPX: rolling' in automatic
    assert 'root 55' in automatic and 'root 50' in automatic
    assert main(args+['--timing', 'allocated']) == 0
    assert 'Timeline allocated:' in capsys.readouterr().out
    assert main(args+['--manual-sections']) == 0
    manual = capsys.readouterr().out
    assert 'Direzione GPX' not in manual and 'opening' in manual and '[km ' not in manual
