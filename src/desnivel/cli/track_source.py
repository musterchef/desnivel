"""Argomenti comuni dei comandi che leggono una tappa."""
from pathlib import Path
import sys


def read_stage_choice(prompt, *, stream=None):
    """Legge una tappa; su terminale il tasto O apre subito un file."""
    stream = sys.stdin if stream is None else stream
    if not stream.isatty():
        return input(prompt).strip()
    import termios
    import tty
    print(prompt, end='', flush=True)
    saved = termios.tcgetattr(stream.fileno())
    try:
        tty.setcbreak(stream.fileno())
        first = stream.read(1)
    finally:
        termios.tcsetattr(stream.fileno(), termios.TCSADRAIN, saved)
    if first.casefold() == 'o':
        print()
        return first
    if first in ('', '\n', '\r'):
        return ''
    return (first+stream.readline()).strip()


def add_track_arguments(parser, *, required=True):
    parser.add_argument('--track', '--gpx', dest='gpx', required=required, type=Path,
                        help='File FIT o GPX della tappa (--gpx resta un alias).')
    parser.add_argument('--timing-reference', type=Path,
                        help='FIT corrispondente da cui leggere le pause quando --track è un GPX.')
