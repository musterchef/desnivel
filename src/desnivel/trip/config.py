"""Configurazione del caricamento FIT/GPX e del trasporto delle metriche."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TimingConfig:
    """Tempi e frequenze di base della pipeline."""

    internal_rate_hz: float
    """Frequenza di ricampionamento interno (Hz)."""


@dataclass(frozen=True)
class OscConfig:
    """Parametri di trasporto OSC."""

    host: str
    port: int
    trip_metrics_rate_hz: float
    """Frequenza del contratto neutrale delle metriche viaggio."""


@dataclass(frozen=True)
class GpxConfig:
    """Criteri comuni per i dati GPS e la derivazione delle metriche FIT/GPX."""

    # Velocità di riferimento (km/h) per normalizzare la componente di sforzo
    # legata al moto. Sopra questa soglia la componente satura.
    speed_reference_kmh: float
    # Pendenza positiva di riferimento (frazione, es. 0.10 = 10%) per
    # normalizzare la componente di sforzo legata alla salita.
    slope_reference: float
    # Pesi della formula di effort = w_speed * speed_norm + w_slope * slope_pos_norm.
    # Devono sommare a 1 per restare nel range [0, 1].
    effort_weight_speed: float
    effort_weight_slope: float
    # Filtraggio leggero del raw GPX (mediana mobile in numero di campioni).
    raw_median_window: int
    # Esclusione conservativa di brevi deviazioni della posizione GPS.
    max_speed_kmh: float
    spike_max_removed_points: int
    spike_max_gap_s: float
    spike_min_detour_ratio: float
    recording_gap_s: float
    stop_min_duration_s: float
    stop_radius_m: float
    # Pause brevi: intervallo anomalo rispetto alla cadenza e basso spostamento.
    pause_min_gap_s: float
    pause_gap_factor: float
    pause_max_speed_kmh: float


@dataclass(frozen=True)
class Config:
    """Configurazione del producer GPX."""

    timing: TimingConfig
    gpx: GpxConfig
    osc: OscConfig
