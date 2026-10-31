"""Collegamento GPX → macrosezioni → assegnazioni e pianificazione musicale."""
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

from desnivel.adapters.voice_device import VoiceDeviceBridge
from desnivel.cli.ensemble_runtime import EnsembleRuntime
from desnivel.cli.trip_direction import load_trip_sections
from desnivel.trip.track import Track


def legacy_direction():
    definition = json.loads(Path('presets/direzione-viaggio.json').read_text())
    definition.pop('automatic_music')
    for family in definition['families'].values():
        family.update(root=57, scale='minor')
    return definition


@pytest.fixture
def direction(tmp_path):
    definitions = Path('presets')
    definition = legacy_direction()
    for family in definition['families'].values():
        for assignment in family['assignments'].values():
            assignment['presence'] = 1  # Le prove musicali isolano sviluppo e interazione.
    analysis = json.loads((definitions/'analisi-percorso.json').read_text())
    analysis.update(slope_window_m=100, min_zone_distance_m=100)
    (tmp_path/'analisi-percorso.json').write_text(json.dumps(analysis))
    (tmp_path/'macrosezioni-percorso.json').write_text((definitions/'macrosezioni-percorso.json').read_text())
    path = tmp_path/'direction.json'
    path.write_text(json.dumps(definition))
    return path


def track():
    slopes = [.04]*3+[.08]*3+[0.]*3+[-.04]*3+[.04]*6
    distance = np.arange(len(slopes)+1, dtype=float)*100
    return Track('test', np.arange(len(distance), dtype=float),
                 {'cum_dist_m': distance, 'ele': 200+np.r_[0, np.cumsum(slopes)*100]})


def make_runtime(direction):
    config = json.loads(Path('presets/organico.json').read_text())
    config['sections'] = load_trip_sections(track(), direction)
    sent = []
    bridge = VoiceDeviceBridge({}, lambda *args: sent.append(args), clock=lambda: 0.)
    runtime = EnsembleRuntime(track(), config, bridge, clock=lambda: 0.)
    return runtime, bridge, sent


def test_boundaries_follow_macrosections_and_preserve_internal_zones(direction):
    sections = load_trip_sections(track(), direction)
    assert [s['name'] for s in sections] == ['ascent', 'level', 'descent', 'ascent']
    assert [s['trip']['start_distance_m'] for s in sections] == [0, 600, 900, 1200]
    assert [s['trip']['zone_indices'] for s in sections] == [[0, 1], [2], [3], [4]]
    assert sections[1]['from_progress'] == pytest.approx(600/1800)
    assert sections[0]['assignments'] == sections[-1]['assignments']
    sections[0]['assignments']['voice_01']['parameters']['velocity'] = 1
    assert sections[-1]['assignments']['voice_01']['parameters']['velocity'] == 88


def test_configured_presence_changes_with_gpx_family_and_keeps_manual_multiplier(direction):
    definition = legacy_direction()
    for family, presence in [('ascent', .75), ('level', 1.), ('descent', .45)]:
        definition['families'][family]['assignments']['voice_03']['presence'] = presence
    direction.write_text(json.dumps(definition))
    runtime, bridge, _ = make_runtime(direction)
    session = runtime.session
    session.set_presence_multiplier('voice_03', 2)
    assert session.presence_state('voice_03', 0) == dict(automatic=.75, multiplier=2, effective=1)
    assert session.presence_state('voice_03', 600/1800) == dict(automatic=1, multiplier=2, effective=1)
    assert session.presence_state('voice_03', 900/1800) == dict(automatic=.45, multiplier=2, effective=.9)
    assert session.presence_state('voice_03', 1200/1800) == dict(automatic=.75, multiplier=2, effective=1)
    runtime.elapsed = 9.5
    assert bridge.status()['voice_03']['presence']['automatic'] == .45


def test_musical_assets_restore_on_return_and_manual_parameters_take_precedence(direction):
    runtime, _, _ = make_runtime(direction)
    session = runtime.session
    assert session.parameters_at('voice_01', 0)['activity'] == .55
    assert session.parameters_at('voice_01', 600/1800)['activity'] == .4
    assert session.parameters_at('voice_01', 900/1800)['activity'] == .85
    assert session.parameters_at('voice_01', 1200/1800)['activity'] == .55
    session.set_parameters('voice_01', {'velocity': 45})
    assert session.parameters_at('voice_01', 900/1800)['velocity'] == 45
    assert session.parameters_at('voice_01', 900/1800)['activity'] == .85
    session.clear_parameters('voice_01')
    assert session.parameters_at('voice_01', 900/1800)['velocity'] == 82


def test_texture_switch_uses_coordinator_source_presence_and_existing_destination(direction):
    runtime, bridge, sent = make_runtime(direction)
    identity = dict(version=1, voice='voice_03', instance='texture', reply_port=9103)
    state = bridge.handle(dict(identity, serial=1, action='hello'))
    assert set(state['controls']) == {'octave', 'velocity', 'follow_source'}
    assert state['controls']['follow_source']['toggle']
    assert state['controls']['follow_source']['value'] == 0
    assert runtime.session.plan(0, 0, 4)['voice_03'].notes[0].pitch == 69
    bridge.handle(dict(identity, serial=2, action='parameter', parameter='follow_source', value=1))
    phrases = runtime.session.plan(0, 4, 4)
    texture = phrases['voice_03']
    assert texture.notes[0].pitch % 12 in {n.pitch % 12 for n in phrases['voice_01'].notes}
    assert 69 <= texture.notes[0].pitch <= 80
    assert runtime.session.coordinator.last_plan['voices']['voice_03']['composition']['source'] == 'voice_01'
    bridge.destination('voice_03')(4, texture)
    assert sent[-1][0] == 9103 and sent[-1][2]['plan']['phrase']['notes'][0]['duration'] == 4
    runtime.session.set_presence_multiplier('voice_01', 0)
    assert not runtime.session.plan(0, 8, 4)['voice_03'].notes
    bridge.handle(dict(identity, serial=3, action='parameter', parameter='follow_source', value=0))
    assert runtime.session.plan(0, 12, 4)['voice_03'].notes[0].pitch == 69


def test_internal_band_change_keeps_same_context_and_phrase_development(direction):
    runtime, bridge, sent = make_runtime(direction)
    # Isola l'interazione completa dalla figura base ammessa ai valori intermedi.
    runtime.session.set_parameter('voice_04', 'variation', 1)
    serial = 0

    def receive(voice, beat):
        nonlocal serial
        serial += 1
        message = dict(version=1, voice=voice, instance=voice, reply_port=9100+int(voice.rsplit('_', 1)[1]),
                       serial=serial, action='hello', transport=dict(beat=beat, playing=1, epoch=0))
        bridge.handle(message)
        runtime.on_message(bridge, message)

    receive('voice_01', 0)
    receive('voice_02', 0)
    receive('voice_03', 0)
    runtime.tick()
    assert runtime.state == 'waiting_for_devices'
    assert not bridge.last_plans
    receive('voice_04', 0)
    runtime.elapsed = 2.5  # km 0.25: climb.
    runtime.tick()
    first = deepcopy(runtime.last_decisions)
    runtime.elapsed = 3.5  # km 0.35: steep_climb, stessa macrosezione.
    receive('voice_01', 4)
    runtime.tick()
    second = runtime.last_decisions
    assert first['trip'] == second['trip']
    assert first['voices']['voice_01']['parameters'] == second['voices']['voice_01']['parameters']
    assert first['voices']['voice_01']['composition']['window'] == 1
    assert second['voices']['voice_01']['composition']['window'] == 2
    runtime.elapsed = 9.5  # km 0.95: descent.
    receive('voice_01', 8)
    runtime.tick()
    assert runtime.snapshot()['section']['trip']['kind'] == 'descent'
    assert runtime.last_decisions['voices']['voice_01']['parameters']['step_beats'] == .5
    assert runtime.last_decisions['voices']['voice_02']['parameters']['density'] == 1.2
    assert set(bridge.last_plans) == {'voice_01', 'voice_02', 'voice_03', 'voice_04'}
    assert runtime.last_decisions['voices']['voice_03']['role'] == 'sustained_texture'
    assert len(runtime.last_decisions['voices']['voice_03']['notes']) == 1
    assert runtime.last_decisions['voices']['voice_03']['notes'][0]['pitch'] == 69
    percussion = runtime.last_decisions['voices']['voice_04']
    assert percussion['role'] == 'percussion'
    assert percussion['composition']['method'] == 'percussion_phrase'
    assert percussion['composition']['logical_start'] == 8
    assert percussion['composition']['material'] == 'spaced_impacts'
    interaction = percussion['composition']['interaction']
    assert interaction['available_sources'] == ['voice_01', 'voice_02']
    supporting_attacks = {n['beat'] for n in runtime.last_decisions['voices']['voice_02']['notes']}
    assert all(n['beat'] in supporting_attacks for n in percussion['notes'] if n['pitch'] in (36, 40))
    foreground_attacks = [n['beat'] for n in runtime.last_decisions['voices']['voice_01']['notes']]
    assert all(all(abs(n['beat']-b) >= .25 for b in foreground_attacks)
               for n in percussion['notes'] if n['pitch'] not in (36, 40))
    assert {note['pitch'] for note in percussion['notes']} <= set(range(36, 52))
    assert {note['pitch'] for note in percussion['notes']} - {36, 38, 42}
    plans = {port: message for port, _, message in sent if message['kind'] == 'plan'}
    assert {note['pitch'] for note in plans[9103]['plan']['phrase']['notes']} == {69}
    assert list(plans[9104]['plan']['phrase']['notes']) == percussion['notes']
    json.dumps(runtime.snapshot(), allow_nan=False)


@pytest.mark.parametrize('problem', ['missing_family', 'extra_family', 'unknown_parameter',
                                     'unsupported_role', 'missing_dependency', 'micro_variation'])
def test_invalid_directions_fail_before_any_note_is_sent(direction, problem):
    definition = json.loads(direction.read_text())
    if problem == 'missing_family':
        del definition['families']['level']
    elif problem == 'extra_family':
        definition['families']['other'] = deepcopy(definition['families']['level'])
    elif problem == 'unknown_parameter':
        definition['families']['level']['assignments']['voice_01']['parameters']['filter'] = .5
    elif problem == 'unsupported_role':
        definition['families']['level']['assignments']['voice_01']['role'] = 'unsupported'
    elif problem == 'missing_dependency':
        del definition['families']['level']['assignments']['voice_01']
    else:
        definition['families']['level']['variations'] = {}
    direction.write_text(json.dumps(definition))
    with pytest.raises(ValueError):
        make_runtime(direction)


def test_family_names_are_configuration_data(direction):
    grouping_path = direction.parent/'macrosezioni-percorso.json'
    grouping = json.loads(grouping_path.read_text())
    grouping['families']['incline'] = grouping['families'].pop('ascent')
    grouping_path.write_text(json.dumps(grouping))
    definition = json.loads(direction.read_text())
    definition['families']['incline'] = definition['families'].pop('ascent')
    direction.write_text(json.dumps(definition))
    assert load_trip_sections(track(), direction)[0]['name'] == 'incline'


def test_dry_run_checks_every_macrosection_without_opening_server(monkeypatch, capsys):
    from desnivel.cli.ensemble import main
    import desnivel.cli.voice_device

    def no_server(*args, **kwargs):
        raise AssertionError('dry-run non deve aprire il server')
    monkeypatch.setattr(desnivel.cli.voice_device, 'VoiceDeviceServer', no_server)
    assert main(['--gpx', 'gpx/tappa05_Firenze_San_Gimignano.gpx', '--config', 'presets/organico.json',
                 '--direction', 'presets/direzione-viaggio.json', '--dry-run']) == 0
    output = capsys.readouterr().out
    assert output.count('[km ') == 44
    assert 'ascent' in output and 'descent' in output and 'level' in output


def test_allocated_dry_run_uses_same_budget_as_report(capsys):
    from desnivel.cli.ensemble import main
    assert main(['--gpx', 'gpx/tappa05_Firenze_San_Gimignano.gpx', '--config', 'presets/organico.json',
                 '--direction', 'presets/direzione-viaggio.json', '--timing', 'allocated', '--dry-run']) == 0
    assert 'Timeline allocated: 696 beat, 174 finestre (12 beat/km).' in capsys.readouterr().out


@pytest.mark.parametrize('extra', [['--manual-sections'], ['--direction', 'presets/direzione-viaggio.json', '--speed', '200']])
def test_allocated_rejects_missing_direction_or_ambiguous_speed(extra, capsys):
    from desnivel.cli.ensemble import main
    with pytest.raises(SystemExit):
        main(['--gpx', 'gpx/tappa05_Firenze_San_Gimignano.gpx', '--config', 'presets/organico.json',
              '--timing', 'allocated', '--dry-run', *extra])
    assert 'richiede una direzione GPX' in capsys.readouterr().err
