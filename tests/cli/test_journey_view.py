import json
import os
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np
import pytest

from desnivel.sinks.session_status import SessionStatusStore
from desnivel.trip.track import Track, TrackSegment
from desnivel.viewer.route import route_payload
from desnivel.viewer.server import JourneyViewServer


def track():
    return Track('test', np.array([0., 10., 10., 20.]),
                 {'lat': np.array([43., 43.1, 44., 44.1]),
                  'lon': np.array([11., 11.1, 12., 12.1])},
                 segments=(TrackSegment(0, 2, 100, 110, 0, 1),
                           TrackSegment(2, 4, 200, 210, 2, 3)))


def test_geometry_preserves_discontinuities_and_active_time():
    payload = route_payload(track())
    assert payload['segments'] == [[[0, 43, 11], [10, 43.1, 11.1]],
                                   [[10, 44, 12], [20, 44.1, 12.1]]]
    json.dumps(payload, allow_nan=False)


def test_geometry_rejects_invalid_coordinates():
    source = track()
    source.samples['lat'][1] = np.nan
    with pytest.raises(ValueError, match='coordinate'):
        route_payload(source)


def test_server_reads_replaced_snapshots_reports_age_and_serves_only_view_assets(tmp_path):
    store = SessionStatusStore(tmp_path / 'state.json')
    server = JourneyViewServer(track(), store.path, 0)
    server.start()
    def get(path):
        with urlopen(server.url + path, timeout=2) as response:
            assert response.headers['Cache-Control'] == 'no-store'
            return response.read()
    try:
        with pytest.raises(HTTPError) as error:
            get('api/state')
        assert error.value.code == 503
        store.write({'state': 'playing', 'trip': {'elapsed_s': 5}})
        assert json.loads(get('api/state'))['session']['trip']['elapsed_s'] == 5
        store.write({'state': 'stopped', 'trip': {'elapsed_s': 7}})
        old = time.time()-10
        os.utime(store.path, (old, old))
        payload = json.loads(get('api/state'))
        assert payload['session']['state'] == 'stopped'
        assert payload['session']['trip']['elapsed_s'] == 7
        assert payload['age_s'] >= 10
        assert json.loads(get('api/route')) == route_payload(track())
        assert b'lang="it"' in get('')
        for path in ('view.js', 'music.js', 'position.js', 'view.css'):
            assert get(path)
        with pytest.raises(HTTPError) as error:
            get('../state.json')
        assert error.value.code == 404
    finally:
        server.close()
    assert not server.thread.is_alive()


def test_ensemble_starts_view_with_initial_state_and_closes_it_on_interrupt(tmp_path, monkeypatch):
    from desnivel.adapters.voice_device import VoiceDeviceBridge
    from desnivel.cli import ensemble, voice_device
    from desnivel.trip import loader
    from desnivel.viewer import server as view_module

    source = track()
    source.samples['cum_dist_m'] = np.array([0., 10., 10., 20.])
    monkeypatch.setattr(loader, 'load_track', lambda *args, **kwargs: source)
    monkeypatch.setattr('desnivel.cli.weather_context.prepare_weather_context', lambda *args, **kwargs: None)
    views = []

    def create_view(track, path, port):
        view = JourneyViewServer(track, path, 0)
        views.append(view)
        return view

    class DeviceServer:
        def __init__(self, *args):
            self.bridge = VoiceDeviceBridge({}, lambda *args: None)
            self.server = self
            self.closed = False

        def handle_request(self):
            with urlopen(views[0].url+'api/state', timeout=2) as response:
                state = json.load(response)
            assert state['session']['state'] == 'waiting_for_transport'
            assert state['session']['trip']['progress'] == 0
            assert state['age_s'] < 3
            raise KeyboardInterrupt

        def close(self):
            self.closed = True

    monkeypatch.setattr(view_module, 'JourneyViewServer', create_view)
    monkeypatch.setattr(voice_device, 'VoiceDeviceServer', DeviceServer)
    status = tmp_path / 'state.json'
    assert ensemble.main(['--track', 'unused.gpx', '--config', 'presets/organico.json', '--manual-sections',
                          '--view-port', '8765', '--status-file', str(status)]) == 0
    assert json.loads(status.read_text())['state'] == 'closed'
    assert not views[0].thread.is_alive()


def test_http_controls_are_queued_and_reject_other_origins(tmp_path):
    view = JourneyViewServer(track(), tmp_path / 'state.json', 0)
    view.start()
    def send(action, origin):
        request = Request(view.url+'api/control', data=json.dumps({'action': action}).encode(),
                          headers={'Content-Type': 'application/json', 'Origin': origin})
        return urlopen(request, timeout=2)
    try:
        with pytest.raises(HTTPError) as error:
            send('restart', 'https://other.example')
        assert error.value.code == 403
        assert list(view.take_commands()) == []
        with send('pause', view.url.rstrip('/')) as response:
            assert response.status == 202
        with send('restart', view.url.rstrip('/')):
            pass
        assert list(view.take_commands()) == ['pause', 'restart']
        from desnivel.cli.recording import main as record
        for mode in ('audio', 'midi', 'both', 'start', 'stop'):
            record([mode, '--view-port', str(view.server.server_port)])
        assert list(view.take_commands()) == ['record_audio', 'record_midi', 'record_both', 'record_start', 'record_stop']
        with pytest.raises(HTTPError) as error:
            send('arbitrary', view.url.rstrip('/'))
        assert error.value.code == 400
    finally:
        view.close()
