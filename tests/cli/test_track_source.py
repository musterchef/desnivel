import io

from desnivel.cli import track_source


class NonTty(io.StringIO):
    def isatty(self):
        return False


class Tty:
    def __init__(self, text):
        self.text = iter(text)

    def isatty(self):
        return True

    def fileno(self):
        return 7

    def read(self, count):
        return next(self.text, '')

    def readline(self):
        return ''.join(self.text)


def test_non_terminal_keeps_line_input(monkeypatch):
    monkeypatch.setattr('builtins.input', lambda prompt: '05')
    assert track_source.read_stage_choice('Tappa: ', stream=NonTty()) == '05'


def test_o_returns_without_reading_the_rest_of_the_line(monkeypatch):
    stream = Tty('Ocontenuto non letto')
    restored = []
    monkeypatch.setattr('termios.tcgetattr', lambda fd: ['saved'])
    monkeypatch.setattr('termios.tcsetattr', lambda fd, when, state: restored.append(state))
    monkeypatch.setattr('tty.setcbreak', lambda fd: None)

    assert track_source.read_stage_choice('Tappa: ', stream=stream) == 'O'
    assert ''.join(stream.text) == 'contenuto non letto'
    assert restored == [['saved']]


def test_number_keeps_reading_until_enter(monkeypatch):
    stream = Tty('07bis\n')
    monkeypatch.setattr('termios.tcgetattr', lambda fd: ['saved'])
    monkeypatch.setattr('termios.tcsetattr', lambda *args: None)
    monkeypatch.setattr('tty.setcbreak', lambda fd: None)

    assert track_source.read_stage_choice('Tappa: ', stream=stream) == '07bis'
