"""Forma neutra della tappa ricavata dalle macrosezioni osservate."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import math

import numpy as np

from .route_structure import derive_route_episodes


def _trend(section):
    delta = section['elevation_delta_m']
    return 'rising' if delta > 0 else 'falling' if delta < 0 else 'level'


def _active_time_axis(track):
    distance = np.asarray(track.samples.get('cum_dist_m', []), dtype=float)
    time = np.asarray(track.t, dtype=float)
    if (distance.ndim != 1 or time.ndim != 1 or len(distance) != len(time) or len(distance) < 2
            or not np.isfinite(distance).all() or not np.isfinite(time).all()
            or np.any(distance[1:] < distance[:-1]) or np.any(time[1:] < time[:-1])
            or distance[-1] <= distance[0]):
        raise ValueError('forma della tappa: distanza e tempo attivo ordinati richiesti')
    distance = distance-distance[0]
    keep = np.r_[distance[1:] > distance[:-1], True]
    return distance[keep], time[keep]-time[0]


def _at(distance, time, position):
    return float(np.interp(position, distance, time))


def _boundary_kind(before, after, contiguous):
    if not contiguous:
        return 'observation_gap'
    pair = (_trend(before), _trend(after))
    if pair == ('rising', 'falling'):
        return 'summit'
    if pair == ('falling', 'rising'):
        return 'valley'
    return 'profile_change'


def describe_route_form(track, sections, structure_settings):
    """Descrive campate ed eventi reali senza assegnare funzioni musicali."""
    if not isinstance(sections, list) or not sections:
        raise ValueError('forma della tappa: macrosezioni non vuote richieste')
    distance, time = _active_time_axis(track)
    total = float(distance[-1])
    spans = []
    previous_end = None
    for index, section in enumerate(sections):
        required = {'index', 'kind', 'start_distance_m', 'end_distance_m',
                    'elevation_delta_m', 'mean_slope_ratio'}
        if not isinstance(section, dict) or required-section.keys():
            raise ValueError('forma della tappa: campi della macrosezione mancanti')
        start, end = section['start_distance_m'], section['end_distance_m']
        values = (start, end, section['elevation_delta_m'], section['mean_slope_ratio'])
        if (any(type(value) not in (int, float) or not math.isfinite(value) for value in values)
                or not 0 <= start < end <= total or previous_end is not None and start < previous_end):
            raise ValueError('forma della tappa: confini ordinati e misure finite richiesti')
        start_s, end_s = _at(distance, time, start), _at(distance, time, end)
        spans.append({'index': index, 'section_index': section['index'], 'source_kind': section['kind'],
                      'trend': _trend(section), 'start_distance_m': start, 'end_distance_m': end,
                      'distance_m': end-start, 'start_active_s': start_s, 'end_active_s': end_s,
                      'active_duration_s': end_s-start_s,
                      'elevation_delta_m': section['elevation_delta_m'],
                      'mean_slope_ratio': section['mean_slope_ratio']})
        previous_end = end
    events = [{'index': 0, 'type': 'departure', 'at_distance_m': spans[0]['start_distance_m'],
               'at_active_s': spans[0]['start_active_s'], 'to_span': 0}]
    for index in range(1, len(spans)):
        before, after = sections[index-1], sections[index]
        contiguous = before['end_distance_m'] == after['start_distance_m']
        position = after['start_distance_m']
        events.append({'index': len(events), 'type': _boundary_kind(before, after, contiguous),
                       'at_distance_m': position, 'at_active_s': _at(distance, time, position),
                       'from_span': index-1, 'to_span': index,
                       'from_source_kind': spans[index-1]['source_kind'],
                       'to_source_kind': spans[index]['source_kind'],
                       'from_trend': spans[index-1]['trend'], 'to_trend': spans[index]['trend']})
    events.append({'index': len(events), 'type': 'arrival', 'at_distance_m': spans[-1]['end_distance_m'],
                   'at_active_s': spans[-1]['end_active_s'], 'from_span': len(spans)-1})
    result = {'version': 1, 'stage': track.stage_id, 'spans': deepcopy(spans), 'events': events}
    result['structure_settings'] = asdict(structure_settings)
    result['episodes'] = derive_route_episodes(spans, structure_settings)
    return result
