from types import SimpleNamespace
import os
import pty
import termios

from desnivel.cli.session_controls import TerminalControls
from desnivel.cli.session_controller import apply_control


def test_only_the_transport_voice_receives_commands_and_duplicate_pause_is_idempotent():
    calls = []
    runtime = SimpleNamespace(paused=False, playing=True, transport_voice='clock_part')
    runtime.bridge = SimpleNamespace(control_transport=lambda voice, action: calls.append((voice, action)))
    def control(action):
        runtime.paused = action == 'pause'
    runtime.control = control
    apply_control(runtime, 'pause')
    apply_control(runtime, 'pause')
    assert calls == [('clock_part', 'pause')]
    apply_control(runtime, 'resume')
    apply_control(runtime, 'resume')
    assert calls == [('clock_part', 'pause'), ('clock_part', 'resume')]


def test_live_transport_messages_update_state_without_sending_transport_commands_back():
    from test_ensemble_runtime import setup
    runtime, bridge, _, sent, receive = setup()
    receive(playing=0)
    receive(playing=1)
    receive(playing=0, epoch=1)
    assert not any(payload.get('kind') == 'transport' for _, _, payload in sent)


def test_terminal_reads_adjacent_keys_and_restores_settings_on_exit():
    master, slave = pty.openpty()
    with os.fdopen(slave, 'r') as stream:
        original = termios.tcgetattr(stream.fileno())
        try:
            with TerminalControls(stream) as keyboard:
                os.write(master, b' rCc123gSmMn\n\x1b')
                assert list(keyboard.poll()) == ['toggle', 'restart', 'scan', 'scan',
                                                 'record_audio', 'record_midi', 'record_both',
                                                 'record_start', 'record_stop', 'weather_toggle', 'weather_toggle',
                                                 'component_prepare', 'component_check', 'setup_cancel']
            restored = termios.tcgetattr(stream.fileno())
            # macOS può attivare PENDIN al ritorno in modalità canonica:
            # è il flag transitorio di rielaborazione dell'input, non un'impostazione cambiata.
            restored[3] &= ~termios.PENDIN
            original[3] &= ~termios.PENDIN
            assert restored == original
        finally:
            os.close(master)


def test_weather_key_changes_context_without_sending_live_transport_commands():
    calls = []
    runtime = SimpleNamespace(toggle_context=lambda name: calls.append(name))
    apply_control(runtime, 'weather_toggle')
    assert calls == ['weather']


def test_terminal_command_input_preserves_utf8_and_does_not_trigger_shortcuts():
    master, slave = pty.openpty()
    try:
        with os.fdopen(slave, 'r') as stream, TerminalControls(stream) as keyboard:
            os.write(master, ':aggiungi traccia\n'.encode())
            assert list(keyboard.poll()) == ['command:aggiungi traccia']
            keyboard.read_command()
            os.write(master, 'città\x7fà\n'.encode())
            assert list(keyboard.poll()) == ['command:città']
            keyboard.read_command()
            os.write(master, b'abc\x1b')
            assert list(keyboard.poll()) == ['setup_cancel']
            assert keyboard.command is None
    finally:
        os.close(master)


def test_preparation_shortcuts_and_pasted_answers_follow_the_current_question():
    master, slave = pty.openpty()
    try:
        with os.fdopen(slave, 'r') as stream, TerminalControls(stream) as keyboard:
            os.write(master, b'abtvd')
            assert list(keyboard.poll()) == ['setup_begin', 'setup_associate', 'scan', 'setup_save', 'details_toggle']
            os.write(master, ':aggiungi traccia\n1\ncittà\n'.encode())
            answers = []
            for action in keyboard.poll():
                answers.append(action)
                if len(answers) < 3:
                    keyboard.read_command()
            assert answers == ['command:aggiungi traccia', 'command:1', 'command:città']
    finally:
        os.close(master)
