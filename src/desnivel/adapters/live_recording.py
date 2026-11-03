"""Preparazione e registrazione in Live attraverso il device del trasporto."""
import time

RECORDING_ACTIONS = {'record_audio', 'record_midi', 'record_both', 'record_start', 'record_stop'}


class LiveRecording:
    def __init__(self, bridge, voice, restart, epoch, clock=time.monotonic):
        self.bridge, self.voice = bridge, voice
        self.restart, self.epoch, self.clock = restart, epoch, clock
        self.status, self.mode, self.error = 'unprepared', None, None
        self.tracks = []
        self.request = 0
        self.deadline = None
        self.rewind_epoch = None

    def _send(self, action, status):
        self.request += 1
        self.bridge.control_recording(self.voice, action, self.request, self.mode)
        self.status, self.error = status, None
        self.deadline = self.clock() + (60 if action == 'prepare' else 8)

    def control(self, action):
        if action not in RECORDING_ACTIONS:
            raise ValueError('comando di registrazione sconosciuto')
        if action == 'record_stop':
            self._send('stop', 'stopping')
            return
        if self.status in ('preparing', 'rewinding', 'starting', 'stopping', 'recording'):
            raise ValueError('terminare la registrazione o l’operazione corrente prima di procedere')
        self.bridge.require_recording(self.voice)
        if action == 'record_start':
            if self.status != 'ready' or not self.tracks:
                raise ValueError('preparare prima le tracce REC: 1 audio, 2 MIDI, 3 entrambi')
            self.rewind_epoch = self.epoch()
            self.restart()
            self.status, self.error = 'rewinding', None
            self.deadline = self.clock()+8
        else:
            self.restart()
            self.mode = action.removeprefix('record_')
            self._send('prepare', 'preparing')

    def on_message(self, message):
        if message['voice'] != self.voice:
            return
        if self.status == 'rewinding' and message['action'] in ('hello', 'transport'):
            transport = message.get('transport', {})
            if (transport.get('playing') == 0 and transport.get('beat') == 0
                    and transport.get('epoch') != self.rewind_epoch):
                self._send('start', 'starting')
        if message['action'] != 'recording_status':
            return
        report = message.get('report', {})
        if report.get('request') != self.request or self.status not in ('preparing', 'starting', 'stopping', 'recording'):
            return
        expected = {'preparing': 'ready', 'starting': 'recording', 'stopping': 'ready', 'recording': 'ready'}[self.status]
        if report.get('status') not in (expected, 'error'):
            return
        self.status = report['status']
        self.error = report.get('error')
        self.tracks = report.get('tracks', self.tracks)
        self.deadline = None

    def tick(self, finished=False):
        if self.deadline is not None and self.clock() > self.deadline:
            self.status, self.error = 'error', 'nessuna conferma dal device per la registrazione'
            self.deadline = None
        if finished and self.status == 'recording':
            try:
                self.control('record_stop')
            except (ValueError, OSError) as error:
                self.status, self.error = 'error', str(error)

    def snapshot(self):
        return dict(status=self.status, mode=self.mode, error=self.error, tracks=self.tracks)
