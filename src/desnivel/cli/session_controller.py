"""Controllo della sessione nel thread proprietario, indipendente dalle interfacce."""
import time

from desnivel.adapters.live_recording import LiveRecording, RECORDING_ACTIONS
from desnivel.cli.connect_voices import connect_all
from desnivel.cli.session_commands import validate_command
from desnivel.cli.session_config import reconfigure_runtime, resolve_configuration
from desnivel.cli.session_setup import SessionSetup


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


class SessionController:
    def __init__(self, runtime, source_config, path, server, library, components, *,
                 direction=None, port=9006, connect_port=9101, clock=time.monotonic):
        self.runtime, self.server, self.library, self.components = runtime, server, library, components
        self.direction, self.port, self.connect_port, self.clock = direction, port, connect_port, clock
        self.error = None
        self.setup_paused = False
        self.restart_deadline = None
        self.recording = LiveRecording(runtime.bridge, runtime.transport_voice,
            lambda: self.control('restart'), lambda: self.runtime.epoch)
        self.setup = SessionSetup(source_config, path, server.devices, self.configure, self.can_edit, port=port)
        server.on_message, server.on_error = self.on_message, self.report_error

    def report_error(self, message):
        self.error = str(message)

    def can_edit(self):
        reason = self.edit_block_reason()
        if reason:
            raise ValueError(reason)

    def edit_block_reason(self):
        if self.restart_deadline is not None:
            return 'attendi il completamento del ritorno a zero'
        if (self.runtime.playing or any(d['playing'] for d in self.server.devices.available())
                or self.recording.status in ('preparing', 'rewinding', 'starting', 'stopping', 'recording')):
            return 'ferma Live e termina le operazioni REC prima di modificare le tracce'
        if self.components.waiting:
            return 'completa o annulla prima la preparazione del componente'
        return None

    def configure(self, candidate):
        resolved = resolve_configuration(self.runtime.track, candidate, self.direction)
        components = self.components.candidate(candidate)
        replacement = reconfigure_runtime(self.runtime, resolved, self.library, external_voices=components.voices)
        components.attach(replacement)
        self.runtime, self.components = replacement, components
        self.server.bridge = replacement.bridge
        self.recording.bridge, self.recording.voice = replacement.bridge, replacement.transport_voice
        self.recording.status, self.recording.tracks, self.recording.mode = 'unprepared', [], None
        self.recording.error, self.recording.deadline = None, None

    def on_message(self, bridge, message):
        self._expire_restart()
        self.runtime.on_message(bridge, message)
        restart_after_stop = (self.restart_deadline is not None and message['voice'] == self.runtime.transport_voice
                and message['instance'] == self.runtime.instance
                and message['serial'] == self.runtime.transport_serial and not self.runtime.playing)
        if restart_after_stop:
            self.restart_deadline = None
            try:
                apply_control(self.runtime, 'restart')
                self.error = None
            except (ValueError, OSError) as error:
                self._cancel_restart(error)
        self.components.on_message(bridge, message)
        # La conferma di Stop precede il riavvolgimento: REC attende quella successiva a zero.
        if not restart_after_stop:
            self.recording.on_message(message)

    def _expire_restart(self):
        if self.restart_deadline is not None and self.clock() >= self.restart_deadline:
            self._cancel_restart('ritorno a zero annullato: nessuna conferma di Stop da Live')

    def _cancel_restart(self, error):
        self.restart_deadline = None
        self.report_error(error)
        if self.recording.status == 'rewinding':
            self.recording.status, self.recording.error = 'error', self.error
            self.recording.deadline = None

    def control(self, action):
        """Durante Play, riavvolge solo dopo la conferma di Stop del trasporto."""
        if self.restart_deadline is not None:
            if action == 'restart':
                return
            if action in ('resume', 'toggle'):
                raise ValueError('attendi la conferma di Stop prima di riprendere')
        if action == 'restart' and self.runtime.playing:
            # La pausa locale può essere già attiva mentre lo Stop è ancora in volo.
            apply_control(self.runtime, 'pause')
            self.restart_deadline = self.clock()+3
            return
        apply_control(self.runtime, action)

    def scan(self):
        devices = self.server.devices.available() or self.server.devices.unannounced()
        connect_all(devices[0]['reply_port'] if devices else self.connect_port)

    def execute(self, command):
        """Applica un comando validato; gli errori restano nello stato condiviso."""
        try:
            command = validate_command(command)
            action = command['action']
            if (self.components.waiting or self.setup_paused) and (action in ('resume', 'record_start')
                    or action == 'toggle' and (self.runtime.paused or not self.runtime.playing)):
                raise ValueError('completa la preparazione del componente oppure annullala prima di riprendere')
            if action in ('setup_begin', 'setup_associate', 'setup_save', 'scan'):
                if self.setup.waiting:
                    raise ValueError('completa o annulla prima la domanda corrente')
                text = {'setup_begin': 'aggiungi traccia', 'setup_associate': 'associa',
                        'setup_save': 'salva', 'scan': 'tracce'}[action]
                self.setup.submit(text)
                if action == 'scan':
                    self.scan()
            elif action == 'setup_reply':
                if not self.setup.waiting:
                    raise ValueError('nessuna domanda in attesa')
                self.setup.submit(command['value'])
            elif action == 'setup_command':
                self.setup.submit(command['value'])
            elif action == 'setup_cancel':
                self.components.cancel()
                self.setup.cancel()
            elif action == 'component_prepare':
                if 'arrangement' in self.setup.config:
                    if self.setup.waiting:
                        raise ValueError('completa o annulla prima la domanda corrente')
                    self.setup.submit('aggiungi traccia')
                else:
                    waiting = self.components.waiting
                    self.components.prepare(playing=self.runtime.playing, recording_busy=self.recording.status in (
                        'preparing', 'rewinding', 'starting', 'stopping', 'recording'))
                    if self.components.waiting and not waiting:
                        self.runtime.control('pause')
                        self.setup_paused = True
            elif action == 'component_check':
                self.components.confirm()
            elif action in RECORDING_ACTIONS:
                self.recording.control(action)
            else:
                self.control(action)
            self.error = None
            return True
        except (ValueError, KeyError, TypeError, OSError) as error:
            self.report_error(error)
            return False

    def tick(self):
        self._expire_restart()
        try:
            self.setup.tick(self.clock())
        except OSError as error:
            self.report_error(f'collegamento dei device: {error}')
        conflicts = [device for device in self.server.devices.available()
                     if device['error'] and device['device_id'] in self.setup.config.get('live_bindings', {}).values()]
        if conflicts:
            self.runtime.fail('associazione Live ambigua: '+conflicts[0]['error'])
        try:
            if self.components.waiting or self.setup_paused:
                if self.runtime.playing:
                    self.runtime.bridge.control_transport(self.runtime.transport_voice, 'pause')
                    self.runtime.control('pause')
                elif not self.components.waiting:
                    self.runtime.control('resume')
                    self.setup_paused = False
                    self.runtime.tick()
            else:
                self.runtime.tick()
        except (ValueError, KeyError, TypeError, OSError) as error:
            self.runtime.fail(error)
        state = self.runtime.snapshot()
        self.recording.tick(finished=self.runtime.state == 'finished')
        state['recording'] = self.recording.snapshot()
        state['components'] = self.components.tick(state)
        state['setup'] = self.components.setup_state() or self.setup.snapshot(voices=state['voices'])
        state['configuration'] = {'name': self.setup.path.stem, 'path': str(self.setup.path)}
        reason = self.edit_block_reason()
        state['controls'].update(edit_allowed=reason is None, edit_reason=reason,
                                 restart_pending=self.restart_deadline is not None,
                                 setup_enabled='arrangement' in self.setup.config,
                                 transport_connected=self.runtime.bridge.connected(self.runtime.transport_voice))
        state['control_error'] = self.error
        return state

    def close(self):
        self.restart_deadline = None
        self.runtime.reset()
        self.runtime.playing = False
        self.runtime.state = 'closed'
        self.components.close()
        if self.recording.status in ('recording', 'preparing', 'starting', 'rewinding'):
            self.execute({'action': 'record_stop'})
        state = self.runtime.snapshot()
        state['control_error'] = self.error
        return state
