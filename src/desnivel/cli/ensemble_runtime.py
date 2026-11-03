"""Sessione continua con replay lineare o timeline allocata in beat."""
from __future__ import annotations

from bisect import bisect_right
from copy import deepcopy
import math
import time

import numpy as np

from desnivel.adapters.voice_device import DeviceVoice
from desnivel.cli.ensemble import EnsembleSession
from desnivel.cli.generators import build_generator
from desnivel.cli.window_context import WindowContext
from desnivel.music.phrases import Phrase
from desnivel.music.timeline import TimelineManager, allocate_timeline


class EnsembleRuntime:
    def __init__(self, track, config, bridge, speed=1., clock=time.monotonic, *, timing="linear", adaptive=True,
                 context_sources=()):
        if type(adaptive) is not bool:
            raise ValueError('adaptive richiede un booleano')
        if not math.isfinite(speed) or speed <= 0:
            raise ValueError('speed deve essere positiva e finita')
        self.track, self.bridge, self.speed, self.clock = track, bridge, speed, clock
        self.window, self.lead = config['window_beats'], config['lead_beats']
        if any(type(x) not in (int, float) or not math.isfinite(x) or x <= 0 for x in (self.window, self.lead)):
            raise ValueError('finestra e anticipo devono essere positivi e finiti')
        distances = track.samples.get('cum_dist_m')
        if distances is None or len(distances) != len(track.t) or not len(track.t):
            raise ValueError('traccia con distanza cumulativa richiesta')
        self.distances = distances
        if not np.all(np.isfinite(distances)) or distances[-1] <= distances[0] or track.duration_s <= 0:
            raise ValueError('durata e distanza della traccia devono essere positive')
        if timing not in ('linear', 'allocated'):
            raise ValueError('timing deve essere linear o allocated')
        self.timing = timing
        self.timeline = None
        self.pending_windows = []
        self.next_window = 0
        self.section_progress = tuple(s['from_progress'] for s in config['sections'])
        if timing == 'allocated':
            if any(not s.get('trip') for s in config['sections']):
                raise ValueError('la modalità allocated richiede macrosezioni GPX')
            settings = config['timeline']
            if not isinstance(settings, dict) or set(settings) not in ({'target_beats', 'min_windows', 'distance_exponent'},
                                                                      {'beats_per_km', 'min_windows', 'distance_exponent'}):
                raise ValueError('timeline richiede beats_per_km oppure target_beats, con min_windows e distance_exponent')
            plan = allocate_timeline(
                [s['trip']['end_distance_m']-s['trip']['start_distance_m'] for s in config['sections']],
                window_beats=self.window, **settings)
            self.timeline = TimelineManager(plan)
        self.transport_voice = config['transport_voice']
        if self.transport_voice not in config['voices']:
            raise ValueError('transport_voice non registrata')
        self.elapsed = 0.
        self.playing = False
        self.beat = 0.
        self.bpm = None
        self.epoch = None
        self._restart_epoch = None
        self.instance = None
        self.transport_serial = -1
        self.error = None
        self.paused = False
        self.restart_count = 0
        self.last_update = clock()
        self.planned_start = None
        self.last_section = None
        self.last_decisions = None
        self._sent_plans = []
        self.sounding = set()
        self.registry = {}
        self.voice_descriptions = {name: {'name': spec.get('name', name), 'generator': spec['generator'],
                                         'dependencies': list(spec.get('dependencies', [])),
                                         'optional_dependencies': list(spec.get('optional_dependencies', []))}
                                   for name, spec in config['voices'].items()}
        self.window_context = WindowContext(track, config.get('trip_analysis'))
        self.context_sources = tuple(context_sources)
        names = set()
        for source, interpret, enabled in self.context_sources:
            source.check_track(track)
            name = source.data['source']
            if name in names or type(enabled) is not bool or interpret is not None and not callable(interpret):
                raise ValueError('sorgenti di contesto distinte con interprete e attivazione validi richieste')
            names.add(name)
        # Anche il confronto con una sorgente disattivata conserva le altre
        # politiche adattive, indipendentemente dalla presenza del profilo.
        self.adaptation_enabled = adaptive and (self.window_context.profile is not None
                                                or any(fn is not None for _, fn, _ in self.context_sources))
        session_config = deepcopy({k: v for k, v in config.items() if k != 'trip_analysis'})
        self.trip_music = deepcopy(config.get('trip_music'))
        self.section_directions = tuple(deepcopy(section.get('direction')) for section in config['sections'])
        self.section_sources = tuple(deepcopy(section.get('trip')) for section in config['sections'])
        destinations = {}
        for name, voice in session_config['voices'].items():
            definition = config['generators'][voice['generator']]
            self.registry[name] = build_generator(definition)
            if definition['type'] == 'responsive_line' and len(voice.get('dependencies', [])) != 1:
                raise ValueError('responsive_line richiede una dipendenza')
            voice['generator'] = name  # Ogni voce ha il proprio generatore e il proprio stato.
            destination = voice['destination']
            if destination in destinations:
                raise ValueError('ogni voce richiede una destinazione distinta')
            bridge.voices[name] = DeviceVoice()
            destinations[destination] = bridge.destination(name)
        self.session = EnsembleSession(session_config, {name: spec.generator for name, spec in self.registry.items()}, destinations)
        if self.session.coordinator.rhythm_source is None and any(
                spec.values.get('groove_follow', 0) for spec in self.registry.values()):
            raise ValueError('groove_follow richiede rhythm_voice nella configurazione')
        for name, registered in self.registry.items():
            def describe_controls(role, parameters, registered=registered):
                details = registered.describe_controls(role, parameters) if registered.describe_controls else {}
                if self.session.coordinator.rhythm_source is None and 'groove_follow' in registered.controls:
                    details['groove_follow'] = {'inactive_reason': 'Richiede rhythm_voice nella configurazione'}
                return details
            bridge.voices[name] = DeviceVoice.for_session(
                self.session, name, lambda: self.progress, beat=lambda: self.beat,
                controls=registered.controls, values=registered.values, presets=registered.presets,
                describe_controls=describe_controls, preset_defaults=registered.preset_defaults,
                migrate_preset=registered.migrate_preset)
            bridge.voices[name].read_weather = lambda name=name: self.weather_status(name)
        self.state = 'waiting_for_transport'

    def toggle_context(self, name):
        """Cambia il contributo alle finestre future, conservando i piani già inviati."""
        if not any(source.data['source'] == name for source, _, _ in self.context_sources):
            raise ValueError(f'contesto {name} non caricato: caricalo all’avvio della sessione')
        if not self.adaptation_enabled:
            raise ValueError('adattamento automatico non attivo')
        self.context_sources = tuple((source, interpret, not enabled if source.data['source'] == name else enabled)
                                     for source, interpret, enabled in self.context_sources)

    def weather_status(self, voice):
        from desnivel.adapters.weather_status import describe_weather
        source = next((item for item in self.context_sources if item[0].data['source'] == 'weather'), None)
        current = next((plan for plan in self._sent_plans
                        if plan['start'] <= self.beat < plan['start']+plan['length_beats']), None)
        if not self.playing or self.state != 'playing':
            current = None
        return describe_weather(source is not None, bool(source and source[2] and self.adaptation_enabled),
                                current, voice, lambda name: self.session.manual(voice, name))

    @property
    def progress(self):
        if self.timeline:
            if self.timeline.finished:
                return 1.
            fraction = 0.
            if self.pending_windows and self.pending_windows[0][0] <= self.beat:
                fraction += min(1., (self.beat-self.pending_windows[0][0])/self.window)
            index, fraction = self.timeline.timeline.position(self.timeline.window_index, fraction)
            start = self.section_progress[index]
            end = self.section_progress[index+1] if index+1 < len(self.section_progress) else 1.
            # Il confine appartiene alla sezione successiva solo dopo il consumo.
            return min(math.nextafter(end, start), start+(end-start)*fraction)
        distance = float(np.interp(self.track.t[0]+self.elapsed, self.track.t, self.distances))
        return min(1., max(0., (distance-self.distances[0])/(self.distances[-1]-self.distances[0])))

    def reset(self):
        for name in self.sounding:
            if self.bridge.connected(name):
                self.bridge.reset(name)
        self.sounding.clear()
        self.planned_start = None
        self.pending_windows.clear()
        if self.timeline:
            self.next_window = self.timeline.window_index
        self.last_section = None
        self.last_decisions = None
        self._sent_plans.clear()
        self.session.coordinator.reset()
        for registered in self.registry.values():
            if registered.reset:
                registered.reset()

    def on_message(self, bridge, message):
        if message['voice'] != self.transport_voice:
            return
        if message['instance'] == self.instance and message['serial'] <= self.transport_serial:
            return
        transport = message.get('transport', {})
        beat, playing, epoch = transport.get('beat'), transport.get('playing'), transport.get('epoch')
        bpm = transport.get('bpm')
        if (type(beat) not in (int, float) or not math.isfinite(beat) or beat < 0
                or type(playing) is not int or playing not in (0, 1)
                or type(epoch) is not int or epoch < 0):
            raise ValueError('stato del trasporto non valido')
        if bpm is not None and (type(bpm) not in (int, float) or not math.isfinite(bpm) or bpm <= 0):
            raise ValueError('BPM del trasporto positivo e finito richiesto')
        # Durante il riavvolgimento possono arrivare notifiche inviate prima
        # del comando. Il device cambia epoch allo Stop o al ritorno al beat zero.
        if self._restart_epoch is not None:
            if self.instance == message['instance'] and epoch <= self._restart_epoch:
                self.transport_serial = message['serial']
                return
            self._restart_epoch = None
        self.advance()
        if self.instance == message['instance'] and beat >= self.beat and self.epoch == epoch:
            self._consume_windows(beat)
        if self.instance != message['instance'] or self.epoch != epoch or beat < self.beat or not playing:
            self.reset()
        self.instance, self.transport_serial = message['instance'], message['serial']
        self.beat, self.playing, self.epoch = beat, bool(playing), epoch
        self.bpm = bpm

    def control(self, action):
        """Controlli della sessione, eseguiti nello stesso thread della pianificazione."""
        if action not in ('pause', 'resume', 'restart'):
            raise ValueError('comando della sessione non supportato')
        self.advance()
        if action == 'restart':
            self.reset()
            self.elapsed = 0.
            if self.timeline:
                self.timeline.reset()
            self.next_window = 0
            self.error = None
            self.paused = False
            self._restart_epoch = self.epoch
            self.playing = False
            self.beat = 0.
            self.restart_count += 1
            self.state = 'stopped'
        elif action == 'pause':
            self._consume_windows(self.beat)
            self.reset()
            self.paused = True
            if self.state != 'finished':
                self.state = 'paused'
        else:
            self.paused = False
            if self.state == 'paused':
                self.state = 'waiting_for_transport'
        self.last_update = self.clock()

    def advance(self):
        now = self.clock()
        delta, self.last_update = max(0., now-self.last_update), now
        if (self.playing and self.state == 'playing' and self.bridge.connected(self.transport_voice) and not self.error
                and not self.timeline):
            self.elapsed = min(self.track.duration_s, self.elapsed+delta*self.speed)

    def _consume_windows(self, beat):
        if not self.timeline or self.state != 'playing':
            return
        while self.pending_windows and beat >= self.pending_windows[0][0]+self.window:
            self.pending_windows.pop(0)
            self.timeline.advance()

    def tick(self):
        self.advance()
        if self.error:
            self.state = 'error'
            return
        self._consume_windows(self.beat)
        if (self.timeline.finished if self.timeline else self.elapsed >= self.track.duration_s):
            self.state = 'finished'
            self.reset()
            return
        if self.paused:
            self.state = 'paused'
            return
        plan_progress = self.progress
        if self.timeline and self.next_window < self.timeline.timeline.total_windows:
            ends = [span.end_window for span in self.timeline.timeline.spans]
            index = bisect_right(ends, self.next_window)
            plan_progress = self.section_progress[index]
        assignments = self.session.director.assignments_at(plan_progress)
        if not self.bridge.connected(self.transport_voice):
            self.state = 'waiting_for_transport'
        elif not self.playing:
            self.state = 'stopped'
        elif any(not self.bridge.connected(name) for name in assignments):
            self.state = 'waiting_for_devices'
        else:
            self.state = 'playing'
        if self.state != 'playing':
            if self.sounding or self.pending_windows:
                self.reset()
            return
        if self.timeline and self.next_window == self.timeline.timeline.total_windows:
            return  # L'ultima finestra deve ancora concludersi in Live.
        start = math.ceil((self.beat+self.lead)/self.window)*self.window
        if start == self.planned_start:
            return
        context = self.session.director.context_at(plan_progress)
        source_context = (self.window_context.allocated(self.timeline.timeline, self.section_sources, self.next_window)
                          if self.timeline else self.window_context.linear(
                              elapsed_s=self.elapsed, live_beat=self.beat, start_beat=start,
                              length_beats=self.window, bpm=self.bpm, speed=self.speed))
        # I cambi di organico si applicano alla prossima finestra, con frasi vuote
        # per le parti uscenti: la finestra già iniziata può concludersi.
        from desnivel.cli.trip_direction import adaptive_context
        intent = adaptive_context(source_context) if self.adaptation_enabled else None
        if self.context_sources:
            source_context['environment'] = {}
            for source, interpret, enabled in self.context_sources:
                description = source.describe(source_context.get('parts', []))
                description['interpretation_enabled'] = bool(enabled and interpret is not None and self.adaptation_enabled)
                source_context['environment'][source.data['source']] = description
                if description['interpretation_enabled']:
                    intent = interpret(intent, description)
        phrases = self.session.plan(plan_progress, start, self.window, adaptive_context=intent)
        for name in self.sounding - phrases.keys():
            if self.bridge.connected(name):
                self.bridge.destination(name)(start, Phrase(self.window, ()))
        self.sounding |= set(phrases)
        self.session.send(start, phrases)
        self.sounding = set(phrases)
        if self.timeline:
            self.pending_windows.append((start, self.next_window))
            self.next_window += 1
        self.planned_start, self.last_section = start, context.name
        self.last_decisions = {**self.session.coordinator.last_plan, 'section': context.name,
                               'section_index': context.section_index,
                               'root': context.root, 'scale': context.scale,
                               'direction': self.section_directions[context.section_index],
                               'trip': self.section_sources[context.section_index],
                               'local_trip': source_context}
        self.last_decisions['adaptive_context'] = vars(intent) if intent is not None else None
        self._sent_plans = [plan for plan in self._sent_plans
                            if plan['start']+plan['length_beats'] > self.beat]
        self._sent_plans.append(deepcopy(self.last_decisions))

    def fail(self, error):
        self.error = str(error)
        self.reset()
        self.state = 'error'

    def snapshot(self):
        context = self.session.director.context_at(self.progress)
        distance = self.distances[0]+self.progress*(self.distances[-1]-self.distances[0])
        elapsed = (float(np.interp(distance, self.distances, self.track.t))-self.track.t[0]
                   if self.timeline else self.elapsed)
        current_plan = next((plan for plan in self._sent_plans
                             if plan['start'] <= self.beat < plan['start']+plan['length_beats']), None)
        upcoming = [plan for plan in self._sent_plans if plan['start'] > self.beat]
        return {'timing': self.timing,
                'trip_music': self.trip_music,
                'timeline': ({**self.timeline.snapshot(), 'total_beats': self.timeline.timeline.total_beats,
                              'requested_beats': self.timeline.timeline.requested_beats,
                              'beats_per_km': self.timeline.timeline.beats_per_km,
                              'adjustments': self.timeline.timeline.to_dict()['adjustments']}
                             if self.timeline else None),
                'version': 1, 'state': self.state, 'error': self.error,
                'adaptation_enabled': self.adaptation_enabled,
                'controls': {'paused': self.paused, 'restart_count': self.restart_count,
                             'contexts': {source.data['source']: {'enabled': enabled}
                                          for source, _, enabled in self.context_sources}},
                'decisions': {'director': self.session.director.decision_at(self.progress),
                              'coordinator': self.last_decisions},
                'trip': {'stage': self.track.stage_id, 'elapsed_s': elapsed,
                         'duration_s': self.track.duration_s, 'progress': self.progress, 'speed': self.speed,
                         'distance_m': float(distance),
                         'total_distance_m': float(self.distances[-1])},
                'section': {'index': context.section_index, 'name': context.name,
                            'root': context.root, 'scale': context.scale,
                            'direction': self.section_directions[context.section_index],
                            'trip': self.section_sources[context.section_index]},
                'transport': {'voice': self.transport_voice, 'playing': self.playing,
                              'beat': self.beat, 'epoch': self.epoch, 'bpm': self.bpm},
                'planning': {'next_start': self.planned_start, 'section': self.last_section,
                             'window_beats': self.window,
                             'current': current_plan if self.playing and self.state == 'playing' else None,
                             'upcoming': upcoming}, 'voices': {name: {**self.voice_descriptions[name], **state}
                           for name, state in self.bridge.status().items()}}
