import json

from desnivel.cli import show_route_form


def route_form():
    return {
        'version': 1,
        'stage': 'test',
        'spans': [
            {'start_distance_m': 0, 'end_distance_m': 2000, 'source_kind': 'ascent', 'trend': 'rising',
             'active_duration_s': 3723, 'elevation_delta_m': 160, 'mean_slope_ratio': .08},
            {'start_distance_m': 2000, 'end_distance_m': 3000, 'source_kind': 'descent', 'trend': 'falling',
             'active_duration_s': 900, 'elevation_delta_m': -50, 'mean_slope_ratio': -.05},
        ],
        'events': [
            {'type': 'departure', 'at_distance_m': 0},
            {'type': 'summit', 'at_distance_m': 2000,
             'from_source_kind': 'ascent', 'to_source_kind': 'descent',
             'from_trend': 'rising', 'to_trend': 'falling'},
            {'type': 'arrival', 'at_distance_m': 3000},
        ],
    }


def test_terminal_view_exposes_spans_and_structural_events():
    rendered = show_route_form.render_route_form(route_form())
    assert 'FORMA DELLA TAPPA · test' in rendered
    assert '↑ salita' in rendered
    assert '1:02:03' in rendered
    assert '+160 m' in rendered
    assert 'km 2.00 · vetta · salita/↑ salita → discesa/↓ discesa' in rendered


def test_structural_view_is_primary_and_details_remain_available():
    form = route_form()
    form['episodes'] = [{
        'index': 0, 'start_distance_m': 0, 'end_distance_m': 3000,
        'trend': 'rising', 'active_duration_s': 4623,
        'elevation_delta_m': 110, 'local_variations': [{
            'trend': 'falling', 'start_distance_m': 1000, 'end_distance_m': 1200,
            'distance_m': 200, 'elevation_delta_m': -5, 'span_indices': [1],
        }],
    }]
    concise = show_route_form.render_route_form(form)
    assert 'VARIAZIONI LOCALI RIUNITE' in concise
    assert '200 m · -5.0 m' in concise
    assert 'CONTINUITÀ STRUTTURALI' in concise
    assert '2 campate osservate · 1 continuità strutturali' in concise
    assert 'EVENTI' not in concise
    assert 'EVENTI' in show_route_form.render_route_form(form, detailed=True)


def test_command_uses_project_direction_and_can_save_json(tmp_path, monkeypatch, capsys):
    track_path = tmp_path/'tappa.gpx'
    direction = tmp_path/'direzione.json'
    output = tmp_path/'forma.json'
    loaded = object()
    monkeypatch.setattr(show_route_form, 'load_track',
                        lambda path, timing_reference=None, config=None: loaded)
    calls = []
    monkeypatch.setattr(show_route_form, 'load_route_form',
                        lambda track, path, settings: calls.append((track, path, settings)) or route_form())

    assert show_route_form.main(['--track', str(track_path), '--direction', str(direction),
                                 '--output', str(output)]) == 0

    assert calls == [(loaded, direction, show_route_form.DEFAULT_SETTINGS_PATH)]
    assert json.loads(output.read_text()) == route_form()
    assert 'JSON completo:' in capsys.readouterr().out


def test_o_opens_the_track_picker(tmp_path, monkeypatch):
    selected = tmp_path/'scelta.gpx'
    loaded = object()
    monkeypatch.setattr(show_route_form, 'choose_track', lambda: selected)
    monkeypatch.setattr(show_route_form, 'load_track',
                        lambda path, timing_reference=None, config=None:
                        loaded if path == selected else None)
    monkeypatch.setattr(show_route_form, 'load_route_form',
                        lambda track, path, settings: route_form() if track is loaded else None)

    assert show_route_form.main(['--tappa', 'o']) == 0
