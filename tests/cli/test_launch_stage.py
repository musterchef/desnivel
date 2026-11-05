from pathlib import Path
import json

import pytest

from desnivel.cli import launch_stage
from desnivel.cli.session_config import journey_configuration, resolve_journey


def test_saved_session_reuses_its_journey_without_asking_for_a_stage(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    track = tmp_path/'gpx/viaggio.gpx'
    track.parent.mkdir()
    track.write_text('<gpx/>')
    config = tmp_path/'sessioni/sera.json'
    config.parent.mkdir()
    config.write_text(json.dumps({'journey': journey_configuration(config, track, None, False)}))
    monkeypatch.setattr('builtins.input', lambda prompt: pytest.fail('il viaggio è già salvato'))
    calls = []
    monkeypatch.setattr(launch_stage.ensemble, 'main', lambda args: calls.append(args) or 0)
    assert launch_stage.main(['--config', str(config)]) == 0
    assert '--track' not in calls[0]
    assert 'Viaggio salvato nella sessione' in capsys.readouterr().out
    assert resolve_journey(json.loads(config.read_text()), config)[0] == track


def test_explicit_stage_replaces_a_saved_journey(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = tmp_path/'sessione.json'
    config.write_text(json.dumps({'journey': {'track': 'precedente.gpx'}}))
    track = tmp_path/'gpx/tappa05_test.gpx'
    track.parent.mkdir()
    track.touch()
    calls = []
    monkeypatch.setattr(launch_stage.ensemble, 'main', lambda args: calls.append(args) or 0)
    assert launch_stage.main(['--config', str(config), '--tappa', '05']) == 0
    assert calls[0][calls[0].index('--track')+1] == str(track)


def test_missing_saved_journey_reports_how_to_select_another_file(tmp_path, monkeypatch, capsys):
    config = tmp_path/'sessione.json'
    config.write_text(json.dumps({'journey': {'track': 'spostato.gpx'}}))
    monkeypatch.setattr('builtins.input', lambda prompt: pytest.fail('nessuna sostituzione implicita'))
    with pytest.raises(SystemExit):
        launch_stage.main(['--config', str(config)])
    assert '--tappa 99' in capsys.readouterr().err


def test_journey_paths_and_pause_settings_survive_saving_and_explicit_overrides(tmp_path):
    config = tmp_path/'sessioni/sera.json'
    track, reference = tmp_path/'viaggio.gpx', tmp_path/'orari.fit'
    saved = {'journey': journey_configuration(config, track, reference, True)}
    assert saved['journey']['track'] == '../viaggio.gpx'
    assert resolve_journey(saved, config) == (track, reference, True)
    assert resolve_journey(saved, config, infer_fit_pauses=False) == (track, reference, False)
    other = tmp_path/'altro.fit'
    assert resolve_journey(saved, config, track=other) == (other, None, False)


@pytest.mark.parametrize('journey', [None, {}, {'track': 1}, {'track': ''},
    {'track': 'a.gpx', 'infer_fit_pauses': 'yes'}, {'track': 'a.gpx', 'unexpected': 1}])
def test_invalid_saved_journeys_are_rejected(tmp_path, journey):
    with pytest.raises(ValueError, match='journey'):
        resolve_journey({'journey': journey}, tmp_path/'sessione.json')


def test_picker_lists_multiple_sessions_and_the_existing_single_file(tmp_path):
    directory = tmp_path/'output/sessioni'
    directory.mkdir(parents=True)
    for name in ('ambient.json', 'basso.json', 'ambient.voice-presets.json'):
        (directory/name).write_text('{}')
    previous = tmp_path/'output/sessione.json'
    previous.write_text('{}')
    assert [path.stem for path in launch_stage.saved_sessions(tmp_path)] == ['ambient', 'basso', 'sessione']
    path, create = launch_stage.choose_session(tmp_path, read=lambda prompt: '2')
    assert path == directory/'basso.json'
    assert not create
    assert previous.read_text() == '{}'


def test_new_session_gets_its_own_path_without_overwriting_or_creating_files(tmp_path):
    answers = iter(('0', 'ascolto serale'))
    path, create = launch_stage.choose_session(tmp_path, read=lambda prompt: next(answers))
    assert path == tmp_path/'output/sessioni/ascolto serale.json'
    assert create
    assert not path.exists()


@pytest.mark.parametrize('name', ['', '../altro', '/tmp/altro', '.nascosta', 'a/b', 'a\\b', 'nome.json', 'nome.voice-presets'])
def test_session_names_cannot_escape_the_directory_or_collide_with_preset_libraries(tmp_path, name):
    with pytest.raises(ValueError):
        launch_stage.new_session_path(tmp_path, name)


def test_picker_retries_duplicate_names_and_accepts_cancellation(tmp_path, capsys):
    directory = tmp_path/'output/sessioni'
    directory.mkdir(parents=True)
    (directory/'ambient.json').write_text('{}')
    answers = iter(('0', 'ambient', 'ambient due'))
    path, create = launch_stage.choose_session(tmp_path, read=lambda prompt: next(answers))
    assert path.name == 'ambient due.json' and create
    assert 'esiste già' in capsys.readouterr().out
    assert launch_stage.choose_session(tmp_path, read=lambda prompt: 'q') is None


def test_launcher_passes_selected_session_and_initializes_only_new_sessions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    track = tmp_path/'gpx/tappa05_test.gpx'
    track.parent.mkdir()
    track.write_text('<gpx/>')
    calls = []
    monkeypatch.setattr(launch_stage.ensemble, 'main', lambda args: calls.append(args) or 0)
    answers = iter(('0', 'ambient'))
    monkeypatch.setattr('builtins.input', lambda prompt: next(answers))
    assert launch_stage.main(['--tappa', '05']) == 0
    assert calls[-1][calls[-1].index('--config')+1] == str(tmp_path/'output/sessioni/ambient.json')
    assert '--setup' in calls[-1]
    saved = tmp_path/'output/sessioni/ambient.json'
    saved.parent.mkdir(parents=True)
    saved.write_text('{}')
    monkeypatch.setattr('builtins.input', lambda prompt: '1')
    assert launch_stage.main(['--tappa', '05']) == 0
    assert '--setup' not in calls[-1]


def test_explicit_configuration_bypasses_the_picker_and_does_not_initialize_a_missing_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    track = tmp_path/'gpx/tappa05_test.gpx'
    track.parent.mkdir()
    track.write_text('<gpx/>')
    monkeypatch.setattr('builtins.input', lambda prompt: pytest.fail('nessuna domanda con --config e --tappa'))
    calls = []
    monkeypatch.setattr(launch_stage.ensemble, 'main', lambda args: calls.append(args) or 0)
    assert launch_stage.main(['--tappa', '05', '--config', 'custom.json', '--dry-run']) == 0
    assert calls[0][calls[0].index('--config')+1] == 'custom.json'
    assert '--setup' not in calls[0]
    assert '--dry-run' in calls[0]


def test_session_dialog_opens_a_configuration_outside_the_saved_directory(tmp_path, monkeypatch):
    external = tmp_path/'altra cartella/set serale.json'
    external.parent.mkdir()
    external.write_text('{}')
    monkeypatch.setattr(launch_stage, 'choose_file', lambda prompt, extensions: external)
    assert launch_stage.choose_session(tmp_path, read=lambda prompt: 'a') == (external, False)


def test_cancelled_dialog_returns_to_the_session_menu(tmp_path, monkeypatch):
    monkeypatch.setattr(launch_stage, 'choose_file', lambda *args: None)
    answers = iter(('a', '0', 'nuova sessione'))
    path, create = launch_stage.choose_session(tmp_path, read=lambda prompt: next(answers))
    assert path.name == 'nuova sessione.json' and create


def test_session_dialog_rejects_a_preset_library_without_leaving_the_menu(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(launch_stage, 'choose_file', lambda *args: tmp_path/'ambient.voice-presets.json')
    answers = iter(('a', 'q'))
    assert launch_stage.choose_session(tmp_path, read=lambda prompt: next(answers)) is None
    assert 'non la libreria' in capsys.readouterr().out


def test_native_file_dialog_passes_filter_arguments_and_preserves_spaces(tmp_path, monkeypatch):
    from types import SimpleNamespace
    path = tmp_path/'set serale.json'
    path.write_text('{}')
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout=str(path)+'\n', stderr='')
    monkeypatch.setattr('desnivel.cli.file_dialogs.subprocess.run', run)
    assert launch_stage.choose_file('Apri una sessione Desnivel', ('.json',)) == path
    assert calls[0][-2:] == ['Apri una sessione Desnivel', 'json']
    assert calls[0][:2] == ['osascript', '-e']


def test_native_dialog_cancellation_and_errors_are_distinct(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr('desnivel.cli.file_dialogs.subprocess.run', lambda *a, **k: SimpleNamespace(returncode=0, stdout='', stderr=''))
    assert launch_stage.choose_track() is None
    monkeypatch.setattr('desnivel.cli.file_dialogs.subprocess.run', lambda *a, **k: SimpleNamespace(returncode=1, stdout='', stderr='errore del selettore'))
    with pytest.raises(ValueError, match='errore del selettore'):
        launch_stage.choose_track()
