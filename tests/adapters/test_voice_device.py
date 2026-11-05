import json

import pytest

from desnivel.adapters.voice_device import Control, DeviceVoice, VoiceDeviceBridge
from desnivel.music.phrases import Note, Phrase


def message(serial=1, action='hello', voice='part_a', instance='device_a', port=9101, **extra):
    return dict(version=1, voice=voice, instance=instance, reply_port=port,
                serial=serial, action=action, **extra)


def setup():
    sent, changes, now = [], [], [0]
    voices = {'part_a': DeviceVoice(
        controls={'density': Control(0, 4)}, values={'density': 1},
        presets={'sparse': {'density': .5}, 'dense': {'density': 2}},
        apply=changes.append, role='melody'), 'part_b': DeviceVoice()}
    bridge = VoiceDeviceBridge(voices, lambda *args: sent.append(args), clock=lambda: now[0])
    return bridge, sent, changes, now


def test_controls_validate_apply_acknowledge_and_ignore_reordered_requests():
    bridge, sent, changes, _ = setup()
    state = bridge.handle(message())
    assert state['role'] == 'melody'
    assert state['presets'] == ['sparse', 'dense']
    bridge.handle(message(2, 'preset', preset='sparse'))
    bridge.handle(message(2, 'preset', preset='sparse'))
    bridge.handle(message(1, 'parameter', parameter='density', value=3))
    assert changes == [{'density': .5}]
    bridge.handle(message(3, 'parameter', parameter='density', value=1.5))
    assert changes[-1] == {'density': 1.5}
    assert sent[-1][2]['preset'] is None
    with pytest.raises(ValueError):
        bridge.handle(message(4, 'parameter', parameter='density', value=99))
    assert bridge.voices['part_a'].values == {'density': 1.5}


def test_recording_commands_require_capability_and_do_not_modify_voice_controls():
    bridge, sent, changes, _ = setup()
    bridge.handle(message())
    with pytest.raises(ValueError, match='aggiornare'):
        bridge.control_recording('part_a', 'prepare', 1, 'both')
    bridge.handle(message(2, capabilities=['recording_control']))
    bridge.control_recording('part_a', 'prepare', 1, 'both')
    assert sent[-1][0] == 9101
    assert sent[-1][2]['kind'] == 'recording'
    assert sent[-1][2]['mode'] == 'both'
    assert sent[-1][2]['request'] == 1
    bridge.handle(message(3, 'recording_status', report={'request': 1, 'status': 'ready'}))
    assert changes == []
    assert bridge.voices['part_a'].values == {'density': 1}


def test_failed_application_does_not_confirm_or_mutate_state():
    bridge, sent, _, _ = setup()
    bridge.handle(message())
    def reject(values):
        raise ValueError('controlli incompatibili')
    bridge.voices['part_a'].apply = reject
    with pytest.raises(ValueError):
        bridge.handle(message(2, 'preset', preset='sparse'))
    assert bridge.voices['part_a'].values == {'density': 1}
    assert len(sent) == 1


def test_transport_commands_target_only_the_connected_clock_voice_with_supported_device():
    bridge, sent, _, _ = setup()
    with pytest.raises(ValueError, match='collegare'):
        bridge.control_transport('part_a', 'pause')
    bridge.handle(message())
    with pytest.raises(ValueError, match='aggiornare'):
        bridge.control_transport('part_a', 'pause')
    bridge.handle(message(2, capabilities=['transport_control']))
    bridge.control_transport('part_a', 'pause')
    assert sent[-1][0] == 9101
    assert sent[-1][2]['kind'] == 'transport'
    assert sent[-1][2]['voice'] == 'part_a'
    assert sent[-1][2]['action'] == 'pause'


def test_multiple_instances_have_separate_destinations_and_expired_instances_are_replaced():
    bridge, sent, _, now = setup()
    bridge.handle(message())
    with pytest.raises(ValueError, match='altro dispositivo'):
        bridge.handle(message(instance='other'))
    with pytest.raises(ValueError, match='porta già'):
        bridge.handle(message(voice='part_b', instance='device_b'))
    bridge.handle(message(voice='part_b', instance='device_b', port=9102))
    phrase = Phrase(4, (Note(0, 60, 1, 80),))
    bridge.destination('part_b')(8, phrase)
    assert sent[-1][0] == 9102
    assert sent[-1][2]['voice'] == 'part_b'
    assert sent[-1][2]['instance'] == 'device_b'
    assert sent[-1][2]['plan']['phrase']['notes'][0]['pitch'] == 60
    json.dumps(sent[-1][2], allow_nan=False)
    now[0] = 4
    with pytest.raises(ValueError, match='non collegato'):
        bridge.destination('part_a')(8, phrase)
    bridge.handle(message(instance='replacement'))
    assert bridge.connections['part_a']['instance'] == 'replacement'


def test_reset_and_player_limits():
    bridge, sent, _, _ = setup()
    bridge.handle(message())
    bridge.handle(message(2, 'panic'))
    assert any(args[2].get('plan', {}).get('reset') for args in sent)
    with pytest.raises(ValueError, match='sovrapposizioni'):
        bridge.destination('part_a')(4, Phrase(4, (Note(0, 60, 2, 80), Note(1, 60, 1, 90))))


def test_device_controls_reach_the_shared_python_composition():
    from desnivel.music.session import EnsembleSession, Generator
    observed, sent = [], []
    def generate(request):
        observed.append(request)
        return Phrase(request.length_beats, (Note(0, request.context.root, 1, request.parameters['velocity']),))
    bridge = VoiceDeviceBridge({}, lambda *args: sent.append(args))
    bridge.voices['part_a'] = DeviceVoice()
    session = EnsembleSession({
        'selection_mode': 'manual',
        'voices': {'part_a': {'generator': 'line', 'destination': 'device'}},
        'sections': [{'name': 'opening', 'from_progress': 0, 'root': 60, 'scale': 'major',
                      'assignments': {'part_a': {'role': 'melody', 'parameters': {'velocity': 80}}}}],
    }, {'line': Generator(generate, ('melody',))}, {'device': bridge.destination('part_a')})
    bridge.voices['part_a'] = DeviceVoice(
        controls={'velocity': Control(1, 127, integer=True)}, values={'velocity': 80},
        presets={'soft': {'velocity': 50}}, role='melody',
        apply=lambda values: session.set_parameters('part_a', values))
    bridge.handle(message())
    bridge.handle(message(2, 'preset', preset='soft'))
    session.send(4, session.plan(0, 4, 4))
    assert observed[-1].role == 'melody'
    assert sent[-1][2]['plan']['phrase']['notes'][0]['velocity'] == 50
    session.clear_parameters('part_a')
    assert session.plan(0, 8, 4)['part_a'].notes[0].velocity == 80


def test_manual_role_survives_sections_and_follow_section_restores_current_assignment():
    from desnivel.music.session import EnsembleSession, Generator
    calls, sent, progress = [], [], [0]
    def generate(request):
        calls.append(request)
        return Phrase(request.length_beats, ())
    session = EnsembleSession({
        'selection_mode': 'manual',
        'voices': {'part_a': {'generator': 'line', 'destination': 'out'}},
        'sections': [
            {'name': 'opening', 'from_progress': 0, 'root': 60, 'scale': 'major',
             'assignments': {'part_a': {'role': 'melody'}}},
            {'name': 'middle', 'from_progress': .3, 'root': 62, 'scale': 'minor',
             'assignments': {'part_a': {'role': 'sustained_texture'}}},
            {'name': 'rest', 'from_progress': .6, 'root': 62, 'scale': 'minor', 'assignments': {}},
            {'name': 'return', 'from_progress': .8, 'root': 60, 'scale': 'major',
             'assignments': {'part_a': {'role': 'melody'}}},
        ]}, {'line': Generator(generate, ('melody', 'sustained_texture'))}, {'out': lambda *args: None})
    bridge = VoiceDeviceBridge({'part_a': DeviceVoice.for_session(session, 'part_a', lambda: progress[0])},
                               lambda *args: sent.append(args))
    state = bridge.handle(message())
    assert state['supported_roles'] == ['melody', 'sustained_texture']
    assert state['role_mode'] == 'section' and state['role'] == 'melody'
    state = bridge.handle(message(2, 'role', role='sustained_texture'))
    assert state['role_mode'] == 'manual'
    session.plan(0, 0, 4)
    assert calls[-1].role == 'sustained_texture'
    progress[0] = .6
    state = bridge.handle(message(3))
    assert state['role'] == 'sustained_texture' and not state['active']
    assert session.plan(.6, 4, 4) == {}  # Il ruolo non attiva una voce esclusa dall'organico.
    progress[0] = .8
    session.plan(.8, 8, 4)
    assert calls[-1].role == 'sustained_texture'
    with pytest.raises(ValueError, match='ruolo non supportato'):
        bridge.handle(message(4, 'role', role='unknown'))
    assert session.role_state('part_a', .8)['role'] == 'sustained_texture'
    state = bridge.handle(message(5, 'role', role=None))
    assert state['role_mode'] == 'section' and state['role'] == 'melody'
    session.plan(.8, 12, 4)
    assert calls[-1].role == 'melody'
    progress[0] = .3
    state = bridge.handle(message(6))
    assert state['role'] == 'sustained_texture' and state['role_mode'] == 'section'
    session.plan(.3, 16, 4)
    assert calls[-1].role == 'sustained_texture'
    # I seriali superati non possono ripristinare una vecchia scelta manuale.
    bridge.handle(message(2, 'role', role='melody'))
    assert session.role_state('part_a', .3)['role_mode'] == 'section'


def test_unbound_device_cannot_assign_roles():
    bridge, _, _, _ = setup()
    bridge.handle(message())
    with pytest.raises(ValueError, match='non disponibile'):
        bridge.handle(message(2, 'role', role='melody'))


def parameter_session(reject=None):
    from desnivel.music.session import EnsembleSession, Generator
    progress = [0.]
    defaults = dict(velocity=80, activity=.5, seed=7)
    controls = dict(velocity=Control(1, 127, True), activity=Control(0, 1), seed=Control(0, 100, True))
    def validate(role, values):
        for name, value in values.items():
            controls[name].validate(value)
        if reject:
            reject(values)
    def generate(request):
        return Phrase(request.length_beats, (Note(0, request.context.root, 1, request.parameters['velocity']),))
    session = EnsembleSession({
        'selection_mode': 'manual',
        'voices': {v: {'generator': 'line', 'destination': v} for v in ('part_a', 'part_b')},
        'sections': [
            {'name': 'opening', 'from_progress': 0, 'root': 60, 'scale': 'major',
             'assignments': {v: {'role': 'melody', 'parameters': {'velocity': 70, 'activity': .3}}
                             for v in ('part_a', 'part_b')}},
            {'name': 'middle', 'from_progress': .5, 'root': 62, 'scale': 'minor',
             'assignments': {v: {'role': 'melody', 'parameters': {'velocity': 100, 'activity': .9, 'seed': 8}}
                             for v in ('part_a', 'part_b')}}]},
        {'line': Generator(generate, ('melody',), validate, parameter_defaults=defaults)},
        {v: lambda *args: None for v in ('part_a', 'part_b')})
    devices = {v: DeviceVoice.for_session(session, v, lambda: progress[0],
               controls=controls, values=dict(defaults), presets={'soft': dict(defaults, velocity=50)})
               for v in ('part_a', 'part_b')}
    return session, VoiceDeviceBridge(devices, lambda *args: None), progress


def test_manual_parameter_leaves_other_controls_automatic_and_releases_independently():
    session, bridge, progress = parameter_session()
    state = bridge.handle(message())
    assert all(c['manual'] is False for c in state['controls'].values())
    state = bridge.handle(message(2, 'parameter', parameter='velocity', value=60))
    assert state['controls']['velocity']['manual'] is True
    assert state['controls']['activity']['manual'] is False
    progress[0] = .6
    state = bridge.handle(message(3))
    assert state['controls']['activity']['value'] == .9
    assert not session.manual('part_b', 'velocity')
    assert session.plan(.6, 0, 4)['part_a'].notes[0] == Note(0, 62, 1, 60)
    bridge.handle(message(4, 'parameter', parameter='seed', value=42))
    state = bridge.handle(message(5, 'manual', parameter='velocity', value=False))
    assert state['controls']['velocity']['manual'] is False
    assert state['controls']['velocity']['value'] == 100
    assert state['controls']['seed']['manual'] is True
    assert state['controls']['seed']['value'] == 42
    assert session.plan(.6, 4, 4)['part_a'].notes[0].velocity == 100
    bridge.handle(message(2, 'manual', parameter='velocity', value=True))
    assert not session.manual('part_a', 'velocity')  # Comando superato.


def test_explicit_manual_uses_current_section_and_survives_rewind():
    session, bridge, progress = parameter_session()
    bridge.handle(message())
    progress[0] = .6
    state = bridge.handle(message(2, 'manual', parameter='velocity', value=True))
    assert state['controls']['velocity']['value'] == 100
    progress[0] = 0
    session.coordinator.reset()
    assert session.manual('part_a', 'velocity')
    assert session.parameters_at('part_a', 0)['velocity'] == 100
    assert session.parameters_at('part_a', 0)['activity'] == .3
    state = bridge.handle(message(3, 'manual', parameter='velocity', value=False))
    assert state['controls']['velocity']['value'] == 70
    assert state['controls']['velocity']['manual'] is False


def test_invalid_edits_preserve_auto_and_preset_values_can_be_released_individually():
    session, bridge, _ = parameter_session()
    bridge.handle(message())
    for action, extra in [('parameter', dict(parameter='velocity', value=300)),
                          ('manual', dict(parameter='velocity', value=1)),
                          ('manual', dict(parameter='missing', value=True))]:
        with pytest.raises(ValueError):
            bridge.handle(message(2, action, **extra))
        assert not session.manual('part_a', 'velocity')
    state = bridge.handle(message(3, 'preset', preset='soft'))
    assert all(c['manual'] is True for c in state['controls'].values())
    state = bridge.handle(message(4, 'manual', parameter='velocity', value=False))
    assert state['preset'] is None
    assert state['controls']['velocity']['manual'] is False
    assert state['controls']['activity']['manual'] is True
    bridge.handle(message(5))
    assert session.manual('part_a', 'activity')
    session.clear_parameters('part_a')
    assert not session.manual('part_a', 'activity')


def test_incompatible_release_keeps_the_previous_manual_values():
    def reject(values):
        if values['velocity'] == 70 and values['activity'] == .9:
            raise ValueError('combinazione incompatibile')
    session, bridge, _ = parameter_session(reject)
    bridge.handle(message())
    bridge.handle(message(2, 'parameter', parameter='velocity', value=60))
    bridge.handle(message(3, 'parameter', parameter='activity', value=.9))
    with pytest.raises(ValueError, match='incompatibile'):
        bridge.handle(message(4, 'manual', parameter='velocity', value=False))
    assert session.manual('part_a', 'velocity')
    assert session.parameters_at('part_a', 0)['velocity'] == 60
    assert session.parameters_at('part_a', 0)['activity'] == .9


def test_control_descriptions_follow_values_without_changing_keys_or_presets():
    bridge, _, changes, _ = setup()
    spec = bridge.voices['part_a']
    spec.describe_controls = lambda role, values: {
        'density': {'label': 'Attacchi per beat',
                    'inactive_reason': 'Soglia zero' if values['density'] == 0 else None}}
    state = bridge.handle(message())
    assert state['controls']['density']['label'] == 'Attacchi per beat'
    assert state['controls']['density']['inactive_reason'] is None
    state = bridge.handle(message(2, 'parameter', parameter='density', value=0))
    assert state['controls']['density']['inactive_reason'] == 'Soglia zero'
    assert changes == [{'density': 0}]
    state = bridge.handle(message(3, 'preset', preset='dense'))
    assert state['controls']['density']['inactive_reason'] is None
    assert spec.presets['dense'] == {'density': 2}
