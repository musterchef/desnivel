"""Acquisisce e salva meteo storico o fondo stradale senza avviare la musica."""
import argparse
from pathlib import Path
from urllib.error import URLError

from desnivel.cli.track_source import add_track_arguments
from desnivel.trip.loader import load_track
from desnivel.trip.surface import SurfaceFetcher
from desnivel.trip.weather import WeatherFetcher


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', choices=('weather', 'surface'))
    add_track_arguments(parser)
    parser.add_argument('--infer-fit-pauses', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--distance-step-m', type=float,
                        help='Passo spaziale massimo di campionamento (meteo: 5000 m; fondo: 100 m).')
    args = parser.parse_args(argv)
    try:
        track = load_track(args.gpx, timing_reference=args.timing_reference,
                           infer_missing_fit_timer=args.infer_fit_pauses)
        fetcher = WeatherFetcher() if args.source == 'weather' else SurfaceFetcher()
        options = {} if args.distance_step_m is None else {'distance_step_m': args.distance_step_m}
        source = fetcher.fetch(track, **options)
        source.save(args.output)
    except (ValueError, OSError, URLError) as exc:
        parser.exit(1, f'Errore acquisizione contesto: {exc}\n')
    print(f"{args.source}: {len(source.data['records'])} intervalli salvati in {args.output}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
