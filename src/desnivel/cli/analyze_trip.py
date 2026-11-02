"""Analizza le zone del percorso senza generare o inviare musica."""
import argparse
import json
from pathlib import Path

import numpy as np

from desnivel.trip.analysis import analyze_track
from desnivel.trip.loader import load_track, read_source
from desnivel.cli.track_source import add_track_arguments
from desnivel.trip.quality import inspect_source
from desnivel.trip.sections import group_zones, measure_section_bridges
from desnivel.reports.trip import render_trip_report
from desnivel.music.timeline import allocate_timeline, TimelineManager


def _linear_spans(track, sections, total_beats):
    """Proietta i tempi del Track sullo stesso budget dell'anteprima musicale."""
    if track.duration_s <= 0:
        raise ValueError('durata del percorso positiva richiesta per il confronto lineare')
    boundaries = [sections[0]['start_distance_m']] + [s['end_distance_m'] for s in sections]
    times = np.interp(np.asarray(boundaries)+track.samples['cum_dist_m'][0],
                      track.samples['cum_dist_m'], track.t)
    # Include la sosta iniziale; le soste sugli altri confini restano nella
    # sezione uscente (interpola usando l'ultimo tempo a pari distanza).
    times[0], times[-1] = track.t[0], track.t[-1]
    beats = ((times-track.t[0])/track.duration_s*total_beats).tolist()
    return [{'source_index': index, 'start_beat': start, 'end_beat': end,
             'duration_beats': end-start} for index, (start, end) in enumerate(zip(beats, beats[1:]))]


def analyze_trip(gpx, config, *, grouping=None, pause_context=None, timeline_session=None, timing_reference=None):
    """Prepara gli stessi dati per report singoli e raccolte di tappe."""
    if (pause_context or timeline_session) and not grouping:
        raise ValueError('contesto locale e timeline richiedono il raggruppamento')
    track = load_track(gpx, timing_reference=timing_reference)
    result = analyze_track(track, json.loads(config.read_text()))
    result['source_quality'] = inspect_source(read_source(gpx)[0],
                                            max_speed_kmh=track.metadata['source_filter']['max_speed_kmh'])
    result['source_filter'] = track.metadata['source_filter']
    if grouping:
        result['grouping'] = group_zones(result, json.loads(grouping.read_text()))
    if pause_context:
        families = result['grouping']['config']['families']
        if any(name not in families for pair in pause_context for name in pair):
            raise ValueError('--pause-context richiede famiglie presenti nel raggruppamento')
        result['section_context'] = [measure_section_bridges(
            result['grouping']['sections'], flank_kind=flank, middle_kind=middle)
            for flank, middle in pause_context]
    if timeline_session:
        session = json.loads(timeline_session.read_text(encoding='utf-8'))
        settings = session['timeline']
        if not isinstance(settings, dict) or set(settings) not in ({'target_beats', 'min_windows', 'distance_exponent'},
                                                                      {'beats_per_km', 'min_windows', 'distance_exponent'}):
            raise ValueError('timeline richiede beats_per_km oppure target_beats, con min_windows e distance_exponent')
        sections = result['grouping']['sections']
        timeline = allocate_timeline([s['end_distance_m']-s['start_distance_m'] for s in sections],
                                     window_beats=session['window_beats'], **settings)
        result['timeline'] = {**timeline.to_dict(), 'position': TimelineManager(timeline).snapshot(),
                              'linear_reference': _linear_spans(track, sections, timeline.total_beats)}
        from desnivel.cli.window_context import WindowContext
        context = WindowContext(track, result)
        result['timeline']['window_contexts'] = [context.allocated(timeline, sections, i)
                                                  for i in range(timeline.total_windows)]
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    add_track_arguments(parser)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--grouping', type=Path, help='Famiglie JSON per raggruppare le zone in macrosezioni.')
    parser.add_argument('--pause-context', nargs=2, action='append', metavar=('FLANK', 'MIDDLE'),
                        help='Misura MIDDLE tra due FLANK, per esempio ascent level; ripetibile, richiede --grouping.')
    parser.add_argument('--timeline-session', type=Path,
                        help='Sessione JSON da cui leggere window_beats e timeline per l’anteprima musicale.')
    parser.add_argument('--output', type=Path, help='Salva zone, misure e configurazione in JSON.')
    parser.add_argument('--html', type=Path, help='Salva il report visuale HTML autonomo.')
    args = parser.parse_args(argv)
    if args.timeline_session and not args.grouping:
        parser.error('--timeline-session richiede --grouping')
    if args.pause_context and not args.grouping:
        parser.error('--pause-context richiede --grouping')
    if args.output and args.html and args.output.resolve() == args.html.resolve():
        parser.error('JSON e HTML richiedono percorsi distinti')
    try:
        result = analyze_trip(args.gpx, args.config, grouping=args.grouping,
                              pause_context=args.pause_context, timeline_session=args.timeline_session,
                              timing_reference=args.timing_reference)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2)+'\n', encoding='utf-8')
        if args.html:
            args.html.parent.mkdir(parents=True, exist_ok=True)
            args.html.write_text(render_trip_report(result), encoding='utf-8')
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.error(str(error))
    print(f"{result['stage']} | {result['total_distance_m']/1000:.2f} km | {len(result['zones'])} zone")
    print('Da km   A km    Zona                 Pendenza media   Dislivello netto   Concordanza')
    for zone in result['zones']:
        print(f"{zone['start_distance_m']/1000:6.2f}  {zone['end_distance_m']/1000:6.2f}  "
              f"{zone['kind']:20} {zone['mean_slope_ratio']:+8.1%}         {zone['elevation_delta_m']:+7.0f} m"
              f"          {zone['matching_distance_ratio']:5.0%}")
    print('Concordanza: quota di distanza con classificazione locale uguale alla zona confermata.')
    if 'grouping' in result:
        sections = result['grouping']['sections']
        print(f'\nMacrosezioni: {len(sections)} (zone originali conservate)')
        print('Da km   A km    Famiglia             Zone incluse')
        for section in sections:
            print(f"{section['start_distance_m']/1000:6.2f}  {section['end_distance_m']/1000:6.2f}  "
                  f"{section['kind']:20} " + ', '.join(str(i+1) for i in section['zone_indices']))
    if args.output:
        print(f'Analisi completa: {args.output}')
    if 'timeline' in result:
        t = result['timeline']
        print(f"Timeline: {t['requested_beats']:g} beat richiesti; {t['total_beats']:g} effettivi; {t['total_windows']} finestre")
        for adjustment in t['adjustments']:
            reason = 'minimi garantiti' if adjustment['code'] == 'minimum_extension' else 'quantizzazione alle finestre'
            print(f"Avviso timeline: {reason}: {adjustment['from_beats']:g} → {adjustment['to_beats']:g} beat")
    if args.html:
        print(f'Report visuale: {args.html.resolve()}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
