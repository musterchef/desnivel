"""Mostra la forma neutra ricavata da una tappa, senza generare musica."""
import argparse
import json
from pathlib import Path

from desnivel.cli.file_dialogs import choose_track
from desnivel.cli.launch_stage import resolve_track
from desnivel.cli.track_source import read_stage_choice
from desnivel.cli.trip_direction import load_route_form
from desnivel.settings import DEFAULT_SETTINGS_PATH, load_settings
from desnivel.trip.loader import load_track


TREND_LABELS = {'rising': '↑ salita', 'falling': '↓ discesa', 'level': '→ piano'}
SOURCE_LABELS = {'ascent': 'salita', 'descent': 'discesa', 'level': 'piano'}
EVENT_LABELS = {
    'departure': 'partenza',
    'profile_change': 'cambio di profilo',
    'summit': 'vetta',
    'valley': 'valle',
    'observation_gap': 'interruzione dei dati',
    'arrival': 'arrivo',
}


def _duration(seconds):
    total = round(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{hours:d}:{minutes:02d}:{seconds:02d}'


def _render_episodes(form):
    lines = ['CONTINUITÀ STRUTTURALI',
             'N   Da km   A km    Profilo       Tempo attivo   Dislivello   Variazioni locali']
    for episode in form['episodes']:
        lines.append(
            f"{episode['index']+1:>2}  {episode['start_distance_m']/1000:6.2f}  "
            f"{episode['end_distance_m']/1000:6.2f}  {TREND_LABELS[episode['trend']]:<12} "
            f"{_duration(episode['active_duration_s']):>12}  "
            f"{episode['elevation_delta_m']:+8.0f} m  "
            f"{len(episode['local_variations']):>4}"
        )
    reversals = [(episode['index'], reversal) for episode in form['episodes']
                 for reversal in episode['local_variations']]
    if reversals:
        lines.extend(('', 'VARIAZIONI LOCALI RIUNITE'))
        for episode_index, reversal in reversals:
            lines.append(
                f"• continuità {episode_index+1} · "
                f"km {reversal['start_distance_m']/1000:.2f}–{reversal['end_distance_m']/1000:.2f} · "
                f"{TREND_LABELS[reversal['trend']]} · "
                f"{reversal['distance_m']:.0f} m · {reversal['elevation_delta_m']:+.1f} m"
            )
    return lines


def render_route_form(form, *, detailed=False):
    """Rende leggibile nel terminale una forma già calcolata."""
    lines = [f"FORMA DELLA TAPPA · {form['stage']}", '']
    if 'episodes' in form:
        lines.extend(_render_episodes(form))
        if not detailed:
            lines.extend(('', f"{len(form['spans'])} campate osservate · "
                          f"{len(form['episodes'])} continuità strutturali",
                          'Usa --detailed per mostrare campate ed eventi osservati.'))
            return '\n'.join(lines)
        lines.extend(('', 'CAMPATE OSSERVATE'))
    lines.append('N   Da km   A km    Famiglia   Profilo       Tempo attivo   Dislivello   Pendenza')
    for index, span in enumerate(form['spans'], 1):
        lines.append(
            f"{index:>2}  {span['start_distance_m']/1000:6.2f}  {span['end_distance_m']/1000:6.2f}  "
            f"{SOURCE_LABELS.get(span['source_kind'], span['source_kind']):<10} "
            f"{TREND_LABELS[span['trend']]:<12} {_duration(span['active_duration_s']):>12}  "
            f"{span['elevation_delta_m']:+8.0f} m  {span['mean_slope_ratio']:+8.1%}"
        )
    lines.extend(('', 'EVENTI'))
    for event in form['events']:
        transition = ''
        if 'from_trend' in event:
            before = SOURCE_LABELS.get(event.get('from_source_kind'), event.get('from_source_kind'))
            after = SOURCE_LABELS.get(event.get('to_source_kind'), event.get('to_source_kind'))
            before = f'{before}/' if before is not None else ''
            after = f'{after}/' if after is not None else ''
            transition = (f" · {before}{TREND_LABELS[event['from_trend']]} → "
                          f"{after}{TREND_LABELS[event['to_trend']]}")
        lines.append(f"• km {event['at_distance_m']/1000:.2f} · "
                     f"{EVENT_LABELS[event['type']]}{transition}")
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--track', '--gpx', dest='track', type=Path,
                        help='File FIT o GPX della tappa (--gpx resta un alias).')
    source.add_argument('--tappa', help='01–12 oppure O per aprire un file.')
    parser.add_argument('--timing-reference', type=Path,
                        help='FIT corrispondente da cui leggere le pause quando --track è un GPX.')
    parser.add_argument('--direction', type=Path, default=Path('presets/direzione-viaggio.json'),
                        help='Criteri di analisi e raggruppamento usati dalla sessione.')
    parser.add_argument('--settings', type=Path, default=DEFAULT_SETTINGS_PATH,
                        help='Impostazioni TOML applicative.')
    parser.add_argument('--output', type=Path, help='Salva la forma completa in JSON.')
    parser.add_argument('--detailed', action='store_true',
                        help='Mostra anche campate grezze ed eventi osservati.')
    args = parser.parse_args(argv)
    try:
        stage = args.tappa
        if args.track is None:
            if stage is None:
                stage = read_stage_choice('Numero tappa (01–12; O apre un file FIT/GPX): ')
            path = choose_track() if stage.casefold() == 'o' else resolve_track(stage, Path.cwd())
            if path is None:
                print('Lettura annullata.')
                return 130
        else:
            path = args.track
        application_settings = load_settings(args.settings)
        track = load_track(path, timing_reference=args.timing_reference,
                           config=application_settings.config)
        form = load_route_form(track, args.direction, args.settings)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(form, ensure_ascii=False, allow_nan=False, indent=2)+'\n',
                                   encoding='utf-8')
    except (EOFError, KeyboardInterrupt):
        print('\nLettura annullata.')
        return 130
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.error(str(error))
    print(render_route_form(form, detailed=args.detailed))
    if args.output:
        print(f'\nJSON completo: {args.output.resolve()}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
