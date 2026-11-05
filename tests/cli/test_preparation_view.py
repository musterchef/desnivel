from io import StringIO

import pytest

from desnivel.cli.session_view import TerminalSessionView, render_session, fit_terminal
from test_session_view import snapshot
from test_session_setup import make_setup, announce


def preparation(tmp_path):
    setup, runtime, devices, _, _ = make_setup(tmp_path)
    for i in range(1, 5):
        announce(devices, i)
    setup.submit('aggiungi traccia')
    state = runtime[0].snapshot()
    state.update(setup=setup.snapshot(), command_input='')
    return state, devices


def test_preparation_puts_four_existing_tracks_and_the_question_on_one_screen(tmp_path):
    state, _ = preparation(tmp_path)
    frame = fit_terminal(render_session(state), 80, 24)
    assert 'preparazione del set' in frame
    assert '4 tracce rilevate' in frame
    for i in range(1, 5):
        assert f'[{i}]  track {i}' in frame
    assert '1 · scegli la traccia' in frame
    assert 'Invio conferma' in frame and '> ▏' in frame
    assert 'Coordinator' not in frame and 'PARAMETRI' not in frame
    assert len(frame.splitlines()) <= 23
    assert all(len(row) < 80 for row in frame.splitlines())


def test_old_controls_are_visible_with_an_actionable_explanation(tmp_path):
    state, devices = preparation(tmp_path)
    devices.devices.clear()
    for i in range(1, 5):
        devices.observe_control(dict(version=1, action='hello', voice=f'voice_0{i}',
                                    instance=f'old_{i}', reply_port=9100+i, serial=1))
    setup, _, _, _, _ = make_setup(tmp_path)
    setup.devices = devices
    state['setup'] = setup.snapshot()
    frame = fit_terminal(render_session(state), 100, 26)
    assert frame.count('controllo da aggiornare') == 4
    assert 'User Library' in ' '.join(frame.split()) and 'ricaricali in Live' in ' '.join(frame.split())
    assert 'identità, porta o seriale' not in frame


def test_existing_track_choices_survive_long_new_track_instructions_in_a_short_terminal(tmp_path):
    setup, runtime, devices, _, _ = make_setup(tmp_path)
    setup.submit('aggiungi traccia')
    setup.submit('0')
    for i in range(1, 6):
        announce(devices, i)
    state = runtime[0].snapshot()
    state.update(setup=setup.snapshot(), command_input='')
    frame = fit_terminal(render_session(state), 60, 14)
    for i in range(1, 6):
        assert f'[{i}] track {i}' in frame
    assert 'scegli la traccia' in frame
    assert 'Invio conferma' in frame and '> ▏' in frame
    assert len(frame.splitlines()) <= 13
    setup.submit('1')
    assert setup.step == 'name'


def test_narrow_preparation_preserves_choices_and_typed_answer(tmp_path):
    state, _ = preparation(tmp_path)
    state['setup'].update(step='behavior', notice='Come deve comportarsi questa voce?', choices=[
        dict(value=str(i), label=name) for i, name in enumerate(
            ('motivo melodico', 'accompagnamento', 'tessitura', 'percussioni con riferimenti', 'pattern percussivo'), 1)])
    state['command_input'] = '3'
    frame = fit_terminal(render_session(state), 60, 18)
    assert all(f'[{i}]' in frame for i in range(1, 6))
    assert '> 3▏' in frame and 'Invio conferma' in frame
    assert len(frame.splitlines()) <= 17


def test_default_performance_is_compact_and_details_are_available():
    state = snapshot()
    normal = render_session(state)
    details = render_session(state, details=True)
    assert 'Bass' in normal and 'PARAMETRI' not in normal
    assert 'PARAMETRI' in details and 'density=' in details


def test_screen_is_restored_on_exit_and_unchanged_frames_are_not_redrawn():
    class Terminal(StringIO):
        def isatty(self): return True
    out = Terminal()
    now = [0.]
    view = TerminalSessionView(out, clock=lambda: now[0])
    with pytest.raises(RuntimeError), view:
        view.update(snapshot())
        before = out.getvalue()
        now[0] = 2
        view.update(snapshot())
        assert out.getvalue() == before
        raise RuntimeError('exit')
    assert out.getvalue().startswith('\x1b[?1049h\x1b[?25l')
    assert out.getvalue().endswith('\x1b[?25h\x1b[?1049l')


def terminal_screen(data, width, height):
    """Modello delle operazioni VT100 usate dal pannello, senza conversione ONLCR."""
    import re
    rows = [[' ']*width for _ in range(height)]
    x = y = 0
    for match in re.finditer(r'\x1b\[(\d*)([HJK])|\r|\n|[^\x1b\r\n]+', data):
        number, command = match.groups()
        token = match.group()
        if command == 'H':
            x = y = 0
        elif command == 'J':
            if number == '2':
                rows = [[' ']*width for _ in range(height)]
            else:
                rows[y][x:] = [' ']*(width-x)
                for index in range(y+1, height):
                    rows[index] = [' ']*width
        elif command == 'K':
            rows[y][x:] = [' ']*(width-x)
        elif token == '\r':
            x = 0
        elif token == '\n':
            y += 1
            assert y < height, 'il pannello non deve scorrere'
        else:
            for char in token:
                assert x < width, 'il pannello non deve andare a capo implicitamente'
                rows[y][x] = char
                x += 1
    return '\n'.join(''.join(row).rstrip() for row in rows).rstrip()


@pytest.mark.parametrize('width,height', [(122, 30), (80, 24), (60, 18)])
def test_refresh_removes_old_text_from_shorter_rows_blank_rows_and_footer(tmp_path, monkeypatch, width, height):
    from copy import deepcopy
    from os import terminal_size
    monkeypatch.setattr('desnivel.cli.session_view.shutil.get_terminal_size', lambda: terminal_size((width, height)))
    class Terminal(StringIO):
        def isatty(self): return True
    output = Terminal()
    now = [0.]
    view = TerminalSessionView(output, clock=lambda: now[0])
    state, _ = preparation(tmp_path)
    state['setup']['notice'] = 'Un messaggio precedente molto lungo che deve scomparire del tutto.'
    view.update(state)
    updated = deepcopy(state)
    updated['setup']['tracks'][2]['name'] = 'pad'
    updated['setup']['notice'] = 'Scegli la traccia.'
    updated['setup']['tracks'].pop()
    now[0] = 1
    view.update(updated)
    expected = fit_terminal(render_session(updated), width, height)
    assert terminal_screen(output.getvalue(), width, height) == '\n'.join(line.rstrip() for line in expected.splitlines()).rstrip()
    assert 'molto lungo' not in terminal_screen(output.getvalue(), width, height)
