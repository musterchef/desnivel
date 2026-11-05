import json
import socket

from pythonosc.osc_packet import OscPacket
from pythonosc.udp_client import SimpleUDPClient

from desnivel.adapters.voice_device import CONTROL_ADDRESS, DeviceVoice
from desnivel.cli.voice_device import VoiceDeviceServer
from desnivel.sinks.voice_wire import voice_packets, VoiceDecoder


def test_discovery_binding_and_handshake_share_the_server_without_starting_music():
    observed = []
    server = VoiceDeviceServer({}, 0, on_message=lambda bridge, message: observed.append(message))
    server.server.timeout = .5
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(('127.0.0.1', 0))
            receiver.settimeout(1)
            client = SimpleUDPClient('127.0.0.1', server.server.server_address[1])
            message = dict(version=1, action='discover', device_id='endpoint', instance='device',
                           reply_port=receiver.getsockname()[1], device_kind='voice',
                           track=dict(name='synth', index=0, id=42))
            for packet in voice_packets(CONTROL_ADDRESS, message, 1, 1):
                client.send(packet)
                server.server.handle_request()
            assert not server.bridge.voices and not observed
            assert server.devices.find('endpoint')['track']['name'] == 'synth'
            server.bridge.voices['melody'] = DeviceVoice()
            server.bridge.bindings = {'melody': 'endpoint'}
            server.devices.bind('endpoint', 'melody', 9006)
            decoder = VoiceDecoder()
            packet = OscPacket(receiver.recv(65535)).messages[0].message
            binding = json.loads(decoder.feed(packet.params))
            assert binding['kind'] == 'binding' and binding['voice'] == 'melody'
            hello = dict(version=1, action='hello', device_id='endpoint', instance='device',
                         reply_port=message['reply_port'], voice='melody', serial=1)
            for packet in voice_packets(CONTROL_ADDRESS, hello, 1, 2):
                client.send(packet)
                server.server.handle_request()
            packet = OscPacket(receiver.recv(65535)).messages[0].message
            state = json.loads(decoder.feed(packet.params))
            assert state['kind'] == 'state'
            assert server.bridge.connected('melody')
            assert len(observed) == 1
    finally:
        server.close()
