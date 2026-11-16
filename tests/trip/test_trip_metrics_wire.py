"""Prova end-to-end su socket UDP reale del contratto neutrale.

A differenza di `test_trip_metrics_osc.py` (che usa `FakeOscClient` in
memoria), qui il messaggio attraversa davvero la rete: verifica che
indirizzo e argomenti sopravvivano alla codifica/decodifica OSC, non
solo alla costruzione della schedule in Python.
"""
from __future__ import annotations

from dataclasses import replace
import threading

import numpy as np
import pytest

pytest.importorskip("pythonosc")

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer

from desnivel.settings import DEFAULT_CONFIG
from desnivel.trip.config import Config
from desnivel.sinks.osc import UdpOscClient
from desnivel.sinks.trip_metrics_osc import build_trip_metric_schedule
from desnivel.trip.track import Track
from desnivel.trip.metrics import TRIP_METRIC_ROOT


def _track() -> Track:
    t = np.arange(21, dtype=float) / 10.0
    return Track(
        stage_id="wire",
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


def test_metric_messages_survive_real_udp_round_trip() -> None:
    schedule = build_trip_metric_schedule(_track(), _config())
    assert schedule, "la schedule di prova deve contenere messaggi"

    received: list[tuple[str, tuple]] = []
    dispatcher = Dispatcher()
    dispatcher.map(f"{TRIP_METRIC_ROOT}/*", lambda address, *args: received.append((address, args)))

    server = BlockingOSCUDPServer(("127.0.0.1", 0), dispatcher)
    host, port = server.server_address

    def _serve_expected_messages() -> None:
        for _ in range(len(schedule)):
            server.handle_request()

    server_thread = threading.Thread(target=_serve_expected_messages, daemon=True)
    server_thread.start()

    client = UdpOscClient(host, port)
    for message in schedule:
        client.send_message(message.address, list(message.args))

    server_thread.join(timeout=5.0)
    server.server_close()

    assert not server_thread.is_alive(), "il server non ha ricevuto tutti i messaggi in tempo"
    assert len(received) == len(schedule)

    # Invio sequenziale su un singolo socket loopback: l'ordine di arrivo
    # coincide con l'ordine di invio, quindi confrontiamo posizione per posizione.
    for expected, (address, (elapsed_s, value)) in zip(schedule, received):
        assert address == expected.address
        assert elapsed_s == pytest.approx(expected.args[0])
        assert value == pytest.approx(expected.args[1])
