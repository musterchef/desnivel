"""Generazione coordinata dei report e navigazione locale tra tappe."""
import json
from pathlib import Path
import shutil
from html.parser import HTMLParser
from urllib.parse import unquote

import pytest

from desnivel.cli.analyze_trips import main, stage_sources
from desnivel.cli.analyze_trip import analyze_trip
from desnivel.reports.trip import render_trip_index


class IndexLinks(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.options = []
        self.frames = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'option':
            self.options.append(unquote(values['value']))
        elif tag == 'iframe':
            self.frames.append(unquote(values['src']))


def test_collection_has_sorted_working_reports_with_same_analysis_as_single_command(tmp_path):
    sources = tmp_path/'gpx'
    sources.mkdir()
    original = Path('gpx/tappa05_Firenze_San_Gimignano.gpx')
    for name in ['tappa02_due.gpx', 'tappa01_uno.gpx']:
        shutil.copyfile(original, sources/name)
    (sources/'ignore.txt').write_text('non GPX')
    output = tmp_path/'report'
    assert main(['--gpx-dir', str(sources), '--settings', 'settings/desnivel.toml',
                 '--pause-context', 'ascent', 'level',
                 '--pause-context', 'descent', 'level', '--timeline-session', 'presets/organico.json',
                 '--output-dir', str(output)]) == 0
    index = IndexLinks((output/'index.html').read_text())
    assert index.options == ['report-tappa01_uno.html', 'report-tappa02_due.html']
    assert index.frames == [index.options[0]]
    for filename in index.options:
        assert (output/filename).is_file()
        result = json.loads((output/Path(filename).with_suffix('.json')).read_text())
        assert 'timeline' in result
        assert [c['flank_kind'] for c in result['section_context']] == ['ascent', 'descent']
    review = json.loads((output/'segmenti-da-verificare.json').read_text())
    assert len(review['stages']) == 2
    page = (output/'segmenti-da-verificare.html').read_text()
    assert 'Europe/Rome' in page
    for stage in review['stages']:
        for segment in stage['segments']:
            assert f'{stage["stage"]}:{segment["id"]}' in page
    expected = analyze_trip(sources/'tappa01_uno.gpx', Path('settings/desnivel.toml'),
                            pause_context=[['ascent', 'level'], ['descent', 'level']],
                            timeline_session=Path('presets/organico.json'))
    assert json.loads((output/'report-tappa01_uno.json').read_text()) == expected


def test_collection_rejects_empty_directory_without_writing_output(tmp_path, capsys):
    source = tmp_path/'gpx'
    source.mkdir()
    with pytest.raises(SystemExit):
        main(['--gpx-dir', str(source), '--settings', 'settings/desnivel.toml',
              '--output-dir', str(tmp_path/'report')])
    assert 'nessun file GPX' in capsys.readouterr().err
    assert not (tmp_path/'report').exists()


def test_stage_collection_prefers_fit_and_orders_original_strava_names_by_stage(tmp_path):
    names = ['tappa02_trip.gpx', 'tappa01_trip.gpx', 'Da_tappa_2_trip.fit', 'Da_tappa_10_trip.fit']
    for name in names:
        (tmp_path/name).touch()
    assert [p.name for p in stage_sources(tmp_path)] == ['tappa01_trip.gpx', 'Da_tappa_2_trip.fit', 'Da_tappa_10_trip.fit']
    (tmp_path/'other_tappa_2_trip.fit').touch()
    with pytest.raises(ValueError, match='più sorgenti'):
        stage_sources(tmp_path)


def test_index_escapes_labels_and_encodes_local_filenames():
    label = '<script>alert("x")</script>'
    filename = 'report-una tappa#1.html'
    html = render_trip_index([{'label': label, 'filename': filename, 'distance_m': 1000, 'total_beats': 12}])
    assert '12 beat' in html
    assert label not in html
    assert '&lt;script&gt;' in html
    assert 'report-una%20tappa%231.html' in html
    assert IndexLinks(html).options == [filename]
    assert '/* INDEX_SCRIPT */' not in html
    with pytest.raises(ValueError):
        render_trip_index([])
