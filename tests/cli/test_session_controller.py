from types import SimpleNamespace

import pytest

from desnivel.cli.live_components import LiveComponents
from desnivel.cli.session_commands import validate_command
from desnivel.cli.session_controller import SessionController
from desnivel.cli.session_frontend import TerminalFrontend
from desnivel.sinks.voice_presets import VoicePresetLibrary
from test_session_setup import make_setup, announce


def controller(tmp_path):
    setup, runtimes, devices, now, sent = make_setup(tmp_path)
    runtime = runtimes[0]
    components = LiveComponents(setup.config, setup.path, 9006)
    components.attach(runtime)
    server = SimpleNamespace(bridge=runtime.bridge, devices=devices)
    service = SessionController(runtime, setup.config, setup.path, server,
                                VoicePresetLibrary(tmp_path/'presets.json'), components, clock=lambda: now[0])
    return service, devices, sent


def test_structured_commands_drive_preparation_without_a_terminal(tmp_path):
    service, devices, _ = controller(tmp_path)
    announce(devices, 1)
    assert service.execute({'action': 'setup_begin'})
    state = service.tick()
    assert state['setup']['step'] == 'destination'
    assert 'command_input' not in state
    assert not service.execute({'action': 'setup_reply', 'value': '99'})
    assert service.tick()['control_error']
    for value in ('1', 'synth', '1'):
        assert service.execute(dict(action='setup_reply', value=value))
    voice = service.runtime.transport_voice
    message = dict(version=1, action='hello', voice=voice, device_id='endpoint_1', instance='instance_1',
                   serial=1, reply_port=10001, transport=dict(beat=0., playing=0, epoch=0, bpm=120))
    service.runtime.bridge.handle(message)
    service.on_message(service.runtime.bridge, message)
    state = service.tick()
    assert state['configuration']['name'] == 'sessione'
    assert state['controls']['transport_connected']
    assert state['controls']['edit_allowed']
    assert state['setup']['counts']['connected'] == 1
    assert service.execute({'action': 'setup_save'})
    assert service.setup.path.exists()
    assert not service.execute(dict(action='setup_reply', value='1'))
    assert 'nessuna domanda' in service.error


def test_commands_cannot_restart_the_wizard_or_save_an_answer_as_a_name(tmp_path):
    service, devices, _ = controller(tmp_path)
    announce(devices, 1)
    service.execute({'action': 'setup_begin'})
    service.execute(dict(action='setup_reply', value='1'))
    assert not service.execute({'action': 'setup_begin'})
    assert not service.execute({'action': 'setup_save'})
    assert service.setup.step == 'name'
    assert not service.setup.path.exists()
    assert service.execute({'action': 'setup_cancel'})
    assert not service.setup.waiting


@pytest.mark.parametrize('command', [None, 'pause', {}, {'action': 'unknown'},
    {'action': 'pause', 'value': 'bad'}, {'action': 'setup_reply', 'value': ['1']},
    {'action': 'setup_reply', 'value': 'a\nb'}, {'action': 'setup_reply', 'value': 'x'*513}])
def test_command_contract_rejects_unsupported_payloads(command):
    with pytest.raises(ValueError):
        validate_command(command)


def test_disabled_terminal_does_not_construct_input_or_rendering(monkeypatch):
    monkeypatch.setattr('desnivel.cli.session_controls.TerminalControls', lambda: pytest.fail('nessuna tastiera'))
    monkeypatch.setattr('desnivel.cli.session_view.TerminalSessionView', lambda: pytest.fail('nessun renderer'))
    with TerminalFrontend(enabled=False) as frontend:
        assert list(frontend.commands()) == []
        frontend.synchronize(SimpleNamespace(waiting=False))
        frontend.update({})


def test_cli_can_run_without_loading_a_terminal_frontend(tmp_path, monkeypatch):
    import json
    from desnivel.cli import ensemble
    setup, runtimes, devices, _, _ = make_setup(tmp_path)
    setup.config['journey'] = {'track': 'unused.gpx', 'infer_fit_pauses': True}
    setup.path.write_text(json.dumps(setup.config))
    runtime = runtimes[0]
    loads = []
    monkeypatch.setattr('desnivel.trip.loader.load_track', lambda *a, **k: loads.append((a, k)) or runtime.track)
    monkeypatch.setattr('desnivel.cli.weather_context.prepare_weather_context', lambda *a, **k: None)
    monkeypatch.setattr('desnivel.cli.session_controls.TerminalControls', lambda: pytest.fail('nessuna tastiera'))
    monkeypatch.setattr('desnivel.cli.session_view.TerminalSessionView', lambda: pytest.fail('nessun renderer'))
    class Server:
        def __init__(self, *args):
            self.bridge = runtime.bridge
            self.devices = devices
            self.server = self
            self.closed = False
        def handle_request(self):
            raise KeyboardInterrupt
        def close(self):
            self.closed = True
    monkeypatch.setattr('desnivel.cli.voice_device.VoiceDeviceServer', Server)
    target = tmp_path/'headless.json'
    assert ensemble.main(['--config', str(setup.path), '--manual-sections',
                          '--no-terminal', '--status-file', str(target)]) == 0
    assert json.loads(target.read_text())['state'] == 'closed'
    assert loads == [((tmp_path/'unused.gpx',), {'timing_reference': None, 'infer_missing_fit_timer': True})]


def transport_controller(tmp_path, *, playing=1):
    service, devices, sent = controller(tmp_path)
    announce(devices, 1)
    service.execute({'action': 'setup_begin'})
    for value in ('1', 'synth', '1'):
        assert service.execute(dict(action='setup_reply', value=value))
    message = dict(version=1, action='hello', voice=service.runtime.transport_voice,
                   device_id='endpoint_1', instance='instance_1', serial=1, reply_port=10001,
                   capabilities=['transport_control', 'recording_control'],
                   transport=dict(beat=8., playing=playing, epoch=0, bpm=120))
    def receive(**changes):
        message['serial'] += 1
        message['transport'].update(changes)
        service.runtime.bridge.handle(message)
        service.on_message(service.runtime.bridge, message)
    receive()
    sent.clear()
    return service, sent, receive


def transport_actions(sent):
    return [payload['action'] for _, _, payload in sent if payload.get('kind') == 'transport']


def test_restart_in_play_waits_for_stop_then_rewinds_once(tmp_path):
    service, sent, receive = transport_controller(tmp_path)
    assert service.execute({'action': 'restart'})
    assert service.runtime.paused
    assert transport_actions(sent) == ['pause']
    assert service.runtime.restart_count == 0
    assert service.tick()['controls']['restart_pending']
    assert not service.execute({'action': 'resume'})
    assert service.execute({'action': 'restart'})
    receive(beat=9., playing=1)
    assert transport_actions(sent) == ['pause']
    receive(playing=0, epoch=1)
    assert transport_actions(sent) == ['pause', 'restart']
    assert service.runtime.restart_count == 1
    assert service.runtime.beat == service.runtime.elapsed == 0
    receive(beat=0., playing=0, epoch=2)
    assert service.runtime._restart_epoch is None
    assert not service.runtime.playing
    assert not service.tick()['controls']['restart_pending']
    assert transport_actions(sent) == ['pause', 'restart']


@pytest.mark.parametrize('paused', [False, True])
def test_restart_when_live_is_stopped_rewinds_directly(tmp_path, paused):
    service, sent, _ = transport_controller(tmp_path, playing=0)
    service.runtime.paused = paused
    assert service.execute({'action': 'restart'})
    assert transport_actions(sent) == ['restart']
    assert service.runtime.restart_count == 1
    assert service.restart_deadline is None


@pytest.mark.parametrize('recording', [False, True])
def test_restart_without_stop_confirmation_times_out_without_rewinding(tmp_path, recording):
    service, sent, receive = transport_controller(tmp_path)
    if recording:
        service.recording.status = 'ready'
        service.recording.tracks = [{'id': 1}]
        service.recording.mode = 'audio'
    service.execute({'action': 'record_start' if recording else 'restart'})
    service.clock = lambda: 4.
    state = service.tick()
    assert 'nessuna conferma di Stop' in state['control_error']
    assert not state['controls']['restart_pending']
    receive(beat=0., playing=0, epoch=1)
    assert transport_actions(sent) == ['pause']
    assert service.runtime.restart_count == 0
    if recording:
        assert service.recording.status == 'error'


def test_restart_after_pause_still_waits_for_the_live_stop_confirmation(tmp_path):
    service, sent, receive = transport_controller(tmp_path)
    service.execute({'action': 'pause'})
    service.execute({'action': 'restart'})
    assert transport_actions(sent) == ['pause']
    receive(playing=0, epoch=1)
    assert transport_actions(sent) == ['pause', 'restart']


def test_recording_waits_for_rewind_confirmation_after_automatic_pause(tmp_path):
    service, sent, receive = transport_controller(tmp_path)
    service.recording.status = 'ready'
    service.recording.tracks = [{'id': 1}]
    service.recording.mode = 'audio'
    assert service.execute({'action': 'record_start'})
    receive(beat=0., playing=0, epoch=1)
    assert service.recording.status == 'rewinding'
    assert not any(payload.get('kind') == 'recording' for _, _, payload in sent)
    receive(beat=0., playing=0, epoch=2)
    assert service.recording.status == 'starting'
    assert transport_actions(sent) == ['pause', 'restart']
