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


def test_decoder_handles_reordered_duplicates_and_keeps_streams_separate():
    from desnivel.sinks.voice_wire import VoiceDecoder
    decoder=VoiceDecoder(clock=lambda:0.)
    message={'telemetry':'à'*2000}
    frames=[p.params for p in voice_packets('/control',message,7,1)]
    assert decoder.feed(frames[-1]) is None
    assert decoder.feed(frames[-1]) is None
    other=[p.params for p in voice_packets('/control',message,8,1)]
    assert decoder.feed(other[0]) is None
    restored=None
    for frame in frames[:-1]:
        restored=decoder.feed(frame)
    assert json.loads(restored)==message
    assert len(decoder.parts)==1


def test_decoder_expires_and_bounds_unfinished_messages():
    from desnivel.sinks.voice_wire import VoiceDecoder
    now=[0.];decoder=VoiceDecoder(clock=lambda:now[0])
    for serial in range(20):
        frame=next(voice_packets('/control',{'text':'x'*3000},1,serial)).params
        assert decoder.feed(frame) is None
    assert len(decoder.parts)==8
    now[0]=2.
    assert decoder.feed(list(b'{}'))==b'{}'
    assert not decoder.parts
    with pytest.raises(ValueError):decoder.feed([-1,1,1,0,12001,2])


@pytest.mark.parametrize('length', [901, 1100, 1490, 1500, 3000, 11000])
def test_control_frames_fit_the_actual_default_max_udpsend_buffer(length):
    from desnivel.sinks.voice_wire import CONTROL_CHUNK_BYTES, CONTROL_CHUNK_MARKER, VoiceDecoder
    message={'text':'x'*(length-11)}
    frames=tuple(voice_packets('/desnivel/v1/voice/control',message,7,9,chunk_bytes=CONTROL_CHUNK_BYTES))
    decoder=VoiceDecoder(clock=lambda:0.)
    restored=None
    for packet in reversed(frames):
        assert len(packet.dgram)<=5096
        assert packet.params[0]==CONTROL_CHUNK_MARKER
        result=decoder.feed(packet.params)
        if result is not None:restored=result
    assert json.loads(restored)==message
