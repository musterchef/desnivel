"""Lettura delle attività e dei campioni originali tramite API Strava."""
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from desnivel.settings import DEFAULT_SETTINGS


def request_json(url, *, token=None, form=None):
    """Richiesta JSON con timeout; gli errori non riportano credenziali o corpo."""
    headers = {'Accept': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    data = None
    if form is not None:
        data = urlencode(form).encode('utf-8')
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    try:
        with urlopen(Request(url, data=data, headers=headers),
                     timeout=DEFAULT_SETTINGS.network.strava_timeout_s) as response:
            return json.load(response)
    except HTTPError as error:
        hints = {401: 'autorizzazione scaduta o non valida',
                 403: 'permessi insufficienti per leggere l’attività',
                 404: 'attività o dati non disponibili',
                 429: 'limite di richieste raggiunto: riprovare più tardi'}
        raise ValueError(f'Strava HTTP {error.code}: {hints.get(error.code, "richiesta non riuscita")}') from None
    except URLError:
        raise ValueError('collegamento a Strava non riuscito') from None


def list_activities(token, after, before):
    """Legge tutte le pagine nell'intervallo indicato, in secondi Unix."""
    activities, page = [], 1
    page_size = DEFAULT_SETTINGS.network.strava_page_size
    while True:
        query = urlencode(dict(after=int(after), before=int(before), page=page, per_page=page_size))
        batch = request_json(f'https://www.strava.com/api/v3/athlete/activities?{query}', token=token)
        if not isinstance(batch, list):
            raise ValueError('elenco attività Strava non valido')
        activities.extend(batch)
        if len(batch) < page_size:
            return activities
        page += 1


def download_activity(token, activity_id):
    """Scarica dettaglio e stream; time, moving e latlng sono obbligatori."""
    if type(activity_id) is not int or activity_id <= 0:
        raise ValueError('ID attività positivo richiesto')
    base = f'https://www.strava.com/api/v3/activities/{activity_id}'
    activity = request_json(base, token=token)
    query = urlencode({'keys': 'time,moving,latlng,distance,altitude,velocity_smooth,grade_smooth',
                       'key_by_type': 'true'})
    streams = request_json(f'{base}/streams?{query}', token=token)
    if not isinstance(activity, dict) or activity.get('id') != activity_id:
        raise ValueError('dettaglio attività Strava non valido')
    if not isinstance(streams, dict):
        raise ValueError('stream Strava non validi')
    for key in ('time', 'moving', 'latlng'):
        if not isinstance(streams.get(key), dict) or not isinstance(streams[key].get('data'), list):
            raise ValueError(f'Strava non ha restituito lo stream necessario: {key}')
    count = len(streams['time']['data'])
    if not count or any(len(stream['data']) != count for stream in streams.values()):
        raise ValueError('stream Strava vuoti o con lunghezze differenti')
    return {'activity': activity, 'streams': streams}
