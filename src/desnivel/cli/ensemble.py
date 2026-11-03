"""Collegamento di configurazione, generatori Python e destinazioni delle voci."""
from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable, Mapping

from desnivel.music.arrangement import Assignment
from desnivel.music.coordinator import MusicCoordinator, Voice, PlanningRequest
from desnivel.music.director import MusicDirector
from desnivel.music.phrases import Phrase
from desnivel.music.interactions import RhythmRelation


@dataclass(frozen=True)
class Generator:
    generate: Callable[[PlanningRequest], Phrase]
    supported_roles: tuple[str, ...]
    validate: Callable | None = None
    describe: Callable | None = None
    stage: Callable | None = None
    accept: Callable | None = None
    prepare_reference: Callable | None = None
    rhythmic_roles: tuple[str, ...] = ()
    accept_reference: Callable | None = None
    parameter_defaults: Mapping = field(default_factory=dict)
    adapt: Callable | None = None


class EnsembleSession:
    """Carica dati JSON già letti e collega implementazioni fornite dal chiamante.

    Le destinazioni ricevono inizio in beat e frase. Adattamento e trasporto
    sono responsabilità delle funzioni registrate, non del motore musicale.
    """

    def __init__(self, config: dict, generators: Mapping[str, Generator],
                 destinations: Mapping[str, Callable[[float, Phrase], None]]):
        config = deepcopy(config)
        if config['selection_mode'] != 'manual':
            raise ValueError('selection_mode deve essere manual')
        voices = {}
        self._destinations = {}
        self._generators = {}
        for name, spec in config['voices'].items():
            generator = generators[spec['generator']]
            self._generators[name] = generator
            voices[name] = Voice(generator.generate, tuple(spec.get('dependencies', ())),
                                 generator.supported_roles, generator.describe,
                                 tuple(spec.get('optional_dependencies', ())),
                                 generator.stage, generator.accept, generator.prepare_reference,
                                 generator.rhythmic_roles, generator.accept_reference, generator.adapt, generator.validate)
            self._destinations[name] = destinations[spec['destination']]
        self.director = MusicDirector(config['sections'])
        for voice in voices.values():
            optional = voice.optional_dependencies
            if (any(name not in voices for name in optional)
                    or len(set(optional)) != len(optional) or set(optional) & set(voice.dependencies)):
                raise ValueError('dipendenze facoltative sconosciute, duplicate o già obbligatorie')
        self._section_progress = tuple(section['from_progress'] for section in config['sections'])
        # Valida tutte le sezioni prima della prima generazione o trasmissione.
        for section in config['sections']:
            assignments = self.director.assignments_at(section['from_progress'])
            for name, assignment in assignments.items():
                if name not in voices:
                    raise ValueError(f'voce non registrata: {name}')
                if assignment.role not in voices[name].supported_roles:
                    raise ValueError(f'ruolo non supportato: {name}/{assignment.role}')
                if self._generators[name].validate:
                    self._generators[name].validate(assignment.role, assignment.parameters)
            pending, available = set(assignments), set()
            while pending:
                ready = {name for name in pending if (set(voices[name].dependencies)
                         | (set(voices[name].optional_dependencies) & assignments.keys())) <= available}
                if not ready:
                    raise ValueError('dipendenze mancanti o cicliche nella sezione')
                pending -= ready
                available |= ready
        relations = tuple(RhythmRelation.from_dict(data) for data in config.get('relations', []))
        self.coordinator = MusicCoordinator(voices, rhythm_source=config.get('rhythm_voice'),
                                           relations=relations, history_beats=config.get('history_beats', 64.))
        for progress in self._section_progress:
            for name, assignment in self.director.assignments_at(progress).items():
                if assignment.parameters.get('groove_follow', 0) and self.coordinator.rhythm_source is None:
                    raise ValueError('groove_follow richiede rhythm_voice nella configurazione')
        self._manual_parameters = {}
        self._parameter_progress = 0.
        self._presence_multipliers = {}
        self._supported_roles = {name: spec.supported_roles for name, spec in voices.items()}

    @classmethod
    def from_file(cls, path, generators, destinations):
        """Legge una configurazione JSON e collega i componenti registrati."""
        return cls(json.loads(Path(path).read_text()), generators, destinations)

    def plan(self, progress: float, start: float, length_beats: float, *, adaptive_context=None, external_sources=None):
        """Produce le frasi della sezione senza inviarle alle destinazioni."""
        assignments = {
            name: Assignment(spec.role, self.base_parameters_at(name, progress) if adaptive_context is not None
                             else {**self.base_parameters_at(name, progress), **self._manual_parameters.get(name, {})},
                             self.presence_state(name, progress)['effective'])
            for name, spec in self.director.assignments_at(progress).items()
        }
        phrases = self.coordinator.plan(
            start, length_beats, self.director.context_at(progress), assignments=assignments,
            rhythm_parameters=(self.base_parameters_at(self.coordinator.rhythm_source, progress)
                               if adaptive_context is not None else
                               {**self.base_parameters_at(self.coordinator.rhythm_source, progress),
                                **self._manual_parameters.get(self.coordinator.rhythm_source, {})})
            if self.coordinator.rhythm_source is not None else None,
            adaptive_context=adaptive_context, manual_parameters=self._manual_parameters, external_sources=external_sources)
        self._parameter_progress = progress
        return {name: phrase for name, phrase in phrases.items() if name in self._destinations}

    def set_role(self, voice: str, role: str | None):
        """Valida la scelta manuale prima di comunicarla al Director."""
        if voice not in self._supported_roles:
            raise ValueError('voce non registrata')
        if role is not None and role not in self._supported_roles[voice]:
            raise ValueError(f'ruolo non supportato: {voice}/{role}')
        validator = self._generators[voice].validate
        if validator:
            for progress in self._section_progress:
                section = self.director.section_assignments_at(progress)
                if voice in section:
                    spec = section[voice]
                    validator(role or spec.role, {**spec.parameters, **self._manual_parameters.get(voice, {})})
        self.director.set_role(voice, role)

    def role_state(self, voice: str, progress: float):
        """Stato del ruolo per il dispositivo, comprese le voci inattive."""
        if voice not in self._supported_roles:
            raise ValueError('voce non registrata')
        section = self.director.section_assignments_at(progress).get(voice)
        manual = self.director.manual_role(voice)
        return {
            'presence': self.presence_state(voice, progress),
            'supported_roles': list(self._supported_roles[voice]),
            'role_mode': 'manual' if manual is not None else 'section',
            'section_role': section.role if section else None,
            'role': manual if manual is not None else (section.role if section else None),
            'active': section is not None,
            'inactive_reason': None if section else 'not_assigned_to_section',
            'next_entry_progress': next((start for start in self._section_progress
                                         if start > progress and voice in self.director.section_assignments_at(start)), None)
                                   if section is None else None,
        }

    def presence_state(self, voice: str, progress: float):
        """Quota automatica della sezione e moltiplicatore manuale della voce."""
        if voice not in self._generators:
            raise ValueError('voce non registrata')
        assignment = self.director.section_assignments_at(progress).get(voice)
        automatic = assignment.presence if assignment else 0.
        multiplier = self._presence_multipliers.get(voice, 1.)
        return {'automatic': automatic, 'multiplier': multiplier,
                'effective': min(1., automatic * multiplier)}

    def set_presence_multiplier(self, voice: str, value: float):
        if voice not in self._generators:
            raise ValueError('voce non registrata')
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 10:
            raise ValueError('moltiplicatore della presenza richiesto tra 0 e 10')
        self._presence_multipliers[voice] = value

    def base_parameters_at(self, voice: str, progress: float):
        if voice not in self._generators:
            raise ValueError('voce non registrata')
        assignment = self.director.assignments_at(progress).get(voice)
        return {**self._generators[voice].parameter_defaults,
                **(assignment.parameters if assignment else {})}

    def parameters_at(self, voice: str, progress: float, *, beat=None):
        details = self.coordinator.parameter_states_at(voice, beat)
        return {**self.base_parameters_at(voice, progress),
                **{name: state['effective'] for name, state in details.items()},
                **self._manual_parameters.get(voice, {})}

    def manual(self, voice: str, name: str):
        if voice not in self._generators:
            raise ValueError('voce non registrata')
        return name in self._manual_parameters.get(voice, {})

    def set_manual(self, voice: str, name: str, value: bool, *, progress=None, beat=None):
        """Mantiene un parametro o lo restituisce agli assetti delle sezioni."""
        if type(value) is not bool:
            raise ValueError('manual richiede un booleano')
        current = self.manual(voice, name)
        if value and not current:
            progress = self._parameter_progress if progress is None else progress
            self.set_parameter(voice, name, self.parameters_at(voice, progress, beat=beat)[name])
        elif not value:
            parameters = dict(self._manual_parameters.get(voice, {}))
            parameters.pop(name, None)
            self.set_parameters(voice, parameters)

    def set_parameter(self, voice: str, name: str, value):
        """Modifica un solo override, conservando gli altri e i parametri di sezione."""
        self.set_parameters(voice, {**self._manual_parameters.get(voice, {}), name: value})

    def set_parameters(self, voice: str, parameters: Mapping):
        """Modifiche manuali applicate alle prossime frasi, anche tra sezioni."""
        if voice not in self._destinations:
            raise ValueError('voce non registrata')
        if parameters.get('groove_follow', 0) and self.coordinator.rhythm_source is None:
            raise ValueError('groove_follow richiede rhythm_voice nella configurazione')
        validator = self._generators[voice].validate
        if validator:
            for progress in self._section_progress:
                section = self.director.section_assignments_at(progress)
                if voice in section:
                    spec = section[voice]
                    validator(self.director.manual_role(voice) or spec.role, {**spec.parameters, **parameters})
        self._manual_parameters[voice] = deepcopy(dict(parameters))

    def clear_parameters(self, voice: str):
        """Ripristina i parametri delle sezioni per la voce indicata."""
        self._manual_parameters.pop(voice, None)

    def send(self, start: float, phrases: Mapping[str, Phrase]):
        """Invia un piano tramite le destinazioni registrate dal chiamante."""
        for name in phrases:
            if name not in self._destinations:
                raise ValueError(f'destinazione non registrata per {name}')
        for name, phrase in phrases.items():
            self._destinations[name](start, phrase)


def main(argv=None):
    """Avvia viaggio, composizione multivoce e dispositivi in un solo processo."""
    import argparse
    import math
    import time
    from desnivel.adapters.voice_device import VoiceDeviceBridge
    from desnivel.cli.ensemble_runtime import EnsembleRuntime
    from desnivel.cli.voice_device import VoiceDeviceServer
    from desnivel.sinks.session_status import SessionStatusStore
    from desnivel.cli.session_view import TerminalSessionView
    from desnivel.cli.session_controls import TerminalControls, apply_control
    from desnivel.cli.connect_voices import connect_all
    from desnivel.trip.loader import load_track

    parser = argparse.ArgumentParser(description=main.__doc__)
    from desnivel.cli.track_source import add_track_arguments
    add_track_arguments(parser)
    parser.add_argument('--infer-fit-pauses', action='store_true',
                        help='Se il FIT non contiene eventi timer, stima le pause dai campioni GPS.')
    parser.add_argument('--config', type=Path, required=True)
    direction_options = parser.add_mutually_exclusive_group()
    direction_options.add_argument('--direction', type=Path,
                                   help='Direzione del viaggio; prevale sul campo direction della configurazione.')
    direction_options.add_argument('--manual-sections', action='store_true',
                                   help='Usa le sezioni manuali della configurazione, senza direzione GPX.')
    parser.add_argument('--speed', type=float, default=None, help='Velocità del replay lineare (default: 1).')
    parser.add_argument('--timing', choices=('linear', 'allocated'), default='linear',
                        help='Tempo lineare del viaggio oppure timeline musicale in beat.')
    parser.add_argument('--port', type=int, default=9006)
    parser.add_argument('--connect-port', type=int, default=9101,
                        help='Porta Receive di una Voice per il comando C: Collega tutte (default: 9101).')
    parser.add_argument('--status-file', type=Path, default=Path('/tmp/desnivel-session/state.json'))
    parser.add_argument('--view-port', type=int,
                        help='Attiva la mappa del viaggio su http://127.0.0.1:PORTA (es. 8765).')
    parser.add_argument('--voice-presets', type=Path,
                        help='Libreria dei preset utente (default: <config>.voice-presets.json).')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--weather-context', type=Path, help='File meteo esplicito; altrimenti riusa la cache o acquisisce automaticamente i dati.')
    parser.add_argument('--without-weather', action='store_true', help='Esclude soltanto il contributo musicale del meteo per il confronto A/B.')
    parser.add_argument('--surface-context', type=Path, help='Fondo stradale acquisito: esposizione del contesto, senza mappatura musicale.')
    args = parser.parse_args(argv)
    server = None
    viewer = None
    try:
        if args.view_port is not None and not 1024 <= args.view_port <= 65535:
            raise ValueError('la porta della vista deve essere tra 1024 e 65535')
        if not 1024 <= args.connect_port <= 65535:
            raise ValueError('la porta per Collega tutte deve essere tra 1024 e 65535')
        config = json.loads(args.config.read_text())
        direction = args.direction
        if not args.manual_sections and direction is None and 'direction' in config:
            if not isinstance(config['direction'], str) or not config['direction']:
                raise ValueError('direction deve indicare un file di direzione')
            direction = args.config.parent/config['direction']
        if args.timing == 'allocated' and (direction is None or args.speed is not None):
            raise ValueError('--timing allocated richiede una direzione GPX (direction o --direction) e non usa --speed')
        speed = args.speed if args.speed is not None else 1.
        if not math.isfinite(speed) or speed <= 0 or not 1024 <= args.port <= 65535:
            raise ValueError('velocità positiva e porta tra 1024 e 65535 richieste')
        track = load_track(args.gpx, timing_reference=args.timing_reference,
                           infer_missing_fit_timer=args.infer_fit_pauses)
        if direction is not None:
            from desnivel.cli.trip_direction import prepare_trip_config
            config = prepare_trip_config(track, config, direction)
        from desnivel.cli.weather_context import prepare_weather_context
        weather_source = prepare_weather_context(track, args.weather_context, download=not args.dry_run)
        if args.dry_run:
            bridge = VoiceDeviceBridge({}, lambda *args: None)
        else:
            server = VoiceDeviceServer({}, args.port)
            bridge = server.bridge
        from desnivel.trip.context import ContextSource
        from desnivel.music.environment import weather_intent
        context_sources = []
        surface_source = ContextSource.load(args.surface_context, track) if args.surface_context is not None else None
        for name, source, interpret, enabled in (
                ('weather', weather_source, weather_intent, not args.without_weather),
                ('surface', surface_source, None, False)):
            if source is not None:
                if source.data['source'] != name:
                    raise ValueError(f'file di contesto {name} richiesto')
                if name == 'weather' and (source.data['axis'] != 'time' or source.data['units'] != {
                        'wind_speed_kmh': 'km/h', 'precipitation_mm': 'mm', 'precipitation_change_mm': 'mm'}):
                    raise ValueError('canali e unità del contesto meteo non validi')
                context_sources.append((source, interpret, enabled))
        runtime = EnsembleRuntime(track, config, bridge, speed, timing=args.timing, context_sources=context_sources)
        from desnivel.sinks.voice_presets import VoicePresetLibrary
        from desnivel.cli.voice_presets import connect_preset_library
        library = VoicePresetLibrary(args.voice_presets or args.config.with_suffix('.voice-presets.json'))
        connect_preset_library(library, bridge.voices)
        recording = track.metadata.get('source_recording', {})
        if recording.get('format') == 'fit' and recording.get('timer_intervals') is None:
            print('FIT senza eventi timer: pause stimate dai campioni GPS (--infer-fit-pauses).', flush=True)
        if runtime.trip_music:
            music = runtime.trip_music
            print(f"Direzione GPX: {music['palette']} · pendenza assoluta media "
                  f"{music['profile']['mean_absolute_slope_ratio']:.2%} · motivo {music['motif_degrees']}", flush=True)
        if runtime.timeline:
            plan = runtime.timeline.timeline
            basis = f' ({plan.beats_per_km:g} beat/km)' if plan.beats_per_km is not None else ''
            print(f'Timeline allocated: {plan.total_beats:g} beat, {plan.total_windows} finestre{basis}.', flush=True)
            for adjustment in plan.to_dict()['adjustments']:
                print(f"Avviso timeline: {adjustment['code']}: {adjustment['from_beats']:g} → {adjustment['to_beats']:g} beat", flush=True)
        # Verifica la generazione in ogni sezione prima di avviare la sessione.
        for i, section in enumerate(config['sections']):
            phrases = runtime.session.plan(section['from_progress'], i*runtime.window, runtime.window)
            origin = section.get('trip')
            location = (f" #{i+1} [km {origin['start_distance_m']/1000:.2f}–{origin['end_distance_m']/1000:.2f}]"
                        if origin else '')
            harmony = f" · root {section['root']} · {section['scale']}"
            print(f"{section['name']}{location}{harmony}: " + ', '.join(f'{name} ({len(p.notes)} note)' for name, p in phrases.items()), flush=True)
        runtime.reset()
        if not args.dry_run:
            store = SessionStatusStore(args.status_file)
            store.write(runtime.snapshot())
            if args.view_port is not None:
                from desnivel.viewer.server import JourneyViewServer
                viewer = JourneyViewServer(track, args.status_file, args.view_port)
    except (ValueError, KeyError, TypeError, OSError) as error:
        if viewer:
            viewer.close()
        if server:
            server.close()
        parser.error(str(error))
    if args.dry_run:
        print('Configurazione e generazione delle sezioni verificate; nessun messaggio inviato.')
        return 0
    from desnivel.cli.snake_setup import SnakeSetup
    snake = SnakeSetup(args.config.parent/'snake.json', runtime.voice_descriptions, args.port)
    runtime.external_source_provider = snake.forecasts
    from desnivel.adapters.live_recording import LiveRecording, RECORDING_ACTIONS
    recording = LiveRecording(server.bridge, runtime.transport_voice,
                              lambda: apply_control(runtime, 'restart'), lambda: runtime.epoch)
    def on_message(bridge, message):
        runtime.on_message(bridge, message)
        recording.on_message(message)
    server.on_message = on_message
    server.server.timeout = .1
    last_write = 0.
    view = TerminalSessionView()
    command_error = None
    setup_paused = False
    def report_device_error(message):
        nonlocal command_error
        command_error = message
    server.on_error = report_device_error
    print(f'Python pronto su 127.0.0.1:{args.port}. Chiudi il ricevitore diagnostico prima di avviare questa sessione.', flush=True)
    print(f'Stato globale: {args.status_file}', flush=True)
    with TerminalControls() as keyboard:
        try:
            if viewer:
                viewer.start()
                print(f'Mappa del viaggio: {viewer.url}', flush=True)
            while True:
                server.server.handle_request()
                actions = list(keyboard.poll())
                if viewer:
                    actions.extend(viewer.take_commands())
                for action in actions:
                    try:
                        if (snake.waiting or setup_paused) and (action in ('resume', 'record_start')
                                              or action == 'toggle' and (runtime.paused or not runtime.playing)):
                            raise ValueError('completa la preparazione Snake oppure premi Esc prima di riprendere')
                        if action == 'snake_setup':
                            was_waiting = snake.waiting
                            snake.begin(playing=runtime.playing, recording_busy=recording.status in (
                                'preparing', 'rewinding', 'starting', 'stopping', 'recording'))
                            if snake.waiting and not was_waiting:
                                runtime.control('pause')
                                setup_paused = True
                        elif action == 'setup_check':
                            snake.confirm()
                        elif action == 'setup_cancel':
                            snake.cancel()
                        elif action == 'connect':
                            connect_all(args.connect_port)
                        elif action in RECORDING_ACTIONS:
                            recording.control(action)
                        else:
                            apply_control(runtime, action)
                        command_error = None
                    except (ValueError, OSError) as error:
                        command_error = str(error)
                try:
                    if snake.waiting or setup_paused:
                        if runtime.playing:
                            server.bridge.control_transport(runtime.transport_voice, 'pause')
                            runtime.control('pause')
                        elif not snake.waiting:
                            runtime.control('resume')
                            setup_paused = False
                            runtime.tick()
                    else:
                        runtime.tick()
                except (ValueError, KeyError, TypeError, OSError) as error:
                    runtime.fail(error)
                state = runtime.snapshot()
                recording.tick(finished=runtime.state == 'finished')
                state['recording'] = recording.snapshot()
                state['components'] = snake.tick(state)
                state['setup'] = snake.snapshot()
                state['control_error'] = command_error
                view.update(state)
                if time.monotonic()-last_write >= .25:
                    store.write(state)
                    last_write = time.monotonic()
        except KeyboardInterrupt:
            runtime.reset()
            runtime.playing = False
            runtime.state = 'closed'
            store.write(runtime.snapshot())
        finally:
            snake.close()
            if recording.status in ('recording', 'preparing', 'starting', 'rewinding'):
                try:
                    recording.control('record_stop')
                except (ValueError, OSError) as error:
                    print(f'Registrazione: {error}', flush=True)
            if viewer:
                viewer.close()
            server.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
