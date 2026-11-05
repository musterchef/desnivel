from copy import deepcopy
from io import StringIO

from desnivel.cli.session_view import TerminalSessionView, render_session


def snapshot():
    return {
        'state': 'playing', 'error': None,
        'trip': {'progress': .261, 'elapsed_s': 8600, 'duration_s': 32421, 'distance_m': 15682, 'speed': 50},
        'transport': {'playing': True, 'beat': 220},
        'voices': {'voice_02': {
            'name': 'Bass', 'connected': True, 'active': False,
            'role': 'bass_line', 'role_mode': 'manual', 'next_entry_progress': .3,
            'preset': None, 'controls': {'density': {'value': .8}},
        }},
        'decisions': {'director': {'section': 'opening', 'from_progress': 0, 'until_progress': .3,
                                   'root': 57, 'scale': 'minor'}, 'coordinator': None},
    }


def test_refreshes_position_during_play_without_state_transition():
    now, output = [0.], StringIO()
    view = TerminalSessionView(output, lambda: now[0])
    view.details = True
    first = snapshot()
    view.update(first)
    second = deepcopy(first)
    second['trip']['progress'] = .27
    second['transport']['beat'] = 222
    now[0] = .5
    view.update(second)
    assert '27.00%' not in output.getvalue()
    now[0] = 1
    view.update(second)
    assert '26.10%' in output.getvalue() and '27.00%' in output.getvalue()
    assert 'beat 222.00' in output.getvalue()
    assert 'fuori organico; ingresso al 30%' in output.getvalue()
    assert 'SCOLLEGATO' not in output.getvalue()


def test_view_reports_actual_planning_order_notes_and_reference_parts():
    state = snapshot()
    state['decisions']['coordinator'] = {
        'start': 224, 'length_beats': 4, 'section': 'development', 'order': ['a', 'b'],
        'voices': {
            'a': {'role': 'melody', 'dependencies': [], 'notes': [{'pitch': 57, 'beat': 0}]},
            'b': {'role': 'bass_line', 'dependencies': ['a'], 'notes': []},
        },
    }
    frame = render_session(state, details=True)
    assert 'a -> b' in frame
    assert '57@0' in frame
    assert 'riferimenti: a' in frame
    assert '0 note MIDI@beat: silenzio' in frame
    assert '224, 228' in frame


def test_view_identifies_the_current_macrosections_and_the_sent_plan_separately():
    state = snapshot()
    state['section'] = {'trip': {'index': 7, 'kind': 'ascent', 'start_distance_m': 16600,
                                 'end_distance_m': 20500, 'zone_indices': [8, 9]}}
    state['decisions']['coordinator'] = {'start': 224, 'length_beats': 4, 'section': 'level',
                                         'trip': {'index': 6, 'kind': 'level'}, 'order': [], 'voices': {}}
    frame = render_session(state, details=True)
    assert 'Macrosezione 8: ascent | km 16.60–20.50 | 2 zone interne' in frame
    assert 'Assetto della macrosezione 7: level' in frame


def test_allocated_view_shows_musical_budget_instead_of_replay_speed():
    state = snapshot()
    state['timeline'] = {'beat': 24, 'total_beats': 480, 'beats_per_km': 12}
    text = render_session(state, details=True)
    assert 'timeline 24 / 480 beat' in text
    assert '12 beat/km' in text
    assert 'replay' not in text


def test_tty_frame_fits_viewport_and_does_not_scroll_on_refresh(monkeypatch):
    from os import terminal_size
    class Terminal(StringIO):
        def isatty(self):
            return True
    monkeypatch.setattr('desnivel.cli.session_view.shutil.get_terminal_size', lambda: terminal_size((60, 18)))
    output = Terminal()
    state = snapshot()
    state['voices']['voice_02']['controls'] = {f'parametro_{i}': {'value': .7} for i in range(20)}
    view = TerminalSessionView(output)
    view.update(state)
    frame = output.getvalue().removeprefix('\x1b[H\x1b[2J').removesuffix('\x1b[J').replace('\x1b[K', '')
    assert len(frame.splitlines()) <= 17
    assert all(len(row) < 60 for row in frame.splitlines())
    assert 'Bass' in frame
    assert 'Ctrl+C' in frame
    assert not output.getvalue().endswith('\n')


def test_compact_terminal_keeps_errors_and_expands_again_when_resized():
    from desnivel.cli.session_view import fit_terminal
    state = snapshot()
    state['error'] = 'connessione assente'
    state['control_error'] = 'comando non riuscito'
    state['voices']['voice_02']['controls'] = {f'parametro_{i}': {'value': .7} for i in range(20)}
    frame = render_session(state, details=True)
    compact = fit_terminal(frame, 80, 12)
    assert 'ERRORE: connessione assente' in compact
    assert 'COMANDO: comando non riuscito' in compact
    assert 'Dettagli ridotti' in compact
    large = fit_terminal(frame, 160, 100)
    assert 'parametro_19' in large
    assert 'Dettagli ridotti' not in large


def test_device_errors_can_enter_the_panel_without_printing_over_it(capsys):
    from desnivel.cli.voice_device import VoiceDeviceServer
    server = VoiceDeviceServer.__new__(VoiceDeviceServer)
    from desnivel.sinks.voice_wire import VoiceDecoder
    server._decoder = VoiceDecoder()
    messages = []
    server.on_error = messages.append
    server._receive('/invalid', -1)
    assert messages == ['frammento OSC non valido']
    assert capsys.readouterr().out == ''
    server.on_error = None
    server._receive('/invalid', -1)
    assert 'Voice device:' in capsys.readouterr().out


def test_plan_time_is_explicit_and_summary_precedes_parameter_details():
    state = snapshot()
    state['decisions']['coordinator'] = {
        'start': 224, 'length_beats': 4, 'section': 'level', 'order': [], 'voices': {}}
    for beat, label in [(220, 'preparato in anticipo'), (224, 'intervallo corrente'),
                        (228, 'intervallo concluso')]:
        state['transport']['beat'] = beat
        frame = render_session(state, details=True)
        assert label in frame
        assert frame.index('ADESSO') < frame.index('Coordinator:') < frame.index('VOCI ·')
        assert frame.index('VOCI ·') < frame.index('PARAMETRI ·')


def test_voice_summary_distinguishes_effective_target_and_manual_without_changing_state():
    state = snapshot()
    state['voices']['voice_02']['controls'] = {
        'density': {'value': .568343, 'manual': False, 'automation': {'target': .71}},
        'syncopation': {'value': .2, 'manual': True, 'automation': {'target': .5}}}
    before = deepcopy(state)
    frame = render_session(state, details=True)
    summary = frame.split('PARAMETRI ·')[0]
    assert 'density=0.568 → 0.71' in summary
    assert 'manual: syncopation' in summary
    assert 'syncopation=0.2 →' not in frame
    assert state == before


def test_setup_instructions_and_immediate_check_stay_visible_in_compact_view():
    from desnivel.cli.session_view import fit_terminal
    state=snapshot()
    state['setup']=dict(status='waiting',notice='controllo Snake non collegato',
        instructions=['Crea traccia MIDI: Snake → controllo → strumento.',
                      'Voce snake_01; Receive 9201; Python 9007.'],next_check_s=5)
    frame=fit_terminal(render_session(state, details=True),100,24)
    assert 'controllo Snake non collegato' in frame
    assert 'Snake → controllo → strumento' in frame
    assert 'snake_01' in frame and '9201' in frame
    assert 'Invio verifica ora' in frame and 'Esc annulla' in frame
    assert 'N: prepara Snake' in frame


def test_source_role_and_unavailability_remain_visible_in_a_compact_terminal():
    from desnivel.cli.session_view import fit_terminal
    state=snapshot()
    state['components']={'snake_01':dict(role='melody',connected=True,status='melody · autonomous',
        source_status='telemetria scaduta')}
    frame=fit_terminal(render_session(state, details=True),80,24)
    assert 'SORGENTE snake_01: melody' in frame and 'telemetria scaduta' in frame


def test_unassociated_existing_controls_are_reported_without_generic_device_errors():
    import json
    from desnivel.adapters.live_devices import LiveDevices
    from desnivel.adapters.voice_device import VoiceDeviceBridge, CONTROL_ADDRESS
    from desnivel.cli.voice_device import VoiceDeviceServer
    from desnivel.sinks.voice_wire import VoiceDecoder
    server = VoiceDeviceServer.__new__(VoiceDeviceServer)
    server._decoder = VoiceDecoder()
    server.bridge = VoiceDeviceBridge({}, lambda *args: None)
    server.devices = LiveDevices(server.bridge.send)
    errors, accepted = [], []
    server.on_error = errors.append
    server.on_message = lambda *args: accepted.append(args)
    for i in range(1, 5):
        message = dict(version=1, action='hello', instance=f'old_{i}', voice=f'voice_0{i}',
                       reply_port=9100+i, serial=1)
        server._receive(CONTROL_ADDRESS, *json.dumps(message).encode())
    assert len(server.devices.unannounced()) == 4
    assert not errors and not accepted and not server.bridge.connections
