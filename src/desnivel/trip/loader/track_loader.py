"""Caricamento FIT e GPX nella stessa pipeline di analisi del viaggio."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from ..config import DEFAULT_CONFIG, Config
from ..track import Track, TrackSegment
from ._derive import derive_channels
from ._filter import filter_position_spikes
from ._parse import stage_id_from_path
from ._source import read_source
from ._resample import resample_to_uniform_grid
from ._travel import select_travel, restrict_to_timer


def load_track(
    gpx_path: str | Path,
    config: Config = DEFAULT_CONFIG,
    stage_id: str | None = None,
    *,
    timing_reference: str | Path | None = None,
    infer_missing_fit_timer: bool = False,
) -> Track:
    """Carica FIT o GPX, escludendo le pause prima di derivare i canali.

    Pipeline interna (tutta pura, testabile a pezzi):

    1. ``read_source`` legge coordinate, orari e metadati del formato.
       I campioni fuori dagli intervalli timer, se presenti, sono esclusi.
    2. ``filter_position_spikes`` esclude brevi deviazioni verificabili.
    3. ``select_travel`` separa i tratti osservati, escludendo interruzioni e soste.
    4. ``derive_channels`` e ``resample_to_uniform_grid`` lavorano separatamente
       su ciascun tratto conservato, a ``config.timing.internal_rate_hz``.

    Args:
        gpx_path: percorso al file ``.fit`` o ``.gpx``.
        config: configurazione (legge ``timing`` e ``gpx``).
        stage_id: identificatore tappa; se ``None`` viene dedotto dal nome file.
        timing_reference: FIT corrispondente per usare i suoi eventi timer
            durante la lettura di un GPX; richiede copertura temporale completa.
        infer_missing_fit_timer: consente la stima GPS delle pause quando
            il FIT principale non contiene eventi timer; il riferimento resta rigoroso.

    Returns:
        `Track` con asse temporale uniforme e samples derivati.
    """
    gpx_path = Path(gpx_path)
    raw, source = read_source(gpx_path, infer_missing_fit_timer=infer_missing_fit_timer)
    if timing_reference is not None:
        if source['format'] != 'gpx' or Path(timing_reference).suffix.lower() != '.fit':
            raise ValueError('il riferimento timer richiede una sorgente GPX e un riferimento FIT')
        reference_raw, recording = read_source(timing_reference)
        if (not np.isfinite(raw['t_unix']).all()
                or raw['t_unix'].min() < reference_raw['t_unix'].min()
                or raw['t_unix'].max() > reference_raw['t_unix'].max()):
            raise ValueError('il FIT di riferimento non copre tutti gli orari del GPX')
        source['timing_reference_path'] = str(timing_reference)
    else:
        recording = source
    timer = recording.get('timer_intervals')
    if timer is not None:
        raw = restrict_to_timer(raw, timer)
    raw, motion_valid, source_filter = filter_position_spikes(raw, config.gpx)
    spans, travel = select_travel(raw, config.gpx, source_filter['reconnections'], timer_intervals=timer)
    if timer is not None:
        travel.update(timer_duration_s=recording['timer_duration_s'],
                      unobserved_timer_duration_s=recording['timer_duration_s']-travel['observed_duration_s'])
        if 'declared_timer_duration_s' in recording:
            travel['declared_timer_duration_s'] = recording['declared_timer_duration_s']
    time_parts, sample_parts, segments, unavailable = [], {}, [], []
    cursor, distance_offset, sample_offset = 0., 0., 0
    for start, stop in spans:
        block = {name: values[start:stop] for name, values in raw.items()}
        derived = derive_channels(block, config.gpx)
        for name in ('recorded_distance_m', 'recorded_speed_kmh', 'gps_accuracy_m'):
            if name in block:
                derived[name] = block[name]
        valid = motion_valid[start:stop].copy()
        valid[0] = True  # Nessun intervallo entrante dall'altra parte dell'interruzione.
        for name in ('speed_kmh', 'slope', 'effort'):
            derived[name][~valid] = np.nan
        elapsed = derived.pop('elapsed_s')
        t, samples = resample_to_uniform_grid(
            elapsed_s=elapsed, channels=derived, rate_hz=config.timing.internal_rate_hz,
            interval_channels=('speed_kmh', 'slope', 'effort'))
        samples['cum_dist_m'] += distance_offset
        time_parts.append(t+cursor)
        for name, values in samples.items():
            sample_parts.setdefault(name, []).append(values)
        unavailable.extend([[float(cursor+elapsed[i-1]), float(cursor+elapsed[i])]
                            for i in np.flatnonzero(~valid)])
        segments.append(TrackSegment(sample_offset, sample_offset+len(t), float(block['t_unix'][0]),
                                     float(block['t_unix'][-1]), int(block['source_index'][0]),
                                     int(block['source_index'][-1])))
        sample_offset += len(t)
        cursor += float(t[-1])
        distance_offset = float(samples['cum_dist_m'][-1])
    t = np.concatenate(time_parts)
    samples = {name: np.concatenate(values) for name, values in sample_parts.items()}
    if not np.isfinite(samples['ele']).any():
        for name in ('ele', 'slope', 'effort'):
            samples.pop(name)

    return Track(
        stage_id=stage_id or stage_id_from_path(gpx_path),
        t=t,
        samples=samples,
        metadata={"source_path": str(gpx_path), 'source_format': source['format'],
                  'source_recording': recording, 'source_filter': source_filter,
                  'timing_reference_path': source.get('timing_reference_path'),
                  'travel_selection': travel, 'unavailable_motion_intervals': unavailable},
        segments=tuple(segments),
    )
