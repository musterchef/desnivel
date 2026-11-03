"""Acquisizione meteorologica storica lungo posizione e orario del viaggio."""
from bisect import bisect_left
from datetime import datetime, timezone
import math

from desnivel.trip.context import ContextSource, route_intervals, track_signature
from desnivel.trip.context_http import request_json


class WeatherFetcher:
    endpoint = 'https://archive-api.open-meteo.com/v1/archive'

    def __init__(self, request=request_json):
        self.request = request

    def fetch(self, track, *, distance_step_m=5000.):
        intervals = route_intervals(track, distance_step_m=distance_step_m, hourly=True)
        date = lambda timestamp: datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()
        records, responses = [], []
        for start in range(0, len(intervals), 20):
            batch = intervals[start:start+20]
            params = dict(latitude=','.join(str(r['latitude']) for r in batch),
                          longitude=','.join(str(r['longitude']) for r in batch),
                          start_date=date(min(r['source_unix'] for r in batch)-7200),
                          end_date=date(max(r['source_unix'] for r in batch)+3600),
                          hourly='wind_speed_10m,precipitation', models='era5',
                          wind_speed_unit='kmh', precipitation_unit='mm', timeformat='unixtime', timezone='UTC')
            response = self.request(self.endpoint, params)
            locations = response if isinstance(response, list) else [response]
            if len(locations) != len(batch):
                raise ValueError('numero di località meteo diverso dalla richiesta')
            responses.append(dict(request=params, response=response))
            for interval, location in zip(batch, locations):
                values = self._values(location, interval['source_unix'])
                records.append(dict(segment=interval['segment'], start=interval['start'], end=interval['end'],
                                    values=values, details={k: interval[k] for k in ('latitude', 'longitude', 'source_unix')}))
        return ContextSource(dict(version=1, source='weather', track_signature=track_signature(track), axis='time',
            units={'wind_speed_kmh': 'km/h', 'precipitation_mm': 'mm', 'precipitation_change_mm': 'mm'},
            records=records, provenance=dict(provider='Open-Meteo', model='era5', temporal_resolution_s=3600,
                distance_step_m=distance_step_m, endpoint=self.endpoint,
                retrieved_at=datetime.now(timezone.utc).isoformat(),
                attribution='Weather data by Open-Meteo.com; ERA5 (Copernicus)', acquisitions=responses)))

    @staticmethod
    def _values(location, timestamp):
        hourly = location.get('hourly', {})
        units = location.get('hourly_units', {})
        if units.get('wind_speed_10m') != 'km/h' or units.get('precipitation') != 'mm':
            raise ValueError('unità meteorologiche inattese')
        times = hourly.get('time', [])
        wind, rain = hourly.get('wind_speed_10m', []), hourly.get('precipitation', [])
        if (not times or len(times) != len(wind) or len(times) != len(rain)
                or any(type(t) not in (int, float) or not math.isfinite(t) for t in times)
                or any(b-a != 3600 for a, b in zip(times, times[1:]))):
            raise ValueError('serie meteorologica oraria non valida')
        if any(v is not None and (type(v) not in (int, float) or not math.isfinite(v) or v < 0)
               for v in (*wind, *rain)):
            raise ValueError('valori meteorologici non validi')
        i = bisect_left(times, timestamp)
        if not 0 < i < len(times):
            return dict(wind_speed_kmh=None, precipitation_mm=None, precipitation_change_mm=None)
        # Precipitazione: accumulo dell'ora precedente al timestamp API, non valore istantaneo.
        # Il confronto usa due ore nello stesso punto geografico, senza confondere lo
        # spostamento fra celle con un cambiamento temporale delle precipitazioni.
        delta = rain[i]-rain[i-1] if rain[i] is not None and rain[i-1] is not None else None
        speed = (wind[i-1]+(wind[i]-wind[i-1])*(timestamp-times[i-1])/3600
                 if wind[i] is not None and wind[i-1] is not None else None)
        return dict(wind_speed_kmh=speed, precipitation_mm=rain[i], precipitation_change_mm=delta)
