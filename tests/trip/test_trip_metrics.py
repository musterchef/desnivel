"""Test per l'aggregazione neutrale delle metriche di viaggio."""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from desnivel.settings import DEFAULT_CONFIG
from desnivel.trip.config import Config
from desnivel.trip.track import Track
from desnivel.trip.metrics import MetricName, build_metric_samples


def _track(duration_s: float = 2.0, rate_hz: float = 10.0) -> Track:
    t = np.arange(int(duration_s * rate_hz) + 1, dtype=float) / rate_hz
    return Track(
        stage_id="test",
        t=t,
        samples={
            "cum_dist_m": 5.0 * t,
            "ele": 1.0 * t,
        },
    )


def _config() -> Config:
    return replace(
        DEFAULT_CONFIG,
        osc=replace(DEFAULT_CONFIG.osc, trip_metrics_rate_hz=1.0),
        gpx=replace(
            DEFAULT_CONFIG.gpx,
            speed_reference_kmh=36.0,
            slope_reference=0.2,
            effort_weight_speed=0.4,
            effort_weight_slope=0.6,
        ),
    )


def test_emits_metric_routes_with_relative_time_and_values() -> None:
    samples = build_metric_samples(_track(), _config())
    at_one_second = {
        sample.name: sample.value
        for sample in samples
        if sample.elapsed_s == pytest.approx(1.0)
    }

    assert at_one_second[MetricName.DISTANCE_DELTA_M] == pytest.approx(5.0)
    assert at_one_second[MetricName.DISTANCE_TOTAL_M] == pytest.approx(5.0)
    assert at_one_second[MetricName.ELEVATION_M] == pytest.approx(1.0)
    assert at_one_second[MetricName.SPEED_KMH] == pytest.approx(18.0)
    assert at_one_second[MetricName.SLOPE_RATIO] == pytest.approx(0.2)
    assert at_one_second[MetricName.EFFORT_ESTIMATE] == pytest.approx(0.8)
    assert all(sample.address.startswith("/desnivel/v1/trip/metric/") for sample in samples)


def test_state_metrics_emit_initial_snapshot_but_no_interval_values() -> None:
    samples = build_metric_samples(_track(duration_s=0.0), _config())
    assert {(sample.name, sample.elapsed_s) for sample in samples} == {
        (MetricName.DISTANCE_TOTAL_M, 0.0),
        (MetricName.ELEVATION_M, 0.0),
    }


def test_missing_elevation_omits_elevation_dependent_metrics() -> None:
    track = _track()
    samples = build_metric_samples(
        Track(track.stage_id, track.t, {"cum_dist_m": track.samples["cum_dist_m"]}),
        _config(),
    )
    emitted_names = {sample.name for sample in samples}

    assert MetricName.DISTANCE_TOTAL_M in emitted_names
    assert MetricName.DISTANCE_DELTA_M in emitted_names
    assert MetricName.SPEED_KMH in emitted_names
    assert MetricName.ELEVATION_M not in emitted_names
    assert MetricName.SLOPE_RATIO not in emitted_names
    assert MetricName.EFFORT_ESTIMATE not in emitted_names


def test_zero_distance_interval_reports_zero_speed() -> None:
    track = _track()
    stopped = Track(
        track.stage_id,
        track.t,
        {"cum_dist_m": np.zeros(track.n_samples), "ele": track.samples["ele"]},
    )
    samples = build_metric_samples(stopped, _config())
    interval_one = [sample for sample in samples if sample.elapsed_s == 1.0]

    values = {sample.name: sample.value for sample in interval_one}
    assert values[MetricName.DISTANCE_DELTA_M] == 0.0
    assert values[MetricName.SPEED_KMH] == 0.0
    assert MetricName.SLOPE_RATIO not in values
    assert MetricName.EFFORT_ESTIMATE not in values


def test_non_finite_intervals_are_omitted() -> None:
    track = _track()
    elevation = track.samples["ele"].copy()
    elevation[5] = np.nan
    samples = build_metric_samples(
        Track(track.stage_id, track.t, {
            "cum_dist_m": track.samples["cum_dist_m"],
            "ele": elevation,
        }),
        _config(),
    )

    assert all(np.isfinite(sample.value) for sample in samples)
    assert any(
        sample.elapsed_s == 1.0 and sample.name is MetricName.ELEVATION_M
        for sample in samples
    )
    assert not any(
        sample.elapsed_s == 1.0
        and sample.name in {MetricName.SLOPE_RATIO, MetricName.EFFORT_ESTIMATE}
        for sample in samples
    )
