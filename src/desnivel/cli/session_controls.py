"""Comandi della sessione e lettura non bloccante della tastiera del terminale."""
import os
import select
import sys


class TerminalControls:
    def __init__(self, stream=None):
        self.stream = stream if stream is not None else sys.stdin
        self.saved = None
        self.command = None

    def read_command(self):
        self.command = ''

    def __enter__(self):
        if self.stream.isatty():
            import termios
            import tty
            self.saved = termios.tcgetattr(self.stream.fileno())
            tty.setcbreak(self.stream.fileno())
        return self

    def poll(self):
        if self.saved is not None:
            while select.select([self.stream], [], [], 0)[0]:
                key = os.read(self.stream.fileno(), 1).decode('latin1')
                if not key:
                    break
                if self.command is not None:
                    if key == '\x1b':
                        self.command = None
                        yield 'setup_cancel'
                    elif key in ('\n', '\r'):
                        text = self.command.encode('latin1').decode('utf-8', errors='replace')
                        self.command = None
                        yield 'command:'+text
                    elif key in ('\x7f', '\b'):
                        data = self.command.encode('latin1').decode('utf-8', errors='ignore')[:-1]
                        self.command = data.encode('utf-8').decode('latin1')
                    elif ord(key) >= 32:
                        self.command += key
                    continue
                key = key.lower()
                if key == ':':
                    self.read_command()
                    continue
                if key == ' ':
                    yield 'toggle'
                elif key == 'r':
                    yield 'restart'
                elif key == 'c':
                    yield 'scan'
                elif key == 'n':
                    yield 'component_prepare'
                elif key == 'a':
                    yield 'setup_begin'
                elif key == 'b':
                    yield 'setup_associate'
                elif key == 't':
                    yield 'scan'
                elif key == 'v':
                    yield 'setup_save'
                elif key == 'd':
                    yield 'details_toggle'
                elif key in ('\n', '\r'):
                    yield 'component_check'
                elif key == '\x1b':
                    yield 'setup_cancel'
                elif key == 'm':
                    yield 'weather_toggle'
                elif key in '123':
                    yield {'1': 'record_audio', '2': 'record_midi', '3': 'record_both'}[key]
                elif key == 'g':
                    yield 'record_start'
                elif key == 's':
                    yield 'record_stop'

    def __exit__(self, *args):
        if self.saved is not None:
            import termios
            termios.tcsetattr(self.stream.fileno(), termios.TCSADRAIN, self.saved)
