"""Comandi della sessione e lettura non bloccante della tastiera del terminale."""
import os
import select
import sys


def apply_control(runtime, action):
    """Controlla Live tramite l'adattatore, poi aggiorna il viaggio nello stesso thread."""
    if action == 'weather_toggle':
        runtime.toggle_context('weather')
        return
    if action == 'toggle':
        action = 'resume' if runtime.paused or not runtime.playing else 'pause'
    if action == 'pause' and runtime.paused:
        return
    if action == 'resume' and not runtime.paused and runtime.playing:
        return
    runtime.bridge.control_transport(runtime.transport_voice, action)
    runtime.control(action)


class TerminalControls:
    def __init__(self, stream=None):
        self.stream = stream if stream is not None else sys.stdin
        self.saved = None

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
                key = os.read(self.stream.fileno(), 1).decode('ascii', errors='ignore').lower()
                if not key:
                    break
                if key == ' ':
                    yield 'toggle'
                elif key == 'r':
                    yield 'restart'
                elif key == 'c':
                    yield 'connect'
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
