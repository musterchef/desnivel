"""Riduzione locale delle campate in continuità strutturali del percorso."""
from __future__ import annotations

from copy import deepcopy

from desnivel.settings import RouteStructureSettings


def _validate(settings):
    if not isinstance(settings, RouteStructureSettings):
        raise TypeError('forma strutturale: richieste impostazioni RouteStructureSettings')
    return settings


def _episode(span):
    return {
        'trend': span['trend'],
        'start_distance_m': span['start_distance_m'],
        'end_distance_m': span['end_distance_m'],
        'distance_m': span['distance_m'],
        'start_active_s': span['start_active_s'],
        'end_active_s': span['end_active_s'],
        'active_duration_s': span['active_duration_s'],
        'elevation_delta_m': span['elevation_delta_m'],
        'mean_slope_ratio': span['mean_slope_ratio'],
        'source_kinds': [span['source_kind']],
        'span_indices': [span['index']],
        'local_variations': [],
    }


def _contiguous(before, after):
    return before['end_distance_m'] == after['start_distance_m']


def _merged(parts, trend, reversals):
    first, last = parts[0], parts[-1]
    distance = sum(part['distance_m'] for part in parts)
    elevation = sum(part['elevation_delta_m'] for part in parts)
    kinds = []
    for part in parts:
        for kind in part['source_kinds']:
            if not kinds or kind != kinds[-1]:
                kinds.append(kind)
    return {
        'trend': trend,
        'start_distance_m': first['start_distance_m'],
        'end_distance_m': last['end_distance_m'],
        'distance_m': distance,
        'start_active_s': first['start_active_s'],
        'end_active_s': last['end_active_s'],
        'active_duration_s': sum(part['active_duration_s'] for part in parts),
        'elevation_delta_m': elevation,
        'mean_slope_ratio': elevation/distance,
        'source_kinds': kinds,
        'span_indices': [index for part in parts for index in part['span_indices']],
        'local_variations': reversals,
    }


def _coalesce(episodes):
    result = []
    for episode in episodes:
        if result and result[-1]['trend'] == episode['trend'] and _contiguous(result[-1], episode):
            previous = result.pop()
            reversals = previous['local_variations']+episode['local_variations']
            result.append(_merged([previous, episode], previous['trend'], reversals))
        else:
            result.append(episode)
    return result


def _can_merge_reversal(before, reversal, after, settings):
    if (before['trend'] != after['trend'] or before['trend'] == 'level'
            or reversal['trend'] in (before['trend'], 'level')
            or not _contiguous(before, reversal) or not _contiguous(reversal, after)):
        return False
    dominant_elevation = abs(before['elevation_delta_m'])+abs(after['elevation_delta_m'])
    dominant_distance = before['distance_m']+after['distance_m']
    reversed_elevation = abs(reversal['elevation_delta_m'])
    if dominant_elevation <= 0 or dominant_distance <= 0 or reversed_elevation <= 0:
        return False
    return (
        reversal['distance_m'] <= settings.max_reversal_distance_m
        and reversed_elevation/dominant_elevation <= settings.max_relative_elevation
        and reversal['distance_m']/dominant_distance <= settings.max_relative_distance
        and abs(after['elevation_delta_m'])/reversed_elevation >= settings.min_recovery_ratio
    )


def derive_route_episodes(spans, settings):
    """Riunisce inversioni locali alla continuità che riprende."""
    settings = _validate(settings)
    if not isinstance(spans, list) or not spans:
        raise ValueError('forma strutturale: campate non vuote richieste')
    episodes = _coalesce([_episode(span) for span in spans])
    if not settings.merge_reversals:
        return [{'index': index, **deepcopy(episode)} for index, episode in enumerate(episodes)]
    while True:
        candidates = []
        for index in range(1, len(episodes)-1):
            before, reversal, after = episodes[index-1:index+2]
            if _can_merge_reversal(before, reversal, after, settings):
                ratio = abs(reversal['elevation_delta_m']) / (
                    abs(before['elevation_delta_m'])+abs(after['elevation_delta_m']))
                candidates.append((ratio, index))
        if not candidates:
            break
        _, index = min(candidates)
        before, reversal, after = episodes[index-1:index+2]
        variation = {
            'trend': reversal['trend'],
            'start_distance_m': reversal['start_distance_m'],
            'end_distance_m': reversal['end_distance_m'],
            'distance_m': reversal['distance_m'],
            'elevation_delta_m': reversal['elevation_delta_m'],
            'span_indices': list(reversal['span_indices']),
        }
        reversals = (before['local_variations']+[variation]
                     +reversal['local_variations']+after['local_variations'])
        episodes[index-1:index+2] = [_merged([before, reversal, after], before['trend'], reversals)]
        episodes = _coalesce(episodes)
    result = []
    for index, episode in enumerate(episodes):
        result.append({'index': index, **deepcopy(episode)})
    return result
