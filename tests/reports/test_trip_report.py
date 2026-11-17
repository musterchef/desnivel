"""Integrità dei dati fra analisi, esportazione JSON e report HTML."""
import json
from html.parser import HTMLParser
from pathlib import Path

import numpy as np
import pytest

from desnivel.reports.trip import render_trip_report
from desnivel.trip.analysis import analyze_track
from desnivel.trip.track import Track


class EmbeddedAnalysis(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.in_data = False
        self.payload = ''
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.in_data = tag == 'script' and dict(attrs).get('id') == 'analysis-data'

    def handle_endtag(self, tag):
        if tag == 'script':
            self.in_data = False

    def handle_data(self, data):
        if self.in_data:
            self.payload += data


def test_arbitrary_names_are_preserved_as_data_and_cannot_close_script():
    name = '</script><img src=x onerror=alert(1)>'
    config = {'sample_distance_m': 100, 'slope_window_m': 200,
              'min_zone_distance_m': 100,
              'bands': [{'name': name, 'from_slope_ratio': None}]}
    track = Track(name, np.array([0., 1.]),
                  {'cum_dist_m': np.array([0., 200.]), 'ele': np.array([100., 110.])})
    analysis = analyze_track(track, config)
    html = render_trip_report(analysis)
    assert json.loads(EmbeddedAnalysis(html).payload) == analysis
    assert name not in html
    assert '<script src=' not in html and '<link ' not in html
    assert '/* REPORT_SCRIPT */' not in html and '/* REPORT_STYLE */' not in html


def test_profile_preserves_endpoints_and_midpoints_in_distance_coordinates():
    config = {'sample_distance_m': 100, 'slope_window_m': 100,
              'min_zone_distance_m': 100,
              'bands': [{'name': 'any', 'from_slope_ratio': None}]}
    track = Track('profile', np.array([0., 1.]),
                  {'cum_dist_m': np.array([50., 175.]), 'ele': np.array([100., 105.])})
    profile = analyze_track(track, config)['profile']
    assert [p['distance_m'] for p in profile] == [0, 50, 100, 112.5, 125]
    assert [p['elevation_m'] for p in profile] == pytest.approx([100, 102, 104, 104.5, 105])


def test_cli_embeds_exactly_the_exported_analysis(tmp_path):
    from desnivel.cli.analyze_trip import main

    root = Path(__file__).resolve().parents[2]
    output, report = tmp_path/'nested/analysis.json', tmp_path/'nested/report.html'
    args = ['--gpx', str(root/'gpx/tappa05_Firenze_San_Gimignano.gpx'),
            '--settings', str(root/'settings/desnivel.toml'),
            '--output', str(output), '--html', str(report)]
    assert main(args) == 0
    result = json.loads(output.read_text())
    assert json.loads(EmbeddedAnalysis(report.read_text()).payload) == result
    assert len(result['grouping']['sections']) < len(result['zones'])


def test_cli_rejects_colliding_output_paths_before_writing(tmp_path):
    from desnivel.cli.analyze_trip import main

    output = tmp_path/'same'
    with pytest.raises(SystemExit):
        main(['--gpx', 'unused.gpx', '--settings', 'unused.toml',
              '--output', str(output), '--html', str(output)])
    assert not output.exists()


def test_report_requires_profile_instead_of_inventing_elevation():
    with pytest.raises(ValueError):
        render_trip_report({'version': 1})


def test_timeline_report_and_json_use_same_beat_allocation_without_changing_analysis(tmp_path, capsys):
    from desnivel.cli.analyze_trip import main
    from desnivel.music.timeline import allocate_timeline

    result_path, html = tmp_path/'result.json', tmp_path/'report.html'
    args = ['--gpx', 'gpx/tappa05_Firenze_San_Gimignano.gpx', '--settings', 'settings/desnivel.toml',
            '--output', str(result_path), '--html', str(html)]
    assert main(args) == 0
    original = json.loads(result_path.read_text())
    assert main(args+['--timeline-session', 'presets/organico.json']) == 0
    result = json.loads(result_path.read_text())
    assert {k: v for k, v in result.items() if k != 'timeline'} == original
    assert json.loads(EmbeddedAnalysis(html.read_text()).payload) == result
    distances = [s['end_distance_m']-s['start_distance_m'] for s in result['grouping']['sections']]
    session = json.loads(Path('presets/organico.json').read_text())
    expected = allocate_timeline(distances, window_beats=session['window_beats'], **session['timeline']).to_dict()
    assert {k: result['timeline'][k] for k in expected} == expected
    assert result['timeline']['position']['source_index'] == 0
    assert len(result['timeline']['spans']) == 44
    assert f"{expected['total_beats']:g} effettivi; {expected['total_windows']} finestre" in capsys.readouterr().out


def test_linear_reference_uses_time_instead_of_distance_and_includes_stops():
    from desnivel.cli.analyze_trip import _linear_spans

    track = Track('stops', np.array([0., 1., 2., 4., 10.]),
                  {'cum_dist_m': np.array([0., 0., 100., 100., 200.])})
    sections = [{'start_distance_m': 0, 'end_distance_m': 100},
                {'start_distance_m': 100, 'end_distance_m': 200}]
    spans = _linear_spans(track, sections, 100)
    assert [s['duration_beats'] for s in spans] == [40, 60]
    assert spans[0]['start_beat'] == 0 and spans[-1]['end_beat'] == 100


def test_timeline_reports_extension(tmp_path, capsys):
    from desnivel.cli.analyze_trip import main

    args = ['--gpx', 'gpx/tappa05_Firenze_San_Gimignano.gpx', '--settings', 'settings/desnivel.toml']
    session = tmp_path/'session.json'
    session.write_text(json.dumps({'window_beats': 4,
                                  'timeline': {'target_beats': 4, 'min_windows': 2, 'distance_exponent': .5}}))
    assert main(args+['--timeline-session', str(session)]) == 0
    assert 'minimi garantiti: 4 → 352 beat' in capsys.readouterr().out


def test_pause_context_is_optional_and_preserves_original_grouping(tmp_path):
    from desnivel.cli.analyze_trip import main
    from desnivel.trip.sections import measure_section_bridges

    output, html = tmp_path/'analysis.json', tmp_path/'analysis.html'
    args = ['--gpx', 'gpx/tappa05_Firenze_San_Gimignano.gpx', '--settings', 'settings/desnivel.toml',
            '--output', str(output), '--html', str(html)]
    assert main(args) == 0
    baseline = json.loads(output.read_text())
    assert main(args+['--pause-context', 'ascent', 'level']) == 0
    result = json.loads(output.read_text())
    assert {k: v for k, v in result.items() if k != 'section_context'} == baseline
    assert result['section_context'] == [measure_section_bridges(
        baseline['grouping']['sections'], flank_kind='ascent', middle_kind='level')]
    assert result['section_context'][0]['candidates']
    assert json.loads(EmbeddedAnalysis(html.read_text()).payload) == result
    assert main(args+['--pause-context', 'ascent', 'level', '--pause-context', 'descent', 'level']) == 0
    combined = json.loads(output.read_text())
    assert combined['section_context'] == result['section_context']+[measure_section_bridges(
        baseline['grouping']['sections'], flank_kind='descent', middle_kind='level')]
    assert combined['section_context'][1]['candidates']
    assert {k: v for k, v in combined.items() if k != 'section_context'} == baseline
    assert json.loads(EmbeddedAnalysis(html.read_text()).payload) == combined
    with pytest.raises(SystemExit):
        main(args+['--pause-context', 'missing', 'level'])


def test_pause_context_rejects_unknown_families():
    from desnivel.cli.analyze_trip import main

    with pytest.raises(SystemExit):
        main(['--gpx', 'gpx/tappa05_Firenze_San_Gimignano.gpx',
              '--settings', 'settings/desnivel.toml', '--pause-context', 'missing', 'level'])
