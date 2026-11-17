"""Ricerca separata del fondo stradale OSM, con associazioni spaziali esplicite."""
from datetime import datetime, timezone
import math

from desnivel.trip.context import ContextSource, route_intervals, track_signature
from desnivel.trip.context_http import request_json
from desnivel.settings import DEFAULT_SETTINGS


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

    def __init__(self, request=request_json, settings=None, network_settings=None):
        self.request = request
        self.settings = settings or DEFAULT_SETTINGS.context.surface
        self.network_settings = network_settings or DEFAULT_SETTINGS.network

    @staticmethod
    def match(latitude, longitude, ways, *, radius_m=None, ambiguity_m=None):
        defaults = DEFAULT_SETTINGS.context.surface
        radius_m = defaults.match_radius_m if radius_m is None else radius_m
        ambiguity_m = defaults.ambiguity_m if ambiguity_m is None else ambiguity_m
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

    def fetch(self, track, *, distance_step_m=None):
        distance_step_m = self.settings.distance_step_m if distance_step_m is None else distance_step_m
        intervals = route_intervals(track, distance_step_m=distance_step_m)
        records, acquisitions = [], []
        for start in range(0, len(intervals), self.settings.batch_size):
            batch = intervals[start:start+self.settings.batch_size]
            margin = self.settings.bbox_padding_degrees
            south = min(r['latitude'] for r in batch)-margin
            north = max(r['latitude'] for r in batch)+margin
            padding = margin/max(.01, math.cos(math.radians((north+south)/2)))
            west = min(r['longitude'] for r in batch)-padding
            east = max(r['longitude'] for r in batch)+padding
            if east-west >= 180:
                raise ValueError('ricerca del fondo attraverso l’antimeridiano non supportata')
            query = f'[out:json][timeout:60];way["highway"]({south},{west},{north},{east});out tags geom;'
            response = self.request(
                self.endpoint, {'data': query}, post=True,
                timeout_s=self.network_settings.context_timeout_s)
            if response.get('remark') or not isinstance(response.get('elements'), list):
                raise ValueError('risposta Overpass incompleta o non valida')
            acquisitions.append(dict(query=query, response=response))
            for interval in batch:
                if interval['end_distance_m'] <= interval['start_distance_m']:
                    continue
                value, details = self.match(
                    interval['latitude'], interval['longitude'], response['elements'],
                    radius_m=self.settings.match_radius_m, ambiguity_m=self.settings.ambiguity_m)
                records.append(dict(segment=interval['segment'], start=interval['start_distance_m'],
                    end=interval['end_distance_m'], values={'surface': value},
                    details=dict(details, latitude=interval['latitude'], longitude=interval['longitude'])))
        return ContextSource(dict(version=1, source='surface', track_signature=track_signature(track), axis='distance',
            units={'surface': 'category'}, records=records, provenance=dict(provider='OpenStreetMap / Overpass',
                endpoint=self.endpoint, distance_step_m=distance_step_m,
                radius_m=self.settings.match_radius_m, ambiguity_m=self.settings.ambiguity_m,
                historical=False, retrieved_at=datetime.now(timezone.utc).isoformat(),
                attribution='© OpenStreetMap contributors, ODbL: https://www.openstreetmap.org/copyright',
                acquisitions=acquisitions)))
