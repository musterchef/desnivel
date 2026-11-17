import pytest
from pathlib import Path

from desnivel.settings import load_settings


VALID = Path('settings/desnivel.toml').read_text(encoding='utf-8')


def test_visible_toml_settings_are_loaded_into_typed_values(tmp_path):
    path = tmp_path/'desnivel.toml'
    path.write_text(VALID)
    settings = load_settings(path).trip.route_structure
    assert settings.merge_reversals
    assert settings.max_reversal_distance_m == 400


def test_analysis_bands_restore_the_open_lower_bound_from_toml(tmp_path):
    path = tmp_path/'desnivel.toml'
    path.write_text(VALID)
    analysis = load_settings(path).trip.analysis.as_dict()
    assert analysis['bands'][0] == {
        'name': 'steep_descent', 'from_slope_ratio': None}
    assert analysis['bands'][-1]['from_slope_ratio'] == .06
    assert load_settings(path).trip.grouping.as_dict()['families']['ascent'] == [
        'climb', 'steep_climb']


def test_toml_values_build_the_loader_and_transport_config(tmp_path):
    path = tmp_path/'desnivel.toml'
    path.write_text(VALID.replace('max_speed_kmh = 70.0', 'max_speed_kmh = 65.0')
                    .replace('port = 9000', 'port = 9010'))
    config = load_settings(path).config
    assert config.gpx.max_speed_kmh == 65
    assert config.osc.port == 9010


@pytest.mark.parametrize('content', [
    '[trip]\nunexpected = 1\n',
    VALID.replace('max_relative_distance = 0.2\n', ''),
    VALID.replace('max_relative_elevation = 0.2', 'max_relative_elevation = 1.0'),
])
def test_missing_unknown_or_invalid_settings_fail_explicitly(tmp_path, content):
    path = tmp_path/'desnivel.toml'
    path.write_text(content)
    with pytest.raises(ValueError):
        load_settings(path)
