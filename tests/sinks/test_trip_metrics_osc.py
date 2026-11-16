"""Test del sink OSC neutrale delle metriche viaggio."""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from desnivel.settings import DEFAULT_CONFIG
from desnivel.trip.config import Config
from desnivel.sinks.osc import FakeOscClient
from desnivel.sinks.trip_metrics_osc import (
    TripMetricsOscSink,
    build_trip_metric_schedule,
)
from desnivel.trip.track import Track
from desnivel.trip.metrics import MetricName


def _track(duration_s: float = 2.0) -> Track:
    t = np.arange(int(duration_s * 10.0) + 1, dtype=float) / 10.0
    return Track(
        stage_id="test",
        t=t,
        samples={"cum_dist_m": 5.0 * t, "ele": t},
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


def test_schedule_serializes_elapsed_time_and_metric_value() -> None:
    schedule = build_trip_metric_schedule(_track(), _config())
    speed_messages = [
        message for message in schedule
        if message.address.endswith(f"/{MetricName.SPEED_KMH.value}")
    ]

    assert [message.t for message in speed_messages] == [1.0, 2.0]
    assert speed_messages[0].address == "/desnivel/v1/trip/metric/speed_kmh"
    assert speed_messages[0].args == (1.0, pytest.approx(18.0))


def test_sink_sends_metrics_on_playback_clock() -> None:
    clock = [100.0]
    delays: list[float] = []

    def sleep(delay: float) -> None:
        delays.append(delay)
        clock[0] += delay

    client = FakeOscClient()
    sink = TripMetricsOscSink(
        client=client,
        config=_config(),
        speed=2.0,
        sleep=sleep,
        monotonic=lambda: clock[0],
    )
    sink.emit(_track())

    assert any(address.endswith("/distance_total_m") for address, _ in client.sent)
    assert all(len(args) == 2 for _, args in client.sent)
    assert delays
    assert sum(delays) == pytest.approx(1.0)
