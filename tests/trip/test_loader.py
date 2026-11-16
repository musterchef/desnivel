"""Test del loader GPX."""
from __future__ import annotations

from pathlib import Path
from dataclasses import replace

import numpy as np
import pytest

from desnivel.settings import DEFAULT_CONFIG
from desnivel.trip.loader import load_track
from desnivel.trip.loader._derive import derive_channels
from desnivel.trip.loader._parse import parse_gpx_points, stage_id_from_path
from desnivel.trip.loader._resample import resample_to_uniform_grid


def _make_minimal_gpx(tmp_path: Path) -> Path:
    """Crea un GPX sintetico con 3 punti, 60s di intervallo, salita lieve."""
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1">
  <trk><trkseg>
    <trkpt lat="45.0700" lon="7.6800"><ele>200.0</ele><time>2026-04-12T08:00:00Z</time></trkpt>
    <trkpt lat="45.0710" lon="7.6810"><ele>205.0</ele><time>2026-04-12T08:01:00Z</time></trkpt>
    <trkpt lat="45.0720" lon="7.6820"><ele>210.0</ele><time>2026-04-12T08:02:00Z</time></trkpt>
  </trkseg></trk>
</gpx>"""
    path = tmp_path / "tappa99_test.gpx"
    path.write_text(xml)
    return path


def _make_gpx_without_elevation(tmp_path: Path) -> Path:
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1">
    <trk><trkseg>
        <trkpt lat="45.0700" lon="7.6800"><time>2026-04-12T08:00:00Z</time></trkpt>
        <trkpt lat="45.0710" lon="7.6810"><time>2026-04-12T08:01:00Z</time></trkpt>
        <trkpt lat="45.0720" lon="7.6820"><time>2026-04-12T08:02:00Z</time></trkpt>
    </trkseg></trk>
</gpx>"""
        path = tmp_path / "tappa99_no_elevation.gpx"
        path.write_text(xml)
        return path


def test_parse_gpx_basic(tmp_path: Path) -> None:
    raw = parse_gpx_points(_make_minimal_gpx(tmp_path))
    assert raw["lat"].shape == (3,)
    assert np.allclose(raw["lat"], [45.07, 45.071, 45.072])
    assert raw["t_unix"][1] - raw["t_unix"][0] == pytest.approx(60.0)


def test_missing_elevation_is_not_parsed_as_sea_level(tmp_path: Path) -> None:
    raw = parse_gpx_points(_make_gpx_without_elevation(tmp_path))
    assert np.isnan(raw["ele"]).all()


def test_stage_id_from_path() -> None:
    assert stage_id_from_path("gpx/tappa01_Torino_Genova.gpx") == "tappa_01"
    assert stage_id_from_path("gpx/tappa12_X.gpx") == "tappa_12"
    assert stage_id_from_path("foo_bar.gpx") == "foo_bar"


def test_derive_channels_produces_expected_keys(tmp_path: Path) -> None:
    raw = parse_gpx_points(_make_minimal_gpx(tmp_path))
    derived = derive_channels(raw, DEFAULT_CONFIG.gpx)
    assert {"lat", "lon", "ele", "elapsed_s", "dist_m", "cum_dist_m",
            "speed_kmh", "slope", "effort"} <= set(derived.keys())
    n = raw["lat"].size
    for key, arr in derived.items():
        assert arr.shape == (n,), f"{key} ha shape {arr.shape}"


def test_derive_speed_and_slope_signs(tmp_path: Path) -> None:
    raw = parse_gpx_points(_make_minimal_gpx(tmp_path))
    derived = derive_channels(raw, DEFAULT_CONFIG.gpx)
    # Punti distanti circa 130 m in 60 s → ~7.8 km/h. Verifichiamo che sia
    # nel range plausibile.
    assert derived["speed_kmh"][1] > 0
    assert derived["speed_kmh"][1] < 50
    # Salita lieve → slope positivo.
    assert derived["slope"][1] > 0
    # Effort è in [0, 1].
    assert derived["effort"].min() >= 0.0
    assert derived["effort"].max() <= 1.0


def test_partial_missing_elevation_is_interpolated() -> None:
    raw = {
        "lat": np.array([45.0, 45.001, 45.002]),
        "lon": np.array([7.0, 7.001, 7.002]),
        "ele": np.array([100.0, np.nan, 120.0]),
        "t_unix": np.array([0.0, 60.0, 120.0]),
    }
    derived = derive_channels(raw, DEFAULT_CONFIG.gpx)
    assert derived["ele"][1] == pytest.approx(110.0)


def test_resample_uniform_grid_preserves_endpoints() -> None:
    src_t = np.array([0.0, 30.0, 60.0])
    channels = {"x": np.array([10.0, 20.0, 30.0])}
    t, out = resample_to_uniform_grid(src_t, channels, rate_hz=10.0)
    assert t[0] == 0.0
    assert t[-1] == pytest.approx(60.0, abs=0.1)
    # Lineare, quindi al centro deve fare ~20.
    mid = int(len(t) // 2)
    assert out["x"][mid] == pytest.approx(20.0, abs=0.5)


def test_load_track_end_to_end(tmp_path: Path) -> None:
    gpx = _make_minimal_gpx(tmp_path)
    # La fixture rappresenta un dispositivo che registra ogni 60 secondi.
    config = replace(DEFAULT_CONFIG, gpx=replace(DEFAULT_CONFIG.gpx, recording_gap_s=120))
    track = load_track(gpx, config)
    rate = DEFAULT_CONFIG.timing.internal_rate_hz
    # 120 s totali, griglia a 10 Hz → 1201 campioni.
    assert track.n_samples == int(120 * rate) + 1
    assert track.duration_s == pytest.approx(120.0, abs=1.0 / rate)
    assert track.stage_id == "tappa_99"
    # Canali essenziali presenti.
    for key in ("speed_kmh", "slope", "effort", "ele"):
        assert key in track.samples
    assert track.metadata["source_path"].endswith("tappa99_test.gpx")


def test_track_without_elevation_omits_elevation_dependent_channels(
    tmp_path: Path,
) -> None:
    config = replace(DEFAULT_CONFIG, gpx=replace(DEFAULT_CONFIG.gpx, recording_gap_s=120))
    track = load_track(_make_gpx_without_elevation(tmp_path), config)
    assert "ele" not in track.samples
    assert "slope" not in track.samples
    assert "effort" not in track.samples
    assert "speed_kmh" in track.samples
    assert "cum_dist_m" in track.samples
