from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

from desnivel.adapters.live_devices import LiveDevices
from desnivel.adapters.voice_device import VoiceDeviceBridge
from desnivel.cli.generators import build_generator
from desnivel.cli.ensemble_runtime import EnsembleRuntime
from desnivel.cli.live_components import snake_session
from desnivel.cli.session_setup import (
    GUIDED_CHOICES,
    SessionSetup,
    _guided_behavior_options,
    _guided_generator_definitions,
    _guided_supported_roles,
)
from desnivel.cli.session_config import reconfigure_runtime
from desnivel.cli.trip_direction import prepare_trip_config
from desnivel.sinks.voice_presets import VoicePresetLibrary
from desnivel.trip.track import Track


def configuration():
    config = json.loads(Path('presets/sessione.json').read_text())
    config.pop('direction')
    config['sections'] = [dict(name='all', from_progress=0, root=57, scale='minor', assignments={})]
    return config


def make_setup(tmp_path):
    now, sent = [0.], []
    config = configuration()
    bridge = VoiceDeviceBridge({}, lambda *args: sent.append(args), clock=lambda: now[0])
    track = Track('test', np.array([0., 10.]), {'cum_dist_m': np.array([0., 100.])})
    runtime = [EnsembleRuntime(track, config, bridge, clock=lambda: now[0])]
    library = VoicePresetLibrary(tmp_path/'presets.json')
    def apply(candidate):
        resolved = deepcopy(candidate)
        for section in resolved['sections']:
            section['assignments'] = deepcopy(candidate['arrangement'])
        component = snake_session(candidate)
        runtime[0] = reconfigure_runtime(runtime[0], resolved, library,
                                        external_voices=component.devices if component else None)
        if component:
            component._bridge = runtime[0].bridge
    devices = LiveDevices(bridge.send, clock=lambda: now[0])
    def can_edit():
        if runtime[0].playing:
            raise ValueError('ferma Live')
    setup = SessionSetup(config, tmp_path/'sessione.json', devices, apply, can_edit)
    return setup, runtime, devices, now, sent


def announce(devices, number, kind='voice'):
    devices.observe(dict(version=1, action='discover', device_id=f'endpoint_{number}',
                         instance=f'instance_{number}', reply_port=10000+number, device_kind=kind,
                         track=dict(id=number, index=number-1, name=f'track {number}')))


def add_motif(setup, device_number=1, name='melody'):
    setup.submit('aggiungi traccia')
    setup.snapshot()
    setup.submit(str(device_number))
    setup.submit(name)
    setup.submit('1')


def test_empty_session_add_multiple_same_type_associate_remove_and_reload(tmp_path):
    setup, runtime, devices, now, sent = make_setup(tmp_path)
    runtime[0].tick()
    assert runtime[0].snapshot()['state'] == 'empty'
    for number in (1, 2, 3):
        announce(devices, number)
    add_motif(setup)
    first = next(iter(setup.config['voices']))
    assert runtime[0].transport_voice == first
    add_motif(setup, name='counterpoint')
    assert len(runtime[0].registry) == 2
    assert len({id(v.generator) for v in runtime[0].registry.values()}) == 2
    setup.tick(now[0])
    assert {packet[2]['voice'] for packet in sent if packet[2]['kind'] == 'binding'} == set(setup.config['voices'])
    setup.submit('associa '+first)
    setup.snapshot()
    setup.submit('1')
    assert setup.config['live_bindings'][first] == 'endpoint_3'
    setup.submit('rimuovi '+first)
    assert first not in runtime[0].registry
    assert runtime[0].transport_voice in runtime[0].registry
    setup.submit('salva')
    saved = json.loads(setup.path.read_text())
    assert saved == setup.config
    assert len(saved['voices']) == 1
    assert any(p[2]['kind'] == 'release' for p in sent)
    setup.submit('rimuovi '+next(iter(saved['voices'])))
    runtime[0].tick()
    assert runtime[0].state == 'empty'
    assert not runtime[0].bridge.voices


def test_missing_device_cancel_and_playing_leave_configuration_untouched(tmp_path):
    setup, runtime, devices, now, _ = make_setup(tmp_path)
    announce(devices, 1)
    setup.submit('aggiungi traccia')
    setup.snapshot()
    now[0] = 4
    with pytest.raises(ValueError, match='assente'):
        setup.submit('1')
    setup.cancel()
    assert not setup.config['voices']
    announce(devices, 1)
    runtime[0].playing = True
    with pytest.raises(ValueError, match='ferma Live'):
        setup.submit('aggiungi traccia')
    assert not setup.config['voices']


def test_dependency_prevents_removal_and_generates_after_the_source(tmp_path):
    setup, runtime, devices, _, _ = make_setup(tmp_path)
    announce(devices, 1)
    announce(devices, 2)
    add_motif(setup)
    first = next(iter(setup.config['voices']))
    setup.submit('aggiungi traccia'); setup.snapshot()
    for answer in ('1', 'bass', '2', '2', '1'):
        setup.submit(answer)
    assert len(setup.config['voices']) == 2
    with pytest.raises(ValueError, match='ancora usata'):
        setup.submit('rimuovi '+first)
    phrases = runtime[0].session.plan(0, 0, 4)
    assert list(phrases)[0] == first
    assert len(phrases) == 2


def test_snake_can_be_the_only_track_and_the_transport_source(tmp_path):
    setup, runtime, devices, _, _ = make_setup(tmp_path)
    announce(devices, 1, 'snake')
    setup.submit('aggiungi traccia'); setup.snapshot()
    for answer in ('1', 'snake solo', '1'):
        setup.submit(answer)
    assert not setup.config['voices']
    assert len(setup.config['snake']['components']) == 1
    name = next(iter(setup.config['snake']['components']))
    assert runtime[0].transport_voice == name
    assert runtime[0].bridge.voices[name].read_values()['source'] == 'none'
    runtime[0].tick()
    assert runtime[0].state == 'waiting_for_transport'
    json.dumps(runtime[0].snapshot())


def test_snake_role_cannot_change_after_session_play(tmp_path):
    setup, runtimes, devices, _, _ = make_setup(tmp_path)
    announce(devices, 1, 'snake')
    setup.submit('aggiungi traccia')
    for answer in ('1', 'snake', '1'):
        setup.submit(answer)
    runtime = runtimes[0]
    name = next(iter(setup.config['snake']['components']))
    identity = dict(version=1, voice=name, instance='snake', reply_port=9201, device_id='endpoint_1')
    hello = dict(identity, serial=1, action='hello', transport=dict(beat=0, playing=0, epoch=0))
    runtime.bridge.handle(hello)
    runtime.on_message(runtime.bridge, hello)
    runtime.bridge.handle(dict(identity, serial=2, action='role', role='bass_line'))
    assert runtime.bridge.voices[name].role_state()['role'] == 'bass_line'
    play = dict(identity, serial=3, action='transport', transport=dict(beat=0, playing=1, epoch=0))
    runtime.bridge.handle(play)
    runtime.on_message(runtime.bridge, play)
    with pytest.raises(ValueError, match='prima del play'):
        runtime.bridge.handle(dict(identity, serial=4, action='role', role='sustained_texture'))
    assert runtime.bridge.voices[name].role_state()['role'] == 'bass_line'


def test_failed_reconfiguration_preserves_current_runtime(tmp_path):
    setup, runtime, devices, _, _ = make_setup(tmp_path)
    announce(devices, 1)
    add_motif(setup)
    previous = runtime[0]
    config = deepcopy(setup.config)
    config['voices']['bad'] = dict(generator='unknown', destination='bad')
    with pytest.raises(KeyError):
        setup._commit(config)
    assert runtime[0] is previous
    assert 'bad' not in setup.config['voices']
    assert 'bad' not in previous.bridge.voices


def test_reconfiguration_preserves_role_lock_after_play(tmp_path):
    setup, runtimes, devices, _, _ = make_setup(tmp_path)
    announce(devices, 1)
    add_motif(setup)
    previous = runtimes[0]
    previous.roles_locked = True
    setup._commit(deepcopy(setup.config))
    runtime = runtimes[0]
    assert runtime is not previous and runtime.roles_locked
    with pytest.raises(ValueError, match='prima del play'):
        runtime.session.set_role(next(iter(setup.config['voices'])), 'bass_line')
    candidate = deepcopy(setup.config)
    voice = next(iter(candidate['voices']))
    candidate['arrangement'][voice]['role'] = 'bass_line'
    with pytest.raises(ValueError, match='prima del play'):
        setup._commit(candidate)
    assert runtimes[0] is runtime


def test_trip_direction_resolves_empty_and_arbitrary_arrangements():
    slopes = np.array([0.]*6+[.04]*6+[-.04]*6)
    distances = np.arange(len(slopes)+1)*100.
    track = Track('test', np.arange(len(distances))*10.,
                  {'cum_dist_m': distances, 'ele': np.r_[100., 100+np.cumsum(slopes)*100]})
    config = configuration()
    resolved = prepare_trip_config(track, config, 'presets/direzione-viaggio.json')
    assert all(not s['assignments'] for s in resolved['sections'])
    assert not resolved['trip_music']['motif_generators']
    config['generators']['another_motif'] = dict(type='motif', degrees=[0, 2, 4])
    config['voices']['different_id'] = dict(generator='another_motif', destination='whatever')
    config['arrangement']['different_id'] = dict(role='melody')
    resolved = prepare_trip_config(track, config, 'presets/direzione-viaggio.json')
    assert all(s['assignments'] == config['arrangement'] for s in resolved['sections'])
    assert resolved['trip_music']['motif_generators'] == ['another_motif']
    assert resolved['generators']['another_motif']['degrees'] == resolved['trip_music']['motif_degrees']


def test_more_than_four_voices_and_cancel_do_not_impose_an_ensemble_size(tmp_path):
    setup, runtime, devices, _, _ = make_setup(tmp_path)
    for number in range(1, 8):
        announce(devices, number)
    for number in range(7):
        add_motif(setup, name=f'voice {number}')
    assert len(runtime[0].registry) == 7
    assert len(runtime[0].session.plan(0, 0, 4)) == 7
    setup.submit('aggiungi traccia')
    setup.cancel()
    assert len(runtime[0].registry) == 7


def test_percussion_and_texture_sources_are_saved_as_explicit_dependencies(tmp_path):
    setup, runtime, devices, _, _ = make_setup(tmp_path)
    for number in (1, 2, 3):
        announce(devices, number)
    add_motif(setup)
    first = next(iter(setup.config['voices']))
    setup.submit('aggiungi traccia'); setup.snapshot()
    for answer in ('1', 'drums', '4', '2', '1', '1'):
        setup.submit(answer)
    drums = list(setup.config['voices'])[-1]
    assert setup.config['voices'][drums]['dependencies'] == [first]
    definition = setup.config['generators'][drums]
    assert definition['interaction'] == dict(support_source=first, answer_source=first)
    setup.submit('aggiungi traccia'); setup.snapshot()
    for answer in ('1', 'texture', '3', '2', '1'):
        setup.submit(answer)
    texture = list(setup.config['voices'])[-1]
    assert setup.config['voices'][texture]['optional_dependencies'] == [first]
    assert setup.config['generators'][texture]['settings']['follow_source'] == 1
    assert len(runtime[0].session.plan(0, 0, 4)) == 3


def test_autonomous_percussion_can_be_the_first_voice(tmp_path):
    setup, runtime, devices, _, _ = make_setup(tmp_path)
    announce(devices, 1)
    setup.submit('aggiungi traccia'); setup.snapshot()
    for answer in ('1', 'drums', '4'):
        setup.submit(answer)
    assert len(setup.config['voices']) == 1
    assert next(iter(setup.config['generators'].values()))['type'] == 'percussion_pattern'
    assert next(iter(runtime[0].session.plan(0, 0, 4).values())).notes


@pytest.mark.parametrize('choice,role,kind', [
    ('1', 'melody', 'motif'), ('2', 'bass_line', 'motif'),
    ('3', 'sustained_texture', 'sustained_texture'), ('4', 'percussion', 'percussion_pattern'),
])
def test_voice_choice_selects_a_supported_guided_generator(tmp_path, choice, role, kind):
    setup, _, devices, _, _ = make_setup(tmp_path)
    announce(devices, 1)
    setup.submit('aggiungi traccia')
    setup.submit('1')
    setup.submit('prima voce')
    assert setup.step == 'voice'
    assert [item['label'] for item in setup.snapshot()['choices']] == [
        'melodia', 'basso', 'nota sostenuta', 'drums']
    setup.submit(choice)
    assert not setup.waiting
    voice = next(iter(setup.config['voices']))
    assert setup.config['arrangement'][voice]['role'] == role
    assert setup.config['generators'][voice]['type'] == kind


@pytest.mark.parametrize('choice,labels', [
    ('2', ['autonomo', 'in relazione a una voce']),
    ('3', ['segue l’armonia della sezione', 'segue una voce']),
    ('4', ['pattern autonomo', 'in relazione ad altre voci']),
])
def test_behavior_choices_belong_to_the_selected_voice(tmp_path, choice, labels):
    setup, _, devices, _, _ = make_setup(tmp_path)
    announce(devices, 1)
    announce(devices, 2)
    add_motif(setup)
    setup.submit('aggiungi traccia')
    setup.submit('1')
    setup.submit('seconda voce')
    setup.submit(choice)
    assert setup.step == 'behavior'
    assert [item['label'] for item in setup.snapshot()['choices']] == labels


def test_guided_roles_and_behavior_choices_follow_generator_declarations():
    definitions = _guided_generator_definitions()
    declared_roles = {
        role
        for definition in definitions.values()
        for role in build_generator(definition).generator.supported_roles
    }
    assert set(_guided_supported_roles()) == declared_roles
    for choice in GUIDED_CHOICES:
        generator = build_generator(definitions[choice.generator]).generator
        assert choice.role in generator.supported_roles
        assert choice in [item for item, _ in _guided_behavior_options(choice.role)]


def test_percussion_choices_are_distinct_generators_for_the_same_role():
    options = [choice for choice in GUIDED_CHOICES if choice.role == 'percussion']
    assert [(choice.generator, choice.label) for choice in options] == [
        ('percussion_pattern', 'pattern autonomo'),
        ('percussion_phrase', 'in relazione ad altre voci'),
    ]


def test_snake_uses_voice_then_behavior_then_source(tmp_path):
    setup, _, devices, _, _ = make_setup(tmp_path)
    announce(devices, 1)
    announce(devices, 2, 'snake')
    add_motif(setup)
    source = next(iter(setup.config['voices']))
    setup.submit('aggiungi traccia')
    setup.submit('1')
    setup.submit('snake basso')
    assert [item['label'] for item in setup.snapshot()['choices']] == [
        'melodia', 'basso', 'nota sostenuta']
    setup.submit('2')
    assert setup.step == 'behavior'
    setup.submit('2')
    assert setup.step == 'snake_source'
    setup.submit('1')
    assert next(iter(setup.config['snake']['components'].values())) == dict(
        role='bass_line', mode='coordinated', source=source)


def test_snake_only_session_receives_live_transport_and_sends_its_banks(tmp_path):
    setup, runtimes, devices, _, sent = make_setup(tmp_path)
    announce(devices, 1, 'snake')
    setup.submit('aggiungi traccia'); setup.snapshot()
    for answer in ('1', 'snake', '1'):
        setup.submit(answer)
    config = setup.config
    component = snake_session(config)
    runtime = runtimes[0]
    component._bridge = runtime.bridge
    # Use the same component controls for the adapter and the shared server.
    runtime.bridge.voices.update(component.devices)
    name = runtime.transport_voice
    for serial, beat in ((1, 0.), (2, 4.)):
        message = dict(version=1, action='hello' if serial == 1 else 'transport', voice=name,
                       device_id='endpoint_1', instance='instance_1', reply_port=10001, serial=serial,
                       transport=dict(beat=beat, playing=1, epoch=0, bpm=120), capabilities=['bank_control'],
                       device_state=dict(ready=True, has_instrument=True, source_protocol=1))
        runtime.bridge.handle(message)
        runtime.on_message(runtime.bridge, message)
        component.on_message(runtime.bridge, message)
        runtime.tick()
        component.tick(runtime.snapshot())
    parameters = [message['parameters'] for _, _, message in sent if message['kind'] == 'parameters']
    assert runtime.state == 'playing'
    assert any('Note_01' in packet for packet in parameters)
    with pytest.raises(ValueError, match='sorgente'):
        runtime.bridge.voices[name].apply_parameter('mode', 'coordinated')


def test_ensemble_terminal_guides_a_new_voice_and_saves_it(tmp_path, monkeypatch):
    from desnivel.cli import ensemble, voice_device
    from desnivel.cli.session_config import resolve_configuration
    path = tmp_path/'sessione.json'
    path.write_text(json.dumps(configuration()))
    track = Track('test', np.array([0., 10.]), {'cum_dist_m': np.array([0., 100.])})
    monkeypatch.setattr('desnivel.trip.loader.load_track', lambda *a, **k: track)
    monkeypatch.setattr('desnivel.cli.weather_context.prepare_weather_context', lambda *a, **k: None)
    frames = []
    class Server:
        def __init__(self, *args):
            self.bridge = VoiceDeviceBridge({}, lambda *a: None)
            self.devices = LiveDevices(self.bridge.send)
            announce(self.devices, 1)
            self.server = self
            self.count = 0
        def handle_request(self):
            self.count += 1
            if self.count == 7:
                raise KeyboardInterrupt
        def close(self):
            pass
    commands = iter(['aggiungi traccia', '1', 'synth', '1', 'salva', 'tracce'])
    class Keys:
        command = None
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read_command(self): self.command = ''
        def poll(self):
            self.command = None
            return ['command:'+next(commands)]
    class View:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def update(self, state): frames.append(deepcopy(state))
    monkeypatch.setattr(voice_device, 'VoiceDeviceServer', Server)
    monkeypatch.setattr('desnivel.cli.session_controls.TerminalControls', Keys)
    monkeypatch.setattr('desnivel.cli.session_view.TerminalSessionView', View)
    assert ensemble.main(['--track', 'unused.gpx', '--config', str(path), '--manual-sections',
                          '--status-file', str(tmp_path/'state.json')]) == 0
    assert frames[0]['state'] == 'empty'
    assert len(frames[-1]['voices']) == 1
    assert not frames[-1]['control_error']
    saved = json.loads(path.read_text())
    from desnivel.cli.session_config import resolve_journey
    assert resolve_journey(saved, path) == (Path('unused.gpx').resolve(), None, False)
    restored = resolve_configuration(track, saved, None)
    assert len(restored['sections'][0]['assignments']) == 1


def test_snake_source_cannot_return_to_none_while_coordinated():
    from desnivel.cli.snake_control import SnakeControlSession
    config = json.loads(Path('presets/snake.json').read_text())
    config['components'] = {'snake': dict(role='melody', mode='autonomous', source='none')}
    session = SnakeControlSession(config, {'a': {'name': 'lead'}}, server_factory=None)
    voice = session.devices['snake']
    voice.apply_parameter('source', 'a')
    voice.apply_parameter('mode', 'coordinated')
    with pytest.raises(ValueError, match='sorgente'):
        voice.apply_manual('source', False)
    assert voice.read_values()['source'] == 'a'


def test_reassociation_can_select_an_existing_voice_by_its_display_name(tmp_path):
    setup, runtime, devices, _, _ = make_setup(tmp_path)
    announce(devices, 1)
    announce(devices, 2)
    add_motif(setup, name='synth principale')
    voice = next(iter(setup.config['voices']))
    setup.submit('associa')
    assert setup.snapshot()['choices'] == [dict(value='1', label='synth principale')]
    setup.submit('1')
    setup.submit('1')
    assert setup.config['live_bindings'][voice] == 'endpoint_2'
    assert len(runtime[0].registry) == 1


def test_rematch_preserves_id_priority_and_falls_back_to_track_name(tmp_path):
    setup, runtime, devices, now, sent = make_setup(tmp_path)
    # Annuncia device 1 con traccia 'synth'
    devices.observe(dict(version=1, action='discover', device_id='endpoint_1',
                         instance='instance_1', reply_port=10001, device_kind='voice',
                         track=dict(id=1, index=0, name='synth')))
    add_motif(setup, device_number=1, name='synth')
    voice = next(iter(setup.config['voices']))
    assert setup.config['live_bindings'][voice] == 'endpoint_1'

    # Se endpoint_1 è ancora presente, mantiene endpoint_1 (priorità assoluta all'ID)
    setup.tick(1.0)
    assert setup.config['live_bindings'][voice] == 'endpoint_1'

    # Se endpoint_1 sparisce (es. Live riavviato e l'ID è cambiato in endpoint_new)
    # ma la traccia ha lo stesso nome 'synth' e tipo 'voice'
    now[0] = 10.0
    devices.observe(dict(version=1, action='discover', device_id='endpoint_new',
                         instance='instance_new', reply_port=10002, device_kind='voice',
                         track=dict(id=1, index=0, name='synth')))
    setup.tick(11.0)
    # È stato riassociato automaticamente al nuovo ID della traccia con lo stesso nome
    assert setup.config['live_bindings'][voice] == 'endpoint_new'
    assert runtime[0].bridge.bindings[voice] == 'endpoint_new'

