"""Adattatore del terminale: tastiera e rendering, senza accesso al runtime."""
from contextlib import ExitStack


class TerminalFrontend:
    def __init__(self, *, enabled=True):
        self.enabled = enabled
        self.keyboard = self.view = None
        if enabled:
            from desnivel.cli.session_controls import TerminalControls
            from desnivel.cli.session_view import TerminalSessionView
            self.keyboard, self.view = TerminalControls(), TerminalSessionView()
        self.waiting = False
        self.step = None
        self.stack = ExitStack()

    def __enter__(self):
        if self.enabled:
            self.stack.enter_context(self.keyboard)
            self.stack.enter_context(self.view)
        return self

    def __exit__(self, *args):
        return self.stack.__exit__(*args)

    def commands(self):
        if not self.enabled:
            return
        for action in self.keyboard.poll():
            if action == 'details_toggle':
                self.view.toggle_details()
            elif action.startswith('command:'):
                yield dict(action='setup_reply' if self.waiting else 'setup_command', value=action[len('command:'):])
            else:
                yield {'action': action}

    def synchronize(self, setup):
        if not self.enabled:
            return
        self.waiting = setup.waiting
        if setup.waiting and (self.keyboard.command is None or setup.step != self.step):
            self.keyboard.read_command()
        elif not setup.waiting and self.step is not None:
            self.keyboard.command = None
        self.step = setup.step
        self.view.last_refresh = None

    def update(self, state):
        if self.enabled:
            draft = self.keyboard.command
            local = {**state, 'command_input': draft.encode('latin1').decode('utf-8', errors='replace') if draft is not None else None}
            if draft is not None:
                self.view.last_refresh = None
            self.view.update(local)
