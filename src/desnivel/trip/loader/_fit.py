"""Lettura FIT: campioni GPS, riepiloghi e intervalli espliciti del timer."""
from collections import Counter

import numpy as np
import fitdecode


def timer_intervals(events):
    """Ricava gli intervalli start/stop senza inventare estremi mancanti."""
    intervals, notes, opened, previous = [], [], None, None
    for event in events:
        time, kind = event['time_unix'], event['event_type']
        if not np.isfinite(time) or (previous is not None and time < previous):
            raise ValueError('eventi timer FIT con tempi non crescenti')
        previous = time
        if kind == 'start':
            if opened is not None:
                notes.append({'reason': 'repeated_start', **event})
            else:
                opened = time
        elif kind in ('stop', 'stop_all', 'stop_disable', 'stop_disable_all'):
            if opened is None:
                notes.append({'reason': 'stop_without_start', **event})
            else:
                if time > opened:
                    if intervals and intervals[-1][1] == opened:
                        intervals[-1][1] = time
                    else:
                        intervals.append([opened, time])
                opened = None
        else:
            raise ValueError(f'tipo evento timer FIT non supportato: {kind}')
    if opened is not None:
        raise ValueError('timer FIT ancora aperto: manca l’evento di arresto')
    if not intervals:
        raise ValueError('nessun intervallo start/stop disponibile nel FIT')
    return intervals, notes


def parse_fit(path, *, infer_missing_timer=False):
    """Unisce i messaggi record nello stesso secondo, conservando l'ultimo valore.

    Non trasporta valori da un secondo all'altro. I record senza coordinate
    restano contati nella diagnostica, ma non diventano posizioni fittizie.
    """
    records, events, sessions, counts = {}, [], [], Counter()
    conflicts, previous_time, order_notes = Counter(), None, []
    try:
        with fitdecode.FitReader(str(path), check_crc=fitdecode.CrcCheck.RAISE,
                                 error_handling=fitdecode.ErrorHandling.RAISE) as reader:
            for message in reader:
                if not isinstance(message, fitdecode.FitDataMessage):
                    continue
                counts[message.name] += 1
                values = {field.name: field.value for field in message.fields if field.value is not None}
                if message.name == 'record':
                    timestamp = values.get('timestamp')
                    if timestamp is None:
                        raise ValueError('record FIT senza timestamp')
                    time = timestamp.timestamp()
                    if previous_time is not None and time < previous_time:
                        order_notes.append({'record_index': counts['record'], 'time_unix': time,
                                            'previous_time_unix': previous_time})
                    previous_time = time
                    target = records.setdefault(time, {})
                    for name, value in values.items():
                        if name in target and target[name] != value:
                            conflicts[name] += 1
                        target[name] = value
                elif message.name == 'event' and values.get('event') == 'timer':
                    if 'timestamp' not in values or 'event_type' not in values:
                        raise ValueError('evento timer FIT incompleto')
                    events.append({'time_unix': values['timestamp'].timestamp(),
                                   'event_type': values['event_type'],
                                   'trigger': values.get('timer_trigger')})
                elif message.name == 'session':
                    sessions.append({name: value.timestamp() if hasattr(value, 'timestamp') else value
                                     for name, value in values.items()
                                     if name in ('start_time', 'timestamp', 'sport', 'sub_sport',
                                                 'total_timer_time', 'total_elapsed_time', 'total_distance',
                                                 'total_ascent', 'total_descent', 'autopause_enabled')})
    except fitdecode.FitError as error:
        raise ValueError(f'FIT non valido: {error}') from error
    if not events and infer_missing_timer:
        intervals, notes = None, [{'reason': 'missing_timer_gps_inference_requested'}]
    else:
        intervals, notes = timer_intervals(events)
    # FIT trasporta messaggi: l'ordine nel contenitore può differire da quello
    # delle misure. L'asse usa gli orari registrati, senza modificarli.
    rows = [(index, time, row) for index, (time, row) in enumerate(sorted(records.items()), 1)
            if 'position_lat' in row and 'position_long' in row]
    if len(rows) < 2:
        raise ValueError('almeno due campioni GPS con coordinate richiesti nel FIT')

    def channel(name, alternate=None, scale=1.):
        return np.array([row.get(name, row.get(alternate, np.nan))*scale for _, _, row in rows], dtype=float)

    raw = {'lat': channel('position_lat', scale=180/2**31),
           'lon': channel('position_long', scale=180/2**31),
           'ele': channel('enhanced_altitude', 'altitude'),
           't_unix': np.array([time for _, time, _ in rows]),
           'source_index': np.array([index for index, _, _ in rows], dtype=int),
           'segment_index': np.ones(len(rows), dtype=int),
           'recorded_distance_m': channel('distance'),
           'recorded_speed_kmh': channel('enhanced_speed', 'speed', scale=3.6),
           'gps_accuracy_m': channel('gps_accuracy')}
    metadata = {'format': 'fit', 'message_counts': dict(counts), 'sessions': sessions,
                'timer_events': events, 'timer_intervals': intervals, 'timer_notes': notes,
                'timer_duration_s': sum(b-a for a, b in intervals) if intervals is not None else None,
                'record_timestamp_conflicts': dict(conflicts),
                'out_of_order_records': order_notes,
                'record_timestamps_without_coordinates': len(records)-len(rows)}
    declared = [s['total_timer_time'] for s in sessions if 'total_timer_time' in s]
    if len(declared) == len(sessions) and declared:
        metadata['declared_timer_duration_s'] = sum(declared)
        if intervals is not None:
            metadata['timer_duration_difference_s'] = metadata['timer_duration_s']-sum(declared)
    return raw, metadata
