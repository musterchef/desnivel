"""Selezione interattiva della tappa e avvio della sessione multivoce."""
import argparse
from pathlib import Path
import re
import subprocess

from . import ensemble


VARIANTS = {
    '07bis': Path('output/ricostruzione-tappa07/tappa07_Roma_Sabaudia.fit'),
}


def choose_track():
    """Apre il selettore macOS; restituisce None se viene annullato."""
    result = subprocess.run([
        'osascript', '-e',
        'try\n'
        'set trackFile to choose file with prompt "Seleziona una traccia FIT o GPX" '
        'of type {"fit", "gpx"}\n'
        'return POSIX path of trackFile\n'
        'on error number -128\n'
        'return ""\n'
        'end try',
    ], capture_output=True, text=True)
    if result.returncode:
        raise ValueError('Impossibile aprire il selettore file: ' + result.stderr.strip())
    selected = result.stdout.strip()
    if not selected:
        return None
    path = Path(selected)
    if path.suffix.lower() not in {'.fit', '.gpx'} or not path.is_file():
        raise ValueError('Seleziona un file FIT o GPX esistente.')
    return path


def resolve_track(stage: str, root: Path) -> Path:
    """Risolve una tappa o variante senza scegliere fra tracce ambigue."""
    if stage in VARIANTS:
        matches = [root / VARIANTS[stage]]
        matches = [path for path in matches if path.is_file()]
    elif re.fullmatch(r'0[1-9]|1[0-2]', stage):
        matches = sorted((root / 'gpx').glob(f'tappa{stage}_*.gpx'))
    else:
        raise ValueError('Usa due cifre da 01 a 12, 07bis oppure 99 per scegliere un file.')
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
    parser.add_argument('--tappa', help='01–12, 07bis oppure 99 per scegliere un file; se omessa viene richiesta.')
    args, session_args = parser.parse_known_args(argv)
    try:
        stage = (args.tappa if args.tappa is not None else
                 input('Numero tappa (01–12, 07bis oppure 99 per un file FIT/GPX): ')).strip()
        track = choose_track() if stage == '99' else resolve_track(stage, Path.cwd())
        if track is None:
            print('Avvio annullato.')
            return 130
    except (EOFError, KeyboardInterrupt):
        print('\nAvvio annullato.')
        return 130
    except ValueError as error:
        parser.error(str(error))
    print(f'Tappa {stage}: {track}', flush=True)
    if stage == '99' and track.suffix.lower() == '.fit':
        print('FIT: se mancano gli eventi timer, le pause saranno stimate dai campioni GPS.',
              flush=True)
        if '--infer-fit-pauses' not in session_args:
            session_args.append('--infer-fit-pauses')
    return ensemble.main([
        '--track', str(track),
        '--config', 'presets/organico.json',
        '--timing', 'allocated',
        '--view-port', '8765',
        *session_args,
    ])


if __name__ == '__main__':
    raise SystemExit(main())
