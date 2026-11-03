"""Contesti esterni riferiti ai tratti osservati, senza interpretazioni musicali."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path

import numpy as np


def track_signature(track):
    """Identifica campioni e tempi sorgente, anche a parità di nome della tappa."""
    digest = hashlib.sha256()
    for values in (track.t, *(track.samples.get(k, []) for k in ('lat', 'lon', 'cum_dist_m'))):
        array = np.asarray(values, dtype='<f8')
        digest.update(str(array.shape).encode())
        digest.update(array.tobytes())
    digest.update(json.dumps([asdict(s) for s in track.segments], sort_keys=True).encode())
    return digest.hexdigest()


class ContextSource:
    """Intervalli non sovrapposti, numerici o categorici, su tempo attivo o distanza."""

    def __init__(self, data):
        self.data = deepcopy(data)
        required = {'version', 'source', 'track_signature', 'axis', 'units', 'records', 'provenance'}
        if (not isinstance(data, dict) or set(data) != required or data['version'] != 1
                or data['axis'] not in ('time', 'distance')
                or not isinstance(data['source'], str) or not data['source']
                or not isinstance(data['track_signature'], str)
                or not isinstance(data['units'], dict) or not data['units']
                or any(not isinstance(k, str) or not isinstance(v, str) for k, v in data['units'].items())
                or not isinstance(data['provenance'], dict) or not isinstance(data['records'], list)):
            raise ValueError('sorgente di contesto non valida')
        previous = {}
        for record in data['records']:
            if not isinstance(record, dict) or set(record) != {'segment', 'start', 'end', 'values', 'details'}:
                raise ValueError('intervallo di contesto non valido')
            segment, start, end = record['segment'], record['start'], record['end']
            if (type(segment) is not int or segment < 0
                    or any(type(x) not in (int, float) or not math.isfinite(x) for x in (start, end))
                    or not 0 <= start < end or start < previous.get(segment, 0)
                    or not isinstance(record['values'], dict) or set(record['values']) != set(data['units'])
                    or not isinstance(record['details'], dict)):
                raise ValueError('intervalli ordinati e non sovrapposti richiesti per tratto')
            for value in record['values'].values():
                if value is not None and not (isinstance(value, str) and value
                        or type(value) in (int, float) and math.isfinite(value)):
                    raise ValueError('valore di contesto numerico finito, categoria o null richiesto')
            previous[segment] = end
        for name in data['units']:
            kinds = {isinstance(r['values'][name], str) for r in data['records'] if r['values'][name] is not None}
            if len(kinds) > 1:
                raise ValueError('un canale non può mescolare numeri e categorie')

    @classmethod
    def load(cls, path, track):
        source = cls(json.loads(Path(path).read_text(encoding='utf-8')))
        source.check_track(track)
        return source

    def check_track(self, track):
        if self.data['track_signature'] != track_signature(track):
            raise ValueError('contesto riferito a una traccia o a un ricampionamento diverso')

    def save(self, path):
        Path(path).write_text(json.dumps(self.data, ensure_ascii=False, allow_nan=False, indent=2)+'\n', encoding='utf-8')

    def describe(self, parts):
        """Aggrega le sole porzioni coperte, separando copertura di ogni canale."""
        low_key, high_key = (('start_active_s', 'end_active_s') if self.data['axis'] == 'time'
                             else ('start_distance_m', 'end_distance_m'))
        width = sum(p[high_key]-p[low_key] for p in parts)
        matches = []
        for part in parts:
            for record in self.data['records']:
                if record['segment'] != part['travel_segment_index']:
                    continue
                low, high = max(part[low_key], record['start']), min(part[high_key], record['end'])
                if high > low:
                    matches.append({**deepcopy(record), 'start': low, 'end': high, 'weight': high-low})
        channels = {}
        for name, unit in self.data['units'].items():
            valid = [r for r in matches if r['values'][name] is not None]
            covered = math.fsum(r['weight'] for r in valid)
            summary = dict(unit=unit, coverage_ratio=covered/width if width else 0., value=None)
            if valid and isinstance(valid[0]['values'][name], str):
                categories = {}
                for r in valid:
                    category = r['values'][name]
                    categories[category] = categories.get(category, 0.)+r['weight']/covered
                summary['categories'] = categories
            elif valid:
                summary['value'] = math.fsum(r['weight']*r['values'][name] for r in valid)/covered
            summary['status'] = ('available' if width and math.isclose(covered, width)
                                 else 'partial' if covered else 'unavailable')
            channels[name] = summary
        return dict(source=self.data['source'], axis=self.data['axis'], channels=channels,
                    records=matches, provenance=deepcopy({k: v for k, v in self.data['provenance'].items()
                                                        if k != 'acquisitions'}))


def route_intervals(track, *, distance_step_m, hourly=False):
    """Campiona ogni tratto separatamente, conservando coordinate e orari originali."""
    if not math.isfinite(distance_step_m) or distance_step_m <= 0:
        raise ValueError('passo spaziale positivo richiesto')
    if not track.segments:
        raise ValueError('contesto esterno: riferimenti ai tratti sorgente richiesti')
    result = []
    for index, segment in enumerate(track.segments):
        sl = slice(segment.start, segment.stop)
        t = track.t[sl]
        d = track.samples['cum_dist_m'][sl]-track.samples['cum_dist_m'][0]
        if len(t) < 2 or t[-1] <= t[0]:
            continue
        boundaries = [float(t[0]), float(t[-1])]
        # I duplicati di distanza (soste) non generano intervalli spaziali fittizi.
        for distance in np.arange(d[0]+distance_step_m, d[-1], distance_step_m):
            boundaries.append(float(np.interp(distance, d, t)))
        offset = segment.source_start_unix-t[0]
        if hourly:
            boundaries.extend(float(x-offset) for x in np.arange(
                (math.floor(segment.source_start_unix/3600)+1)*3600, segment.source_end_unix, 3600))
        boundaries = sorted(set(boundaries))
        for low, high in zip(boundaries, boundaries[1:]):
            midpoint = (low+high)/2
            lat = float(np.interp(midpoint, t, track.samples['lat'][sl]))
            lon = float(np.interp(midpoint, t, track.samples['lon'][sl]))
            if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
                raise ValueError('coordinate geografiche valide richieste')
            result.append(dict(segment=index, start=low, end=high,
                               start_distance_m=float(np.interp(low, t, d)),
                               end_distance_m=float(np.interp(high, t, d)),
                               latitude=lat, longitude=lon, source_unix=float(midpoint+offset)))
    if not result:
        raise ValueError('nessun intervallo osservato disponibile')
    return result
