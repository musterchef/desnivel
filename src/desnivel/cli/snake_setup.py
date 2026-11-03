"""Preparazione guidata di Snake, senza bloccare il ciclo della sessione."""
from pathlib import Path
import time

from desnivel.cli.connect_voices import connect_all
from desnivel.cli.snake_control import SnakeControlSession

CHECK_INTERVAL_S = 10.
RECEIVE_PORT = 9201


class SnakeSetup:
    def __init__(self, config_path, sources, main_port, *, clock=time.monotonic,
                 create_session=SnakeControlSession.from_file, connect=connect_all):
        self.config_path = Path(config_path)
        self.sources, self.main_port = sources, main_port
        self.clock, self.create_session, self.connect = clock, create_session, connect
        self.session = None
        self.status = 'idle'
        self.notice = ''
        self.next_check = None
        self.check_requested = False
        self.instructions = []

    @property
    def waiting(self):
        return self.status == 'waiting'

    def begin(self, *, playing, recording_busy=False):
        if playing or recording_busy:
            raise ValueError('ferma Live e termina le operazioni REC prima di preparare Snake')
        if self.status == 'ready' and self.session is not None and not self.session.setup_missing():
            self.notice = 'Snake è già abilitato; ruolo e modalità si scelgono nel suo controllo.'
            return
        if self.session is None:
            self.session = self.create_session(self.config_path, self.sources, self.main_port)
        self.instructions = [
            'In Live crea una traccia MIDI: Snake con Length → Desnivel_Snake_Control → strumento.',
            *[f'Nel controllo imposta voce {name}; Receive {RECEIVE_PORT+index}, Python {self.session.port}.'
              for index, name in enumerate(self.session.components)],
            'Lascia Live in Stop. Invio: verifica subito · Esc: annulla. Controllo automatico ogni 10 s.',
        ]
        self.status, self.notice = 'waiting', 'In attesa di Snake: prepara la traccia in Live.'
        self.check_requested = True

    def confirm(self):
        if self.waiting:
            self.check_requested = True

    def forecasts(self, *args, **kwargs):
        if self.session is None or self.status != 'ready':
            return {}
        return self.session.forecasts(*args, **kwargs)

    def cancel(self):
        if self.waiting:
            self.close()
            self.status, self.notice = 'cancelled', 'Preparazione Snake annullata; la sessione resta disponibile.'
            self.instructions = []

    def tick(self, state):
        if self.session is None:
            return {}
        components = self.session.tick({**state, 'state': 'preparing'} if self.waiting else state)
        if not self.waiting:
            return components
        missing = self.session.setup_missing()
        if not missing:
            self.status, self.notice = 'ready', 'Snake pronto: traccia con strumento e controllo collegati. Puoi premere Play.'
            self.instructions = []
            self.next_check = None
        elif self.check_requested or self.next_check is None or self.clock() >= self.next_check:
            try:
                self.connect(RECEIVE_PORT)
            except OSError as error:
                self.notice = f'Controllo del collegamento Snake non riuscito: {error}'
            else:
                self.notice = 'Snake non ancora pronto: ' + '; '.join(f'{name}: {reason}' for name, reason in missing.items())
            self.next_check = self.clock()+CHECK_INTERVAL_S
            self.check_requested = False
        return components

    def snapshot(self):
        return dict(status=self.status, notice=self.notice, instructions=list(self.instructions),
                    next_check_s=max(0., self.next_check-self.clock()) if self.waiting and self.next_check is not None else None)

    def close(self):
        if self.session is not None:
            self.session.close()
            self.session = None
        self.next_check = None
        self.check_requested = False
