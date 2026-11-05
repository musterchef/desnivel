"""Avvio da terminale della sessione musicale e delle integrazioni locali."""
from copy import deepcopy
import json
from pathlib import Path


def main(argv=None):
    """Avvia viaggio, composizione multivoce e dispositivi in un solo processo."""
    import argparse
    import math
    import time
    from desnivel.adapters.voice_device import VoiceDeviceBridge
    from desnivel.cli.ensemble_runtime import EnsembleRuntime
    from desnivel.cli.voice_device import VoiceDeviceServer
    from desnivel.sinks.session_status import SessionStatusStore
    from desnivel.trip.loader import load_track

    parser = argparse.ArgumentParser(description=main.__doc__)
    from desnivel.cli.track_source import add_track_arguments
    add_track_arguments(parser, required=False)
    parser.add_argument('--infer-fit-pauses', action=argparse.BooleanOptionalAction, default=None,
                        help='Se il FIT non contiene eventi timer, stima le pause dai campioni GPS.')
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--setup', action='store_true', help='Crea una sessione vuota se il file di configurazione non esiste.')
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
                        help='Attiva il pannello della sessione e la mappa su http://127.0.0.1:PORTA (es. 8765).')
    parser.add_argument('--voice-presets', type=Path,
                        help='Libreria dei preset utente (default: <config>.voice-presets.json).')
    parser.add_argument('--no-terminal', action='store_true', help='Esegue la sessione senza tastiera e pannello del terminale.')
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
        config_origin = args.config
        if args.setup and not config_origin.exists():
            config_origin = Path(__file__).resolve().parents[3]/'presets/sessione.json'
        config = json.loads(config_origin.read_text())
        from desnivel.cli.session_config import resolve_journey, journey_configuration
        args.gpx, args.timing_reference, args.infer_fit_pauses = resolve_journey(
            config, args.config, track=args.gpx, timing_reference=args.timing_reference,
            infer_fit_pauses=args.infer_fit_pauses)
        if 'arrangement' in config and args.port != 9006:
            raise ValueError('il rilevamento dei device della sessione guidata usa la porta Python 9006')
        if 'arrangement' in config and 'direction' in config:
            config['direction'] = str((config_origin.parent/config['direction']).resolve())
        source_config = deepcopy(config)
        source_config['journey'] = journey_configuration(
            args.config, args.gpx, args.timing_reference, args.infer_fit_pauses)
        direction = args.direction
        if not args.manual_sections and direction is None and 'direction' in config:
            if not isinstance(config['direction'], str) or not config['direction']:
                raise ValueError('direction deve indicare un file di direzione')
            direction = config_origin.parent/config['direction']
        if args.timing == 'allocated' and (direction is None or args.speed is not None):
            raise ValueError('--timing allocated richiede una direzione GPX (direction o --direction) e non usa --speed')
        if direction is not None and 'arrangement' in source_config:
            source_config['direction'] = str(direction.resolve())
        speed = args.speed if args.speed is not None else 1.
        if not math.isfinite(speed) or speed <= 0 or not 1024 <= args.port <= 65535:
            raise ValueError('velocità positiva e porta tra 1024 e 65535 richieste')
        track = load_track(args.gpx, timing_reference=args.timing_reference,
                           infer_missing_fit_timer=args.infer_fit_pauses)
        from desnivel.cli.session_config import resolve_configuration
        config = resolve_configuration(track, config, direction)
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
        from desnivel.cli.live_components import LiveComponents
        components = LiveComponents(config, args.config, args.port)
        runtime = EnsembleRuntime(track, config, bridge, speed, timing=args.timing, context_sources=context_sources,
                                  external_voices=components.voices)
        components.attach(runtime)
        bridge.set_bindings(config.get('live_bindings', {}))
        from desnivel.sinks.voice_presets import VoicePresetLibrary
        from desnivel.cli.voice_presets import connect_preset_library
        library = VoicePresetLibrary(args.voice_presets or args.config.with_suffix('.voice-presets.json'))
        connect_preset_library(library, bridge.voices, allow_missing='arrangement' in config)
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
            if args.dry_run:
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
    from itertools import chain
    from desnivel.cli.session_controller import SessionController
    from desnivel.cli.session_frontend import TerminalFrontend
    controller = SessionController(runtime, source_config, args.config, server, library, components,
                                   direction=direction, port=args.port, connect_port=args.connect_port)
    server.server.timeout = .1
    last_write = 0.
    print(f'Python pronto su 127.0.0.1:{args.port}. Stato: {args.status_file}', flush=True)
    with TerminalFrontend(enabled=not args.no_terminal) as terminal:
        try:
            if viewer:
                viewer.start()
                print(f'Controllo della sessione: {viewer.url}session/', flush=True)
                print(f'Mappa del viaggio: {viewer.url}', flush=True)
            if 'arrangement' in source_config:
                controller.execute({'action': 'scan'})
            while True:
                server.server.handle_request()
                commands = chain(terminal.commands(), viewer.take_commands() if viewer else ())
                for command in commands:
                    controller.execute(command)
                    terminal.synchronize(controller.setup)
                state = controller.tick()
                terminal.update(state)
                if time.monotonic()-last_write >= .25:
                    store.write(state)
                    last_write = time.monotonic()
        except KeyboardInterrupt:
            pass
        finally:
            try:
                store.write(controller.close())
            finally:
                if viewer:
                    viewer.close()
                server.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
