"""Server HTTP locale: risorse della vista, geometria e snapshot su file."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json
import os
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Thread
import time
from urllib.parse import urlsplit

from desnivel.viewer.route import route_payload
from desnivel.cli.session_commands import validate_command


class JourneyViewServer:
    """Legge lo stato su file e accoda comandi, senza accedere al runtime."""

    def __init__(self, track, status_path, port):
        route = json.dumps(route_payload(track), allow_nan=False).encode('utf-8')
        status_path = Path(status_path)
        commands = self.commands = Queue(maxsize=16)
        assets = files('desnivel.viewer')
        resources = {'/': ('index.html', 'text/html; charset=utf-8'),
                     '/view.css': ('view.css', 'text/css; charset=utf-8'),
                     '/view.js': ('view.js', 'text/javascript; charset=utf-8'),
                     '/music.js': ('music.js', 'text/javascript; charset=utf-8'),
                     '/position.js': ('position.js', 'text/javascript; charset=utf-8')}
        resources.update({'/theme.css': ('theme.css', 'text/css; charset=utf-8'),
                          '/skin.js': ('skin.js', 'text/javascript; charset=utf-8'),
                          '/session/': ('session.html', 'text/html; charset=utf-8'),
                          '/session.css': ('session.css', 'text/css; charset=utf-8'),
                          '/session.js': ('session.js', 'text/javascript; charset=utf-8')})

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path != '/api/control':
                    self.respond(404, b'Not found', 'text/plain')
                    return
                origin = f'http://127.0.0.1:{self.server.server_port}'
                if self.headers.get('Origin') != origin:
                    self.respond(403, b'Origin not allowed', 'text/plain')
                    return
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 4096:
                        raise ValueError('dimensione del comando non valida')
                    payload = json.loads(self.rfile.read(size))
                    commands.put_nowait(validate_command(payload))
                except (ValueError, Full) as error:
                    self.respond(400, json.dumps({'error': str(error) or 'coda piena'}).encode(), 'application/json')
                    return
                self.respond(202, b'{"queued":true}', 'application/json')

            def do_GET(self):
                path = urlsplit(self.path).path
                if path == '/api/route':
                    self.respond(200, route, 'application/json')
                elif path == '/api/state':
                    try:
                        # fstat sul file aperto: età e contenuto dello stesso snapshot atomico.
                        with status_path.open(encoding='utf-8') as stream:
                            state = json.load(stream)
                            age = max(0., time.time()-os.fstat(stream.fileno()).st_mtime)
                        body = json.dumps({'age_s': age, 'session': state}, allow_nan=False).encode('utf-8')
                    except (OSError, ValueError) as error:
                        body = json.dumps({'error': f'Stato non disponibile: {error}'}).encode('utf-8')
                        self.respond(503, body, 'application/json')
                        return
                    self.respond(200, body, 'application/json')
                elif path in resources:
                    filename, content_type = resources[path]
                    self.respond(200, assets.joinpath(filename).read_bytes(), content_type)
                else:
                    self.respond(404, b'Not found', 'text/plain')

            def respond(self, status, body, content_type):
                self.send_response(status)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # Il browser ha chiuso la richiesta.

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
        self.thread = Thread(target=self.server.serve_forever, name='journey-view', daemon=True)

    @property
    def url(self):
        return f'http://127.0.0.1:{self.server.server_port}/'

    def start(self):
        self.thread.start()

    def take_commands(self):
        """Consuma i comandi nel ciclo proprietario del runtime."""
        while True:
            try:
                yield self.commands.get_nowait()
            except Empty:
                return

    def close(self):
        if self.thread.is_alive():
            self.server.shutdown()
            self.thread.join()
        self.server.server_close()
