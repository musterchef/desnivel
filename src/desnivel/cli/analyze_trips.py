"""Genera i report delle tappe FIT/GPX e una pagina per scegliere quale consultare."""
import argparse
import json
from pathlib import Path

from desnivel.cli.analyze_trip import analyze_trip
from desnivel.reports.trip import render_trip_report, render_trip_index, render_source_review
from desnivel.trip.loader._parse import stage_id_from_path
from desnivel.settings import DEFAULT_SETTINGS_PATH


def stage_sources(directory):
    """Preferisce il FIT quando la stessa tappa è presente nei due formati."""
    stages = {}
    for path in directory.iterdir():
        if path.is_file() and path.suffix.lower() in ('.fit', '.gpx'):
            stages.setdefault(stage_id_from_path(path), []).append(path)
    sources = []
    for stage, paths in sorted(stages.items()):
        preferred = [p for p in paths if p.suffix.lower() == '.fit'] or paths
        if len(preferred) != 1:
            raise ValueError(f'più sorgenti per {stage}: ' + ', '.join(p.name for p in preferred))
        sources.append(preferred[0])
    return sources


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--track-dir', '--gpx-dir', dest='gpx_dir', type=Path, required=True,
                        help='Cartella FIT/GPX; a parità di tappa viene usato il FIT.')
    parser.add_argument('--settings', type=Path, default=DEFAULT_SETTINGS_PATH,
                        help='Impostazioni TOML applicative.')
    parser.add_argument('--grouping', type=Path)
    parser.add_argument('--pause-context', nargs=2, action='append', metavar=('FLANK', 'MIDDLE'))
    parser.add_argument('--timeline-session', type=Path)
    parser.add_argument('--output-dir', type=Path, default=Path('output/tappe'))
    args = parser.parse_args(argv)
    if (args.pause_context or args.timeline_session) and not args.grouping:
        parser.error('--pause-context e --timeline-session richiedono --grouping')
    try:
        sources = stage_sources(args.gpx_dir)
        if not sources:
            raise ValueError(f'nessun file GPX o FIT in {args.gpx_dir}')
        reports = []
        for source in sources:
            try:
                result = analyze_trip(source, args.settings, grouping=args.grouping,
                                      pause_context=args.pause_context, timeline_session=args.timeline_session)
            except (ValueError, KeyError, TypeError, OSError) as error:
                raise ValueError(f'{source.name}: {error}') from error
            reports.append((source, result))
        args.output_dir.mkdir(parents=True, exist_ok=True)
        entries = []
        for source, result in reports:
            filename = f'report-{source.stem}.html'
            (args.output_dir/filename).write_text(render_trip_report(result), encoding='utf-8')
            (args.output_dir/f'report-{source.stem}.json').write_text(
                json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2)+'\n', encoding='utf-8')
            label = source.stem.replace('_', ' ')
            entry = {'stage': result['stage'], 'label': label, 'filename': filename,
                     'distance_m': result['total_distance_m'], 'source_quality': result['source_quality'],
                     'source_filter': result['source_filter']}
            if 'timeline' in result:
                entry['total_beats'] = result['timeline']['total_beats']
            entries.append(entry)
            print(f"{label}: {result['total_distance_m']/1000:.2f} km")
        index = args.output_dir/'index.html'
        index.write_text(render_trip_index(entries), encoding='utf-8')
        (args.output_dir/'segmenti-da-verificare.html').write_text(render_source_review(entries), encoding='utf-8')
        review = {'version': 1, 'display_timezone': 'Europe/Rome', 'stages': [
            {'stage': e['stage'], 'label': e['label'], 'report': e['filename'],
             'review_settings': e['source_quality']['review_settings'],
             'segments': e['source_quality']['review_segments']} for e in entries]}
        (args.output_dir/'segmenti-da-verificare.json').write_text(
            json.dumps(review, ensure_ascii=False, allow_nan=False, indent=2)+'\n', encoding='utf-8')
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.error(str(error))
    print(f'{len(entries)} tappe. Selezione: {index.resolve()}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
