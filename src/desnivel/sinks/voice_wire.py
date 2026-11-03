"""Pacchetti OSC numerici limitati, con frammentazione dei JSON di voce."""
import json

MAX_JSON_BYTES = 12000
MAX_DATAGRAM_BYTES = 8192
CHUNK_BYTES = 1500
CHUNK_MARKER = -1
CONTROL_CHUNK_BYTES = 900
CONTROL_CHUNK_MARKER = -2
CHUNK_SIZES = {CHUNK_MARKER: CHUNK_BYTES, CONTROL_CHUNK_MARKER: CONTROL_CHUNK_BYTES}


def voice_packets(address, message, stream, serial, *, chunk_bytes=CHUNK_BYTES):
    from pythonosc.osc_message_builder import OscMessageBuilder
    payload = json.dumps(message, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')
    if len(payload) > MAX_JSON_BYTES:
        raise ValueError('messaggio di voce oltre il limite di 12000 byte JSON')
    if chunk_bytes not in CHUNK_SIZES.values():
        raise ValueError('dimensione del frammento OSC non supportata')
    marker = next(key for key, size in CHUNK_SIZES.items() if size == chunk_bytes)
    for offset in range(0, len(payload), chunk_bytes):
        data = list(payload[offset:offset+chunk_bytes])
        args = ([marker, stream, serial, offset, len(payload)]+data
                if len(payload) > chunk_bytes else data)
        builder = OscMessageBuilder(address=address)
        for value in args:
            builder.add_arg(value)
        packet = builder.build()
        if len(packet.dgram) > MAX_DATAGRAM_BYTES:
            raise ValueError('pacchetto OSC di voce oltre il limite di 8192 byte')
        yield packet


class VoiceDecoder:
    """Riassembla lo stesso formato numerico, con memoria e scadenza limitate."""

    def __init__(self, *, clock=None):
        import time
        self.clock = clock or time.monotonic
        self.parts = {}

    def feed(self, data):
        if not data:
            raise ValueError('attesi byte UTF-8 come interi OSC')
        now = self.clock()
        self.parts = {key: part for key, part in self.parts.items() if now-part['created'] <= 1.5}
        if data[0] not in CHUNK_SIZES:
            if len(data) > MAX_JSON_BYTES or any(type(v) is not int or not 0 <= v <= 255 for v in data):
                raise ValueError('byte o lunghezza OSC non validi')
            return bytes(data)
        if len(data) < 6 or any(type(v) is not int for v in data):
            raise ValueError('frammento OSC non valido')
        _, stream, serial, offset, total = data[:5]
        chunk_bytes = CHUNK_SIZES[data[0]]
        payload = data[5:]
        if (not 0 <= stream <= 0x7fffffff or not 0 <= serial <= 0x7fffffff
                or not chunk_bytes < total <= MAX_JSON_BYTES or not 0 <= offset < total
                or offset % chunk_bytes or len(payload) != min(chunk_bytes, total-offset)
                or any(not 0 <= value <= 255 for value in payload)):
            raise ValueError('limiti del frammento OSC non validi')
        key = (stream, serial)
        if key not in self.parts:
            if len(self.parts) >= 8:
                del self.parts[next(iter(self.parts))]
            self.parts[key] = dict(created=now, total=total, chunks={}, chunk_bytes=chunk_bytes)
        part = self.parts[key]
        if part['total'] != total or part['chunk_bytes'] != chunk_bytes:
            del self.parts[key]
            raise ValueError('lunghezza dei frammenti incoerente')
        part['chunks'][offset] = bytes(payload)
        if sum(map(len, part['chunks'].values())) != total:
            return None
        del self.parts[key]
        return b''.join(part['chunks'][offset] for offset in range(0, total, chunk_bytes))
