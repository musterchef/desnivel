"""Sink OSC per il contratto neutrale delle metriche di viaggio."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from ..settings import DEFAULT_CONFIG
from ..trip.config import Config
from ..trip.track import Track
from ..trip.metrics import build_metric_samples
from .osc import OscClient
from .schedule import ScheduledMessage, play_schedule


def build_trip_metric_schedule(
    track: Track,
    config: Config = DEFAULT_CONFIG,
) -> list[ScheduledMessage]:
    """Serializza le metriche neutre come `(elapsed_s, value)` su OSC."""
    return [
        ScheduledMessage(
            t=sample.elapsed_s,
            address=sample.address,
            args=(sample.elapsed_s, sample.value),
        )
        for sample in build_metric_samples(track, config)
    ]


@dataclass
class TripMetricsOscSink:
    """Riproduce le metriche di un Track direttamente via OSC."""

    client: OscClient
    config: Config = DEFAULT_CONFIG
    speed: float = 1.0
    sleep: Any = staticmethod(time.sleep)
    monotonic: Any = staticmethod(time.monotonic)

    def emit(self, track: Track) -> None:
        play_schedule(
            build_trip_metric_schedule(track, self.config),
            self.client,
            self.speed,
            sleep=self.sleep,
            monotonic=self.monotonic,
        )


__all__ = [
    "TripMetricsOscSink",
    "build_trip_metric_schedule",
]
