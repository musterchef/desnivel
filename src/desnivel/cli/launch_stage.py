"""Selezione interattiva della tappa e avvio della sessione multivoce."""
import argparse
import json
from pathlib import Path
import re

from . import ensemble
from desnivel.cli.file_dialogs import choose_file, choose_track
from desnivel.cli.session_files import new_session_path, saved_sessions
from desnivel.cli.session_config import resolve_journey
from desnivel.cli.track_source import read_stage_choice


VARIANTS = {
    '07bis': Path('output/ricostruzione-tappa07/tappa07_Roma_Sabaudia.fit'),
}


def choose_session(root, *, read=None):
    read = input if read is None else read
    paths = saved_sessions(root)
    print('\nSESSIONI DESNIVEL\n  [0] crea una nuova sessione\n  [A] apri file…')
    for index, path in enumerate(paths, 1):
        print(f'  [{index}] {path.stem} — {path.relative_to(root)}')
    while True:
        choice = read('Sessione [numero, P prova formazione, A apri file, q annulla]: ').strip()
        if choice.lower() == 'q':
            return None
        if choice.lower() == 'a':
            try:
                path = choose_file('Apri una sessione Desnivel', ('.json',))
                if path is not None and path.name.casefold().endswith('.voice-presets.json'):
                    raise ValueError('Scegli la configurazione di una sessione, non la libreria dei preset voce.')
            except ValueError as error:
                print(error)
                continue
            if path is not None:
                return path, False
            continue
        if choice == '0':
            while True:
                name = read('Nome della nuova sessione [q annulla]: ').strip()
                if name.lower() == 'q':
                    return None
                try:
                    return new_session_path(root, name), True
                except ValueError as error:
                    print(error)
        if choice.isdecimal() and 1 <= int(choice) <= len(paths):
            return paths[int(choice)-1], False
        print('Scegli un numero, A per aprire un file oppure q per annullare.')


def resolve_track(stage: str, root: Path) -> Path:
    """Risolve una tappa o variante senza scegliere fra tracce ambigue."""
    if stage in VARIANTS:
        matches = [root / VARIANTS[stage]]
        matches = [path for path in matches if path.is_file()]
    elif re.fullmatch(r'0[1-9]|1[0-2]', stage):
        matches = sorted((root / 'gpx').glob(f'tappa{stage}_*.gpx'))
    else:
        raise ValueError('Usa due cifre da 01 a 12 oppure O per aprire un file.')
    if not matches:
        raise ValueError(f'Traccia della tappa {stage} non trovata.')
    if len(matches) > 1:
        raise ValueError(f'Più tracce per la tappa {stage}: ' + ', '.join(map(str, matches)))
    return matches[0]


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog='Gli altri argomenti sono passati a desnivel.cli.ensemble e possono '
               'sostituire i valori predefiniti di config, timing e view-port.')
    parser.add_argument('--tappa', help='01–12 oppure O per aprire un file; se omessa riusa il viaggio salvato nella sessione.')
    parser.add_argument('--config', type=Path, help='Carica direttamente una configurazione, senza mostrare il menu delle sessioni.')
    from desnivel.settings import DEFAULT_SETTINGS_PATH, load_settings
    parser.add_argument('--settings', type=Path, default=DEFAULT_SETTINGS_PATH,
                        help='Impostazioni TOML applicative.')
    args, session_args = parser.parse_known_args(argv)
    try:
        selection = (args.config, False) if args.config is not None else choose_session(Path.cwd())
        if selection is None:
            print('Avvio annullato.')
            return 130
        config, create = selection
        stage = None
        track = None
        manual_sections = False
        if not create and config.is_file():
            saved = json.loads(config.read_text())
            manual_sections = (saved.get('selection_mode') == 'manual'
                              and not ('direction' in saved and 'timeline' in saved))
            if args.tappa is None and 'journey' in saved:
                track, _, _ = resolve_journey(saved, config)
                if not track.is_file():
                    raise ValueError(f'Viaggio della sessione non trovato: {track}. Usa --tappa O per aprire un altro file.')
        if track is None:
            stage = (args.tappa if args.tappa is not None else
                     read_stage_choice('Numero tappa (01–12; O apre un file FIT/GPX): ')).strip()
            track = choose_track() if stage.casefold() == 'o' else resolve_track(stage, Path.cwd())
        if track is None:
            print('Avvio annullato.')
            return 130
    except (EOFError, KeyboardInterrupt):
        print('\nAvvio annullato.')
        return 130
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(f'Sessione {config.stem}: {config}', flush=True)
    print(f"{'Viaggio salvato nella sessione' if stage is None else 'Tappa '+stage}: {track}", flush=True)
    if stage is not None and stage.casefold() == 'o' and track.suffix.lower() == '.fit':
        print('FIT: se mancano gli eventi timer, le pause saranno stimate dai campioni GPS.',
              flush=True)
        if not any(flag in session_args for flag in ('--infer-fit-pauses', '--no-infer-fit-pauses')):
            session_args.append('--infer-fit-pauses')
    return ensemble.main([
        *(['--track', str(track)] if stage is not None else []),
        '--config', str(config),
        *(['--setup'] if create else []),
        *(['--manual-sections'] if manual_sections else []),
        '--timing', 'linear' if manual_sections else 'allocated',
        '--view-port', str(load_settings(args.settings).transport.session.viewer_port),
        '--settings', str(args.settings),
        *session_args,
    ])


if __name__ == '__main__':
    raise SystemExit(main())
