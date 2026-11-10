import pytest

from desnivel.music.patterns import scale_notes


def test_scale_is_independent_of_device_range():
    assert scale_notes('pentatonic_minor', 33, 6) == [33, 36, 38, 40, 43, 45]
    assert scale_notes('major', 80, 4) == [80, 82, 84, 85]
    with pytest.raises(ValueError):
        scale_notes('nope', 0)
