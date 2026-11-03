"""Richiede la preparazione o il controllo della registrazione alla sessione locale."""
import argparse
import json
from urllib.error import URLError
from urllib.request import Request, urlopen


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('audio', 'midi', 'both', 'start', 'stop'))
    parser.add_argument('--view-port', type=int, default=8765)
    args = parser.parse_args(argv)
    if not 1024 <= args.view_port <= 65535:
        parser.error('porta richiesta tra 1024 e 65535')
    origin = f'http://127.0.0.1:{args.view_port}'
    request = Request(origin+'/api/control',
                      data=json.dumps({'action': 'record_'+args.action}).encode(),
                      headers={'Content-Type': 'application/json', 'Origin': origin})
    try:
        with urlopen(request, timeout=4) as response:
            if response.status != 202:
                raise ValueError(f'risposta inattesa: {response.status}')
    except (URLError, ValueError) as error:
        parser.exit(1, f'Registrazione: {error}. Avviare la sessione con --view-port {args.view_port}.\n')
    print('Richiesta inviata. Esito nel terminale della sessione e nella dashboard.')


if __name__ == '__main__':
    main()
