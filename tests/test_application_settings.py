import pytest

from desnivel.settings import load_settings


VALID = """
[trip.route_structure]
merge_reversals = true
max_relative_elevation = 0.2
max_relative_distance = 0.2
max_reversal_distance_m = 400.0
min_recovery_ratio = 1.0
"""


def test_visible_toml_settings_are_loaded_into_typed_values(tmp_path):
    path = tmp_path/'desnivel.toml'
    path.write_text(VALID)
    settings = load_settings(path).route_structure
    assert settings.merge_reversals
    assert settings.max_reversal_distance_m == 400


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
