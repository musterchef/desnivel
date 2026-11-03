"""Ricerca separata del fondo stradale OSM, con associazioni spaziali esplicite."""
from datetime import datetime, timezone
import math

from desnivel.trip.context import ContextSource, route_intervals, track_signature
from desnivel.trip.context_http import request_json


def _distance_to_way(latitude, longitude, geometry):
    """Distanza metrica locale dal punto alla polilinea, non dai soli nodi."""
    scale = math.cos(math.radians(latitude))
    points = [(math.radians(p['lon']-longitude)*6371000*scale,
               math.radians(p['lat']-latitude)*6371000) for p in geometry]
    best = math.inf
    for (ax, ay), (bx, by) in zip(points, points[1:]):
        dx, dy = bx-ax, by-ay
        length = dx*dx+dy*dy
        amount = max(0., min(1., -(ax*dx+ay*dy)/length)) if length else 0.
        best = min(best, math.hypot(ax+amount*dx, ay+amount*dy))
    return best


class SurfaceFetcher:
    endpoint = 'https://overpass-api.de/api/interpreter'

    def __init__(self, request=request_json):
        self.request = request

    @staticmethod
    def match(latitude, longitude, ways, *, radius_m=25., ambiguity_m=5.):
        candidates = sorted(((_distance_to_way(latitude, longitude, w['geometry']), w['id'], w)
                             for w in ways if w.get('type') == 'way' and w.get('tags', {}).get('highway')
                             and len(w.get('geometry', [])) >= 2), key=lambda item: (item[0], item[1]))
        candidates = [c for c in candidates if c[0] <= radius_m]
        if not candidates:
            return None, dict(status='no_road_within_radius')
        distance, way_id, way = candidates[0]
        details = dict(way_id=way_id, distance_m=distance, tags=way['tags'])
        if len(candidates) > 1 and candidates[1][0]-distance <= ambiguity_m:
            return None, dict(details, status='ambiguous', candidate_way_ids=[c[1] for c in candidates
                                                                          if c[0]-distance <= ambiguity_m])
        surface = way['tags'].get('surface')
        return surface, dict(details, status='matched' if surface else 'surface_not_tagged')

    def fetch(self, track, *, distance_step_m=100.):
        intervals = route_intervals(track, distance_step_m=distance_step_m)
        records, acquisitions = [], []
        for start in range(0, len(intervals), 20):
            batch = intervals[start:start+20]
            south = min(r['latitude'] for r in batch)-.0003
            north = max(r['latitude'] for r in batch)+.0003
            padding = .0003/max(.01, math.cos(math.radians((north+south)/2)))
            west = min(r['longitude'] for r in batch)-padding
            east = max(r['longitude'] for r in batch)+padding
            if east-west >= 180:
                raise ValueError('ricerca del fondo attraverso l’antimeridiano non supportata')
            query = f'[out:json][timeout:60];way["highway"]({south},{west},{north},{east});out tags geom;'
            response = self.request(self.endpoint, {'data': query}, post=True)
            if response.get('remark') or not isinstance(response.get('elements'), list):
                raise ValueError('risposta Overpass incompleta o non valida')
            acquisitions.append(dict(query=query, response=response))
            for interval in batch:
                if interval['end_distance_m'] <= interval['start_distance_m']:
                    continue
                value, details = self.match(interval['latitude'], interval['longitude'], response['elements'])
                records.append(dict(segment=interval['segment'], start=interval['start_distance_m'],
                    end=interval['end_distance_m'], values={'surface': value},
                    details=dict(details, latitude=interval['latitude'], longitude=interval['longitude'])))
        return ContextSource(dict(version=1, source='surface', track_signature=track_signature(track), axis='distance',
            units={'surface': 'category'}, records=records, provenance=dict(provider='OpenStreetMap / Overpass',
                endpoint=self.endpoint, distance_step_m=distance_step_m, radius_m=25., ambiguity_m=5.,
                historical=False, retrieved_at=datetime.now(timezone.utc).isoformat(),
                attribution='© OpenStreetMap contributors, ODbL: https://www.openstreetmap.org/copyright',
                acquisitions=acquisitions)))
