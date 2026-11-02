import json

import pytest

from desnivel.sinks.voice_wire import voice_packets


@pytest.mark.parametrize('length', [1, 1490, 1500, 3000, 11000])
def test_numeric_osc_packets_preserve_utf8_and_limit_datagrams(length):
    message = {'text': ('à🚲' * length)[:length]}
    payload = json.dumps(message, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    if len(payload) > 12000:
        with pytest.raises(ValueError, match='12000'):
            tuple(voice_packets('/desnivel/v1/voice/message', message, 7, 9))
        return
    packets = tuple(voice_packets('/desnivel/v1/voice/message', message, 7, 9))
    restored = []
    for packet in packets:
        assert len(packet.dgram) <= 8192
        assert all(type(value) is int for value in packet.params)
        if len(payload) > 1500:
            assert packet.params[:5] == [-1, 7, 9, len(restored), len(payload)]
            restored.extend(packet.params[5:])
        else:
            restored.extend(packet.params)
    assert bytes(restored) == payload
    assert json.loads(bytes(restored)) == message


def test_json_limit_is_explicit():
    with pytest.raises(ValueError, match='12000'):
        tuple(voice_packets('/desnivel/v1/voice/message', {'text': 'a' * 12000}, 1, 1))
