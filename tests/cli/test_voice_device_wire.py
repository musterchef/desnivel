import json
import socket

from pythonosc.osc_packet import OscPacket
from pythonosc.udp_client import SimpleUDPClient

from desnivel.adapters.voice_device import CONTROL_ADDRESS, Control, DeviceVoice
from desnivel.cli.voice_device import VoiceDeviceServer
from desnivel.music.phrases import Note, Phrase


def test_device_handshake_and_phrase_over_local_udp():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(('127.0.0.1', 0))
        receiver.settimeout(1)
        port = receiver.getsockname()[1]
        server = VoiceDeviceServer({'part': DeviceVoice(role='melody')}, port=0)
        try:
            client = SimpleUDPClient('127.0.0.1', server.server.server_address[1])
            client.send_message(CONTROL_ADDRESS, list(json.dumps(dict(
                version=1, voice='part', instance='device', serial=1,
                reply_port=port, action='hello')).encode('utf-8')))
            server.server.handle_request()
            packet = OscPacket(receiver.recv(65535)).messages[0].message
            state = json.loads(bytes(packet.params).decode('utf-8'))
            assert state['role'] == 'melody'
            phrase = Phrase(4, (Note(0, 64, 1, 80),))
            server.bridge.destination('part')(8, phrase)
            packet = OscPacket(receiver.recv(65535)).messages[0].message
            plan = json.loads(bytes(packet.params).decode('utf-8'))
            assert plan['voice'] == 'part' and plan['instance'] == 'device'
            assert plan['plan']['start'] == 8
            assert plan['plan']['phrase']['notes'][0]['pitch'] == 64
        finally:
            server.close()


def test_large_adaptive_state_over_real_udp():
    automation = {f'p{i}': dict(base=.5, target=.8, effective=.6, source='adaptive',
                              reason='contesto musicale e densità delle altre voci ' * 4)
                  for i in range(12)}
    voice = DeviceVoice(
        controls={name: Control(0, 1) for name in automation},
        values={name: .6 for name in automation}, apply=lambda values: None,
        read_automation=lambda: automation)
    errors = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(('127.0.0.1', 0))
        receiver.settimeout(1)
        server = VoiceDeviceServer({'part': voice}, port=0, on_error=errors.append)
        try:
            client = SimpleUDPClient('127.0.0.1', server.server.server_address[1])
            client.send_message(CONTROL_ADDRESS, list(json.dumps(dict(
                version=1, voice='part', instance='device', serial=1,
                reply_port=receiver.getsockname()[1], action='hello')).encode('utf-8')))
            server.server.handle_request()
            chunks = {}
            total = None
            identity = None
            while total is None or sum(map(len, chunks.values())) < total:
                datagram = receiver.recv(65535)
                assert len(datagram) <= 8192
                args = OscPacket(datagram).messages[0].message.params
                assert args[0] == -1
                if identity is None:
                    identity = args[1:3]
                    total = args[4]
                assert args[1:3] == identity and args[4] == total
                chunks[args[3]] = args[5:]
            assert total > 9216 / 5  # Il vecchio invio superava il limite UDP di macOS.
            data = bytes(value for offset in sorted(chunks) for value in chunks[offset])
            state = json.loads(data.decode('utf-8'))
            assert not errors
            assert {name: control['automation'] for name, control in state['controls'].items()} == automation
        finally:
            server.close()
