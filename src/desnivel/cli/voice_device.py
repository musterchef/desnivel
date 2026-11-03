"""Ricevitore del dispositivo comune; prova opzionale con una frase da file."""
from __future__ import annotations

import argparse
import json
import math
import select
from pathlib import Path
from uuid import uuid4

from desnivel.adapters.voice_device import ADDRESS, CONTROL_ADDRESS, DeviceVoice, VoiceDeviceBridge
from desnivel.music.phrases import Phrase
from desnivel.sinks.voice_wire import voice_packets, VoiceDecoder


class VoiceDeviceServer:
    """Server locale da usare nel thread che governa la sessione musicale."""

    def __init__(self, voices, port=9006, on_message=None, on_error=None):
        from pythonosc.dispatcher import Dispatcher
        from pythonosc.osc_server import BlockingOSCUDPServer
        from pythonosc.udp_client import SimpleUDPClient
        self.clients = {}
        self.on_message = on_message
        self.on_error = on_error
        self._wire_stream = uuid4().int & 0x7fffffff
        self._wire_serial = 0
        self._decoder = VoiceDecoder()

        def send(port, address, message):
            self._wire_serial = self._wire_serial % 0x7fffffff+1
            packets = tuple(voice_packets(address, message, self._wire_stream, self._wire_serial))
            if port not in self.clients:
                self.clients[port] = SimpleUDPClient('127.0.0.1', port)
            for packet in packets:
                self.clients[port].send(packet)

        self.bridge = VoiceDeviceBridge(voices, send)
        dispatcher = Dispatcher()
        dispatcher.map(CONTROL_ADDRESS, self._receive)
        self.server = BlockingOSCUDPServer(('127.0.0.1', port), dispatcher)

    def _receive(self, address, *args):
        message = None
        try:
            payload = self._decoder.feed(args)
            if payload is None:
                return
            message = json.loads(payload.decode('utf-8'))
            if not isinstance(message, dict):
                raise ValueError('atteso un oggetto JSON')
            self.bridge.handle(message)
            if self.on_message:
                self.on_message(self.bridge, message)
        except (ValueError, KeyError, TypeError, OverflowError, OSError) as error:
            if isinstance(message, dict):
                self.bridge.error(message, error)
            if self.on_error:
                self.on_error(str(error))
            else:
                print(f'Voice device: {error}', flush=True)

    def poll(self, limit=64):
        """Consuma richieste già disponibili senza bloccare il ciclo chiamante."""
        for _ in range(limit):
            if not select.select([self.server], [], [], 0)[0]:
                break
            self.server.handle_request()

    def close(self):
        for voice in list(self.bridge.connections):
            try:
                self.bridge.reset(voice)
            except ValueError:
                pass  # Il dispositivo scaduto esegue già il proprio Panic.
        self.server.server_close()

    def serve_forever(self):
        self.server.serve_forever()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--voice', action='append', required=True, help='Identificativo ammesso; ripetibile.')
    parser.add_argument('--port', type=int, default=9006)
    parser.add_argument('--phrase', type=Path, help='Prova di esecuzione: invia questa frase una volta per avvio del trasporto.')
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error('porta richiesta tra 1024 e 65535')
    if args.phrase and len(args.voice) != 1:
        parser.error('--phrase richiede una sola --voice')
    phrase = Phrase.from_dict(json.loads(args.phrase.read_text())) if args.phrase else None
    sent_epochs = {}

    def audition(bridge, message):
        if phrase is None or message['action'] != 'hello':
            return
        transport = message.get('transport', {})
        beat = transport.get('beat')
        if type(beat) not in (int, float) or not math.isfinite(beat) or beat < 0:
            raise ValueError('posizione del trasporto non valida')
        key = (message['instance'], transport.get('epoch'))
        if transport.get('playing') and sent_epochs.get(message['voice']) != key:
            start = math.ceil((beat + 2) / 4) * 4
            bridge.destination(message['voice'])(start, phrase)
            sent_epochs[message['voice']] = key
            print(f"Frase di prova inviata a {message['voice']} dal beat {start:g}", flush=True)

    server = VoiceDeviceServer({name: DeviceVoice() for name in args.voice}, args.port, audition)
    print(f"Python pronto su 127.0.0.1:{args.port}; parti: {', '.join(args.voice)}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
