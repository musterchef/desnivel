"""Confronta il riconoscimento delle pause GPX con i timer dei FIT corrispondenti."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import numpy as np

from desnivel.reports.pause_validation import render_pause_validation
from desnivel.settings import DEFAULT_CONFIG
from desnivel.trip.loader import read_source
from desnivel.trip.loader._filter import filter_position_spikes
from desnivel.trip.loader._parse import stage_id_from_path
from desnivel.trip.loader._travel import select_travel
from desnivel.trip.pause_validation import compare_pauses


def indexed_sources(directory, suffix):
    sources = {}
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.suffix.lower() != suffix:
            continue
        stage = stage_id_from_path(path)
        if stage in sources:
            raise ValueError(f'più sorgenti {suffix} per {stage}')
        sources[stage] = path
    return sources


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_pairs(gpx_dir, fit_dir, *, config=DEFAULT_CONFIG):
    gpx, fit = indexed_sources(gpx_dir, '.gpx'), indexed_sources(fit_dir, '.fit')
    stages = []
    for stage in sorted(gpx.keys() & fit.keys()):
        raw, _ = read_source(gpx[stage])
        raw, valid, filtered = filter_position_spikes(raw, config.gpx)
        reference, recording = read_source(fit[stage])
        shared = np.intersect1d(raw['t_unix'], reference['t_unix'])
        if len(shared) < 2:
            raise ValueError(f'{stage}: orari GPX/FIT insufficienti per il confronto')
        spans, selection = select_travel(raw, config.gpx, filtered['reconnections'])
        kept = np.zeros(len(raw['t_unix'])-1, dtype=bool)
        for a, b in spans:
            kept[a:b-1] = True
        result = compare_pauses(raw, kept, recording['timer_intervals'], valid, config.gpx.recording_gap_s)
        stages.append({'stage': stage, 'gpx': str(gpx[stage]), 'fit': str(fit[stage]),
                       'gpx_sha256': fingerprint(gpx[stage]), 'fit_sha256': fingerprint(fit[stage]),
                       'shared_timestamps': len(shared), 'pause_inference': selection['pause_inference'], **result})
    if not stages:
        raise ValueError('nessuna coppia GPX/FIT disponibile')
    return {'version': 1, 'config': asdict(config.gpx), 'stages': stages,
            'without_fit': sorted(gpx.keys()-fit.keys()),
            'summary': {key: sum(s['metrics'][key] for s in stages) for key in stages[0]['metrics']}}


def attach_baseline(result, baseline):
    """Accetta confronti precedenti sugli stessi file e sulla stessa durata valutata."""
    if baseline.get('version') != 1:
        raise ValueError('confronto precedente versione 1 richiesto')
    previous = {s['stage']: s for s in baseline['stages']}
    if previous.keys() != {s['stage'] for s in result['stages']}:
        raise ValueError('il confronto precedente deve includere le stesse tappe')
    for stage in result['stages']:
        old = previous[stage['stage']]
        if (any(stage[key] != old[key] for key in ('gpx_sha256', 'fit_sha256'))
                or not np.isclose(stage['metrics']['compared_s'], old['metrics']['compared_s'], rtol=0, atol=1e-7)):
            raise ValueError(f'{stage["stage"]}: file o durata valutata differenti dal confronto precedente')
        stage['baseline_metrics'] = old['metrics']
    result['baseline_config'] = baseline['config']
    result['baseline_summary'] = {key: sum(s['baseline_metrics'][key] for s in result['stages'])
                                  for key in result['summary']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gpx-dir', type=Path, default=Path('gpx'))
    parser.add_argument('--fit-dir', type=Path, default=Path('fit'))
    parser.add_argument('--baseline', type=Path, help='Snapshot JSON di un confronto precedente sugli stessi file.')
    parser.add_argument('--output-dir', type=Path, default=Path('output/confronto-pause'))
    args = parser.parse_args(argv)
    try:
        result = validate_pairs(args.gpx_dir, args.fit_dir)
        if args.baseline:
            attach_baseline(result, json.loads(args.baseline.read_text()))
        payload = json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2)+'\n'
        html = render_pause_validation(result)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir/'confronto-pause.json').write_text(payload, encoding='utf-8')
        (args.output_dir/'confronto-pause.html').write_text(html, encoding='utf-8')
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.error(str(error))
    print(f"{len(result['stages'])} coppie: {result['summary']['extra_pause_s']:g} s esclusi con timer attivo; "
          f"{result['summary']['missed_pause_s']:g} s conservati con timer fermo.")
    if result['without_fit']:
        print('Senza riferimento FIT: '+', '.join(result['without_fit']))
    print((args.output_dir/'confronto-pause.html').resolve())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
