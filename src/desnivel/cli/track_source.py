"""Argomenti comuni dei comandi che leggono una tappa."""
from pathlib import Path


def add_track_arguments(parser, *, required=True):
    parser.add_argument('--track', '--gpx', dest='gpx', required=required, type=Path,
                        help='File FIT o GPX della tappa (--gpx resta un alias).')
    parser.add_argument('--timing-reference', type=Path,
                        help='FIT corrispondente da cui leggere le pause quando --track è un GPX.')
