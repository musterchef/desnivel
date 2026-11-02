"""Pacchetti OSC numerici limitati, con frammentazione dei JSON di voce."""
import json

MAX_JSON_BYTES = 12000
MAX_DATAGRAM_BYTES = 8192
CHUNK_BYTES = 1500
CHUNK_MARKER = -1


def voice_packets(address, message, stream, serial):
    from pythonosc.osc_message_builder import OscMessageBuilder
    payload = json.dumps(message, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')
    if len(payload) > MAX_JSON_BYTES:
        raise ValueError('messaggio di voce oltre il limite di 12000 byte JSON')
    for offset in range(0, len(payload), CHUNK_BYTES):
        data = list(payload[offset:offset+CHUNK_BYTES])
        args = ([CHUNK_MARKER, stream, serial, offset, len(payload)]+data
                if len(payload) > CHUNK_BYTES else data)
        builder = OscMessageBuilder(address=address)
        for value in args:
            builder.add_arg(value)
        packet = builder.build()
        if len(packet.dgram) > MAX_DATAGRAM_BYTES:
            raise ValueError('pacchetto OSC di voce oltre il limite di 8192 byte')
        yield packet
