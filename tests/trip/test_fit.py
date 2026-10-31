"""FIT reali nel formato binario: timer, CRC e pipeline comune al GPX."""
from datetime import datetime, timezone
import struct

from fitdecode.utils import compute_crc
import numpy as np
import pytest

from desnivel.trip.loader import load_track, read_source
from desnivel.trip.loader._fit import timer_intervals
from desnivel.trip.loader._parse import stage_id_from_path
from desnivel.trip.loader._derive import derive_channels
from desnivel.trip.config import DEFAULT_CONFIG


EPOCH = datetime(1989, 12, 31, tzinfo=timezone.utc).timestamp()
BASE = int(datetime(2025, 9, 20, 13, tzinfo=timezone.utc).timestamp()-EPOCH)


def write_fit(path, *, records=None, events=None, timer=4):
    """Piccolo file binario con definizioni FIT e CRC verificabile dal lettore."""
    def definition(local, global_number, fields):
        return bytes([0x40|local, 0, 0])+struct.pack('<H', global_number)+bytes([len(fields)])+b''.join(bytes(f) for f in fields)

    # Record: timestamp, lat/lon in semicircles, altitude, speed, distance.
    body = definition(0, 20, [(253, 4, 0x86), (0, 4, 0x85), (1, 4, 0x85),
                              (2, 2, 0x84), (6, 2, 0x84), (5, 4, 0x86)])
    rows = records if records is not None else [(0, 0), (1, 10), (2, 20), (3, 500), (11, 900), (12, 1000), (13, 1010), (14, 1020)]
    for time, metres in rows:
        lat = round((45+metres/111195)*2**31/180)
        lon = round(7*2**31/180)
        body += bytes([0])+struct.pack('<IiiHHI', BASE+time, lat, lon, 3000, 10000, int(metres*100))
    body += definition(1, 21, [(253, 4, 0x86), (0, 1, 0), (1, 1, 0)])
    for time, kind in (events if events is not None else [(0, 0), (2, 1), (12, 0), (14, 1)]):
        body += bytes([1])+struct.pack('<IBB', BASE+time, 0, kind)
    body += definition(2, 18, [(2, 4, 0x86), (7, 4, 0x86), (8, 4, 0x86), (9, 4, 0x86)])
    body += bytes([2])+struct.pack('<IIII', BASE, 14000, timer*1000, 102000)
    header = struct.pack('<BBHI4s', 12, 0x20, 2160, len(body), b'.FIT')
    payload = header+body
    path.write_bytes(payload+struct.pack('<H', compute_crc(payload)))
    return path


def test_fit_timer_excludes_paused_positions_before_channel_derivation(tmp_path, monkeypatch):
    from desnivel.trip.loader import track_loader
    calls = []
    original = track_loader.derive_channels

    def derive(raw, config):
        calls.append(raw['lat'].size)
        return original(raw, config)

    monkeypatch.setattr(track_loader, 'derive_channels', derive)
    track = load_track(write_fit(tmp_path/'tappa_6_trip.fit'))
    assert track.stage_id == 'tappa_06'
    assert track.duration_s == 4
    assert calls == [3, 3]
    assert len(track.segments) == 2
    assert track.samples['cum_dist_m'][-1] == pytest.approx(40, abs=.03)
    assert np.nanmax(track.samples['speed_kmh']) == pytest.approx(36, abs=.03)
    assert track.metadata['travel_selection']['selection_source'] == 'timer_events'
    assert track.metadata['source_recording']['timer_duration_difference_s'] == 0
    assert track.metadata['source_format'] == 'fit'
    assert track.samples['recorded_speed_kmh'][0] == 36
    assert track.samples['recorded_distance_m'][-1] == 1020


def test_timer_summary_mismatch_is_preserved_not_used_to_rescale_time(tmp_path):
    track = load_track(write_fit(tmp_path/'trip.fit', timer=3))
    assert track.duration_s == 4
    recording = track.metadata['source_recording']
    assert recording['declared_timer_duration_s'] == 3
    assert recording['timer_duration_s'] == 4
    assert recording['timer_duration_difference_s'] == 1


def test_stop_and_restart_at_same_second_do_not_remove_an_observed_interval(tmp_path):
    path = write_fit(tmp_path/'trip.fit', records=[(0, 0), (1, 10), (2, 20), (3, 30), (4, 40)],
                     events=[(0, 0), (2, 1), (2, 0), (4, 1)])
    track = load_track(path)
    assert track.duration_s == 4
    assert len(track.segments) == 1
    assert track.metadata['source_recording']['timer_intervals'] == [[EPOCH+BASE, EPOCH+BASE+4]]


def test_crc_error_is_rejected(tmp_path):
    path = write_fit(tmp_path/'trip.fit')
    payload = bytearray(path.read_bytes())
    payload[-1] ^= 1
    path.write_bytes(payload)
    with pytest.raises(ValueError, match='FIT non valido'):
        load_track(path)


def test_fit_without_timer_does_not_silently_infer_pauses(tmp_path):
    with pytest.raises(ValueError, match='nessun intervallo'):
        load_track(write_fit(tmp_path/'trip.fit', events=[]))


def test_late_duplicate_record_does_not_create_extra_time_or_distance(tmp_path):
    path = write_fit(tmp_path/'trip.fit', records=[(0, 0), (1, 10), (2, 20), (1, 10), (12, 1000), (13, 1010), (14, 1020)])
    raw, recording = read_source(path)
    assert len(recording['out_of_order_records']) == 1
    assert len(raw['t_unix']) == 6
    assert load_track(path).duration_s == 4


def test_out_of_order_messages_are_sorted_by_original_times_with_explicit_diagnostics(tmp_path):
    path = write_fit(tmp_path/'trip.fit', records=[(0, 0), (2, 20), (1, 10)])
    raw, metadata = read_source(path)
    assert np.array_equal(np.diff(raw['t_unix']), [1, 1])
    assert len(metadata['out_of_order_records']) == 1
    assert metadata['out_of_order_records'][0]['record_index'] == 3


def test_gpx_uses_fit_timer_without_replacing_gpx_coordinates_or_altitude(tmp_path):
    fit = write_fit(tmp_path/'trip.fit')
    raw, _ = read_source(fit)
    points = ''.join(f'<trkpt lat="{lat}" lon="{lon}"><ele>200</ele><time>'
                     f'{datetime.fromtimestamp(time, timezone.utc).isoformat()}</time></trkpt>'
                     for lat, lon, time in zip(raw['lat'], raw['lon'], raw['t_unix']))
    gpx = tmp_path/'trip.gpx'
    gpx.write_text(f'<gpx xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>{points}</trkseg></trk></gpx>')
    fit_track = load_track(fit)
    track = load_track(gpx, timing_reference=fit)
    assert np.array_equal(track.t, fit_track.t)
    assert track.samples['cum_dist_m'][-1] == pytest.approx(fit_track.samples['cum_dist_m'][-1])
    assert set(track.samples['ele']) == {200}
    assert track.metadata['timing_reference_path'] == str(fit)
    assert track.metadata['travel_selection']['selection_source'] == 'timer_events'


def test_invalid_reference_format_is_explicit(tmp_path):
    path = write_fit(tmp_path/'trip.fit')
    with pytest.raises(ValueError, match='sorgente GPX'):
        load_track(path, timing_reference=path)


def test_missing_or_reversed_timestamps_cannot_become_synthetic_motion():
    for times in ([0, np.nan, 2], [0, 2, 1]):
        raw = dict(lat=np.array([45., 45.001, 45.002]), lon=np.array([7.]*3), ele=np.array([100.]*3),
                   t_unix=np.array(times))
        with pytest.raises(ValueError, match='timestamp finiti'):
            derive_channels(raw, DEFAULT_CONFIG.gpx)


def test_timer_events_require_closed_intervals_but_allow_final_stop_already_paused():
    def event(time, kind):
        return dict(time_unix=time, event_type=kind)
    intervals, notes = timer_intervals([event(0, 'start'), event(2, 'stop'), event(3, 'stop')])
    assert intervals == [[0, 2]] and notes[0]['reason'] == 'stop_without_start'
    with pytest.raises(ValueError, match='ancora aperto'):
        timer_intervals([event(0, 'start')])


def test_strava_original_filename_identifies_stage_without_renaming():
    assert stage_id_from_path('Da_Piazza_Castello_al_Castel_lo_tappa_10_San_Nicola_Manfredi_San_Severo.fit') == 'tappa_10'


def test_analysis_command_accepts_fit_and_reports_timer_provenance(tmp_path):
    import json
    from desnivel.cli.analyze_trip import main
    path = write_fit(tmp_path/'tappa06_trip.fit')
    output, html = tmp_path/'report.json', tmp_path/'report.html'
    assert main(['--track', str(path), '--config', 'presets/analisi-percorso.json',
                 '--output', str(output), '--html', str(html)]) == 0
    data = json.loads(output.read_text())
    assert data['source_format'] == 'fit'
    assert data['travel_selection']['observed_duration_s'] == 4
    assert data['source_recording']['declared_timer_duration_s'] == 4
    assert 'timer FIT' in html.read_text()


def test_missing_fit_timer_can_explicitly_use_gps_pause_inference(tmp_path):
    path = write_fit(tmp_path/'trip.fit', events=[], records=[(i, i*10) for i in range(8)], timer=3)
    track = load_track(path, infer_missing_fit_timer=True)
    recording = track.metadata['source_recording']
    assert recording['timer_intervals'] is None
    assert recording['timer_duration_s'] is None
    assert recording['declared_timer_duration_s'] == 3
    assert 'timer_duration_difference_s' not in recording
    assert recording['timer_notes'] == [{'reason': 'missing_timer_gps_inference_requested'}]
    assert track.metadata['travel_selection']['selection_source'] == 'gps_inference'
    assert track.duration_s == 7


def test_missing_timer_option_preserves_real_events_and_rejects_an_incomplete_timer(tmp_path):
    assert load_track(write_fit(tmp_path/'valid.fit'), infer_missing_fit_timer=True).duration_s == 4
    with pytest.raises(ValueError, match='ancora aperto'):
        load_track(write_fit(tmp_path/'open.fit', events=[(0, 0)]), infer_missing_fit_timer=True)
