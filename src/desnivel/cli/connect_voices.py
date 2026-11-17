"""Richiede il collegamento di tutte le Desnivel_Voice caricate in Live."""
from __future__ import annotations

import argparse

from desnivel.sinks.osc import UdpOscClient

CONNECT_ALL_ADDRESS = '/desnivel/v1/voice/connect-all'


def connect_all(port=None):
    if port is None:
        from desnivel.settings import DEFAULT_SETTINGS
        port = DEFAULT_SETTINGS.transport.session.connect_port
    """Invia la richiesta a una Voice che la distribuisce alle altre in Max."""
    if not 1024 <= port <= 65535:
        raise ValueError('porta richiesta tra 1024 e 65535')
    UdpOscClient('127.0.0.1', port).send_message(CONNECT_ALL_ADDRESS, [])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    from desnivel.settings import DEFAULT_SETTINGS
    parser.add_argument('--port', type=int, default=DEFAULT_SETTINGS.transport.session.connect_port,
                        help='Porta Receive di una Voice caricata in Live.')
    args = parser.parse_args(argv)
    try:
        connect_all(args.port)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(f'Richiesta Collega tutte inviata a 127.0.0.1:{args.port}. '
          'Verifica i collegamenti nella sessione Python o nei device.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
