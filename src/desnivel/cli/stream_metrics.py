"""Invia via OSC le metriche neutre derivate da un file GPX."""
from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from desnivel.settings import DEFAULT_CONFIG
from desnivel.trip.loader import load_track
from desnivel.cli.track_source import add_track_arguments
from desnivel.sinks.osc import UdpOscClient
from desnivel.sinks.trip_metrics_osc import (
    TripMetricsOscSink,
    build_trip_metric_schedule,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="desnivel-stream-metrics",
        description="Invia metriche neutrali di una tappa via OSC.",
    )
    add_track_arguments(parser)
    parser.add_argument("--stage", default=None, help="ID tappa; default dal nome GPX.")
    parser.add_argument("--speed", type=float, default=1.0, help="Velocita' di replay.")
    parser.add_argument("--osc-host", default=DEFAULT_CONFIG.osc.host)
    parser.add_argument("--osc-port", type=int, default=DEFAULT_CONFIG.osc.port)
    parser.add_argument("--dry-run", action="store_true", help="Mostra i messaggi senza inviarli.")
    parser.add_argument("--loop", action="store_true", help="Ripeti il replay fino a Ctrl+C.")
    args = parser.parse_args(argv)

    if args.speed <= 0:
        parser.error("--speed deve essere > 0")

    config = replace(
        DEFAULT_CONFIG,
        osc=replace(DEFAULT_CONFIG.osc, host=args.osc_host, port=args.osc_port),
    )
    track = load_track(args.gpx, config=config, stage_id=args.stage, timing_reference=args.timing_reference)
    schedule = build_trip_metric_schedule(track, config)
    source = track.metadata.get("source_path", str(args.gpx))
    print(
        f"[desnivel-stream-metrics] {track.stage_id}: "
        f"durata={track.duration_s:.1f}s, {len(schedule)} messaggi "
        f"a {config.osc.trip_metrics_rate_hz:g} Hz <- {source}",
    )

    if args.dry_run:
        for message in schedule[:5] + schedule[-5:]:
            print(
                f"  t={message.t:7.2f}s {message.address} "
                f"{message.args[1]:.6g}",
            )
        return 0

    client = UdpOscClient(args.osc_host, args.osc_port)
    sink = TripMetricsOscSink(client=client, config=config, speed=args.speed)
    try:
        iteration = 0
        while True:
            iteration += 1
            if args.loop:
                print(f"[desnivel-stream-metrics] giro #{iteration}")
            sink.emit(track)
            if not args.loop:
                break
    except KeyboardInterrupt:
        print("\n[desnivel-stream-metrics] interrotto.")
    print("[desnivel-stream-metrics] fine.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
