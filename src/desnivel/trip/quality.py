"""Ispezione delle velocità derivate dai punti GPX originali, senza filtri."""
from dataclasses import asdict
from datetime import datetime, timezone

import numpy as np

from desnivel.settings import DEFAULT_SETTINGS

from .loader._geo import haversine_m


def inspect_source(raw, *, top_count=None, neighbor_points=None,
                   max_speed_kmh=None, review_settings=None):
    """Ordina gli intervalli per velocità e conserva i punti necessari alla verifica.

    Non classifica gli intervalli veloci come errori e non modifica le misure.
    Una velocità richiede coordinate e tempi validi nello stesso segmento,
    senza punti scartati dal parser fra i due estremi.
    """
    defaults = asdict(DEFAULT_SETTINGS.trip.quality)
    top_count = defaults.pop('top_count') if top_count is None else top_count
    neighbor_points = defaults.pop('neighbor_points') if neighbor_points is None else neighbor_points
    max_speed_kmh = (DEFAULT_SETTINGS.trip.gpx.max_speed_kmh
                     if max_speed_kmh is None else max_speed_kmh)
    if type(top_count) is not int or top_count < 1 or type(neighbor_points) is not int or neighbor_points < 0:
        raise ValueError('top_count positivo e neighbor_points non negativo richiesti')
    channels = {key: np.asarray(raw[key]) for key in
                ('lat', 'lon', 'ele', 't_unix', 'source_index', 'segment_index')}
    n = channels['lat'].size
    if not n or any(a.ndim != 1 or a.size != n for a in channels.values()):
        raise ValueError('canali sorgente monodimensionali, non vuoti e allineati richiesti')
    lat, lon, times = (channels[k] for k in ('lat', 'lon', 't_unix'))
    coordinates = np.isfinite(lat) & np.isfinite(lon) & (np.abs(lat) <= 90) & (np.abs(lon) <= 180)
    pair_coordinates = coordinates[:-1] & coordinates[1:]
    distances = np.full(n-1, np.nan)
    distances[pair_coordinates] = haversine_m(lat[:-1][pair_coordinates], lon[:-1][pair_coordinates],
                                             lat[1:][pair_coordinates], lon[1:][pair_coordinates])
    dt = np.diff(times)
    reasons = {
        'invalid_coordinates': ~pair_coordinates,
        'missing_time': ~np.isfinite(times[:-1]) | ~np.isfinite(times[1:]),
        'non_increasing_time': np.isfinite(dt) & (dt <= 0),
        'segment_boundary': (channels['segment_index'][:-1] != channels['segment_index'][1:])
                            | (channels['segment_index'][:-1] == 0),
        'skipped_point': np.diff(channels['source_index']) != 1,
    }
    available = ~np.logical_or.reduce(list(reasons.values()))
    speeds = np.full(n-1, np.nan)
    speeds[available] = distances[available]/dt[available]*3.6
    # Asse sorgente non corretto: include anche i collegamenti fra segmenti.
    # Rimane distinto dalla distanza osservata usata dal loader.
    cumulative = np.r_[0., np.cumsum(np.where(np.isfinite(distances), distances, 0.))]

    def finite(value):
        return float(value) if np.isfinite(value) else None

    def interval(index):
        return {'distance_m': finite(distances[index]), 'duration_s': finite(dt[index]),
                'speed_kmh': finite(speeds[index]),
                'unavailable_reasons': [key for key, mask in reasons.items() if mask[index]]}

    def point(index):
        time = times[index]
        return {'source_index': int(channels['source_index'][index]),
                'segment_index': int(channels['segment_index'][index]),
                'time_utc': datetime.fromtimestamp(float(time), timezone.utc).isoformat() if np.isfinite(time) else None,
                'lat': finite(lat[index]), 'lon': finite(lon[index]),
                'elevation_m': finite(channels['ele'][index]),
                'source_distance_m': float(cumulative[index]),
                'incoming_interval': interval(index-1) if index else None}

    valid_indices = np.flatnonzero(available)
    order = valid_indices[np.argsort(-speeds[valid_indices], kind='stable')][:top_count]
    fastest = []
    for i in order:
        fastest.append({**interval(i), 'start': point(i), 'end': point(i+1),
                        'neighbors': [point(j) for j in range(max(0, i-neighbor_points),
                                                           min(n, i+neighbor_points+2))]})
    valid_speeds = speeds[available]
    settings = {**defaults, **(review_settings or {})}
    if (set(settings) != set(defaults) or any(type(v) not in (int, float) or not np.isfinite(v) or v <= 0
                                                    for v in (*settings.values(), max_speed_kmh))):
        raise ValueError('criteri di revisione noti, positivi e finiti richiesti')
    flags = {key: mask.copy() for key, mask in reasons.items()}
    flags['speed_limit'] = available & (speeds > max_speed_kmh)
    flags['moving_sampling_gap'] = available & (dt > settings['sampling_gap_s']) & (distances > settings['gap_distance_m'])
    flags['resume_after_stationary_coordinates'] = np.zeros(n-1, dtype=bool)
    regular_time = np.isfinite(times).all() and (np.diff(times) > 0).all()
    if regular_time:
        for i in np.flatnonzero(available & (distances > settings['resume_distance_m'])):
            start = np.searchsorted(times, times[i]-settings['stationary_duration_s'], side='right')-1
            if (start < 0 or not (coordinates[start:i+1]).all()
                    or not (np.diff(channels['source_index'][start:i+1]) == 1).all()
                    or not (channels['segment_index'][start:i+1] == channels['segment_index'][i]).all()):
                continue
            radius = haversine_m(lat[start:i+1], lon[start:i+1], lat[i], lon[i])
            flags['resume_after_stationary_coordinates'][i] = radius.max() <= settings['stationary_radius_m']
    groups = []
    for i in np.flatnonzero(np.logical_or.reduce(list(flags.values()))):
        previous = groups[-1][-1] if groups else None
        if (previous is not None and regular_time
                and times[i]-times[previous+1] <= settings['group_gap_s']
                and (channels['segment_index'][previous:i+2] == channels['segment_index'][i]).all()):
            groups[-1].append(int(i))
        else:
            groups.append([int(i)])
    review = []
    for group in groups:
        a, b = group[0], group[-1]+1
        left = max(0, int(np.searchsorted(times, times[a]-settings['context_s']))) if regular_time else max(0, a-neighbor_points)
        right = min(n, int(np.searchsorted(times, times[b]+settings['context_s'], side='right'))) if regular_time else min(n, b+neighbor_points+1)
        peak = group[int(np.argmax(np.where(np.isfinite(speeds[group]), speeds[group], -np.inf)))]
        review.append({'id': f'p{int(channels["source_index"][a])}-{int(channels["source_index"][b])}',
                       'start': point(a), 'end': point(b),
                       'reasons': [key for key, mask in flags.items() if mask[group].any()],
                       'flagged_interval_count': len(group), 'peak_speed_kmh': finite(speeds[peak]),
                       'peak_start': point(peak), 'peak_end': point(peak+1),
                       'context_start': point(left), 'context_end': point(right-1),
                       'context_mode': 'source_time' if regular_time else 'adjacent_points',
                       'flagged_intervals': [{'start_source_index': int(channels['source_index'][i]),
                                             'end_source_index': int(channels['source_index'][i+1]),
                                             **interval(i), 'review_reasons': [key for key, mask in flags.items() if mask[i]]}
                                            for i in group]})
    return {'points': n, 'segments': len(set(channels['segment_index']) - {0}),
            'missing_time_points': int(np.count_nonzero(~np.isfinite(times))),
            'missing_elevation_points': int(np.count_nonzero(~np.isfinite(channels['ele']))),
            'invalid_coordinate_points': int(np.count_nonzero(~coordinates)),
            'available_speed_intervals': int(available.sum()),
            'unavailable_speed_intervals': int((~available).sum()),
            'unavailable_reasons': {key: int(mask.sum()) for key, mask in reasons.items()},
            'speed_median_kmh': finite(np.median(valid_speeds)) if valid_speeds.size else None,
            'speed_p95_kmh': finite(np.percentile(valid_speeds, 95)) if valid_speeds.size else None,
            'fastest_intervals': fastest,
            'review_settings': {'top_count': top_count, 'neighbor_points': neighbor_points,
                                'max_speed_kmh': max_speed_kmh, **settings},
            'review_segments': review}
