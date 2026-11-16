"""Metriche di viaggio esportabili senza interpretazione musicale."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

from desnivel.settings import DEFAULT_CONFIG

from .config import Config
from .track import Track


TRIP_METRIC_ROOT = "/desnivel/v1/trip/metric"


class MetricName(str, Enum):
    """Campi del pilot neutrale, distinti da parametri audio/visuali."""

    DISTANCE_DELTA_M = "distance_delta_m"
    DISTANCE_TOTAL_M = "distance_total_m"
    ELEVATION_M = "elevation_m"
    SPEED_KMH = "speed_kmh"
    SLOPE_RATIO = "slope_ratio"
    EFFORT_ESTIMATE = "effort_estimate"


@dataclass(frozen=True)
class MetricSpec:
    name: MetricName
    unit: str
    description: str


METRIC_SPECS: tuple[MetricSpec, ...] = (
    MetricSpec(MetricName.DISTANCE_DELTA_M, "m", "Distanza nell'intervallo"),
    MetricSpec(MetricName.DISTANCE_TOTAL_M, "m", "Distanza cumulata"),
    MetricSpec(MetricName.ELEVATION_M, "m", "Quota filtrata"),
    MetricSpec(MetricName.SPEED_KMH, "km/h", "Velocita' media nell'intervallo"),
    MetricSpec(MetricName.SLOPE_RATIO, "ratio", "Pendenza nell'intervallo"),
    MetricSpec(
        MetricName.EFFORT_ESTIMATE,
        "[0, 1]",
        "Stima composita configurata, non misura fisiologica",
    ),
)


@dataclass(frozen=True)
class MetricSample:
    elapsed_s: float
    name: MetricName
    value: float

    @property
    def address(self) -> str:
        return f"{TRIP_METRIC_ROOT}/{self.name.value}"


def build_metric_samples(
    track: Track,
    config: Config = DEFAULT_CONFIG,
) -> tuple[MetricSample, ...]:
    """Aggrega il Track sulla griglia OSC e restituisce solo valori finiti.

    Le misure di stato sono campionate agli estremi. Distanza, velocita',
    pendenza e stima effort descrivono ciascuna finestra completa.
    """
    if track.n_samples == 0:
        return ()

    rate_hz = config.osc.trip_metrics_rate_hz
    if rate_hz <= 0:
        raise ValueError("trip_metrics_rate_hz deve essere positivo")

    elapsed = np.asarray(track.t, dtype=float) - float(track.t[0])
    duration = float(elapsed[-1])
    period_s = 1.0 / rate_hz
    complete_intervals = int(np.floor(duration * rate_hz))
    ticks = np.arange(complete_intervals + 1, dtype=float) * period_s

    cumulative = track.samples.get("cum_dist_m")
    elevation = track.samples.get("ele")
    if cumulative is not None:
        cumulative = np.asarray(cumulative, dtype=float)
    if elevation is not None:
        elevation = np.asarray(elevation, dtype=float)

    samples: list[MetricSample] = []
    unavailable_motion = np.zeros(max(0, ticks.size-1), dtype=bool)
    for start, end in track.metadata.get('unavailable_motion_intervals', ()):
        first = np.searchsorted(ticks, start, side='right' if end > start else 'left')-1
        last = np.searchsorted(ticks, end, side='left' if end > start else 'right')
        unavailable_motion[max(0, first):min(last, unavailable_motion.size)] = True
    for segment in track.segments[1:]:
        boundary = track.t[segment.start]-track.t[0]
        # Finestre a cavallo della giunzione non descrivono un tratto osservato.
        unavailable_motion |= (ticks[:-1] < boundary) & (ticks[1:] > boundary)

    for tick in ticks:
        if cumulative is not None:
            total = _sample_at(elapsed, cumulative, float(tick))
            _append_if_finite(samples, tick, MetricName.DISTANCE_TOTAL_M, total)
        if elevation is not None:
            height = _sample_at(elapsed, elevation, float(tick))
            _append_if_finite(samples, tick, MetricName.ELEVATION_M, height)

    for interval_index in range(1, ticks.size):
        interval_end = float(ticks[interval_index])
        interval_start = float(ticks[interval_index - 1])
        interval_duration = interval_end - interval_start
        if unavailable_motion[interval_index-1]:
            continue
        distance_delta = _interval_delta(elapsed, cumulative, interval_start, interval_end)
        _append_if_finite(
            samples, interval_end, MetricName.DISTANCE_DELTA_M, distance_delta,
        )

        if not np.isfinite(distance_delta) or distance_delta < 0:
            continue

        speed_kmh = distance_delta / interval_duration * 3.6
        _append_if_finite(samples, interval_end, MetricName.SPEED_KMH, speed_kmh)
        if distance_delta == 0:
            continue

        elevation_delta = _interval_delta(elapsed, elevation, interval_start, interval_end)
        if not np.isfinite(elevation_delta):
            continue
        slope_ratio = elevation_delta / distance_delta
        _append_if_finite(samples, interval_end, MetricName.SLOPE_RATIO, slope_ratio)

        effort = _effort_estimate(speed_kmh, slope_ratio, config)
        _append_if_finite(samples, interval_end, MetricName.EFFORT_ESTIMATE, effort)

    samples.sort(key=lambda sample: (sample.elapsed_s, sample.address))
    return tuple(samples)


def _sample_at(times: np.ndarray, values: np.ndarray, target_s: float) -> float:
    """Interpolate only between finite endpoints; never bridge a missing gap."""
    if values.size != times.size or values.size == 0:
        return float("nan")
    right = int(np.searchsorted(times, target_s, side="left"))
    if right < times.size and times[right] == target_s:
        return float(values[right])
    if right == 0 or right >= times.size:
        return float("nan")
    left = right - 1
    if not (np.isfinite(values[left]) and np.isfinite(values[right])):
        return float("nan")
    fraction = (target_s - times[left]) / (times[right] - times[left])
    return float(values[left] + fraction * (values[right] - values[left]))


def _interval_delta(
    times: np.ndarray,
    values: np.ndarray | None,
    start_s: float,
    end_s: float,
) -> float:
    if values is None:
        return float("nan")
    interior = (times > start_s) & (times < end_s)
    if not np.isfinite(values[interior]).all():
        return float("nan")
    # Alla giunzione due estremi osservati hanno lo stesso tempo attivo:
    # l'inizio legge il tratto entrante, la fine quello uscente.
    first = int(np.searchsorted(times, start_s, side='right'))-1
    start = float(values[first]) if first >= 0 and times[first] == start_s else _sample_at(times, values, start_s)
    end = _sample_at(times, values, end_s)
    if not (np.isfinite(start) and np.isfinite(end)):
        return float("nan")
    return end - start


def _effort_estimate(speed_kmh: float, slope_ratio: float, config: Config) -> float:
    cfg = config.gpx
    speed_norm = np.clip(speed_kmh / cfg.speed_reference_kmh, 0.0, 1.0)
    slope_norm = np.clip(max(slope_ratio, 0.0) / cfg.slope_reference, 0.0, 1.0)
    return float(np.clip(
        cfg.effort_weight_speed * speed_norm
        + cfg.effort_weight_slope * slope_norm,
        0.0,
        1.0,
    ))


def _append_if_finite(
    samples: list[MetricSample],
    elapsed_s: float,
    name: MetricName,
    value: float,
) -> None:
    if np.isfinite(value):
        samples.append(MetricSample(float(elapsed_s), name, float(value)))


__all__ = [
    "TRIP_METRIC_ROOT",
    "MetricName",
    "MetricSpec",
    "METRIC_SPECS",
    "MetricSample",
    "build_metric_samples",
]
