from types import SimpleNamespace

import pytest

from desnivel.adapters.live_recording import LiveRecording


def setup():
    calls, now = [], [0.]
    bridge = SimpleNamespace(require_recording=lambda voice: None,
                             control_recording=lambda *args: calls.append(args))
    capture = LiveRecording(bridge, 'clock', lambda: calls.append('restart'), lambda: 3,
                            clock=lambda: now[0])
    return capture, calls, now


def report(capture, status, **extra):
    capture.on_message(dict(voice='clock', action='recording_status',
                           report=dict(request=capture.request, status=status, **extra)))


def test_prepares_waits_for_rewind_confirmation_then_records_once():
    capture, calls, _ = setup()
    capture.control('record_both')
    assert calls == ['restart', ('clock', 'prepare', 1, 'both')]
    assert capture.status == 'preparing'
    report(capture, 'ready', tracks=[dict(name='synth_MIDI_REC')])
    capture.control('record_start')
    assert capture.status == 'rewinding'
    for voice, beat, playing, epoch in [('other', 0, 0, 4), ('clock', 0, 0, 3),
                                       ('clock', 4, 0, 4), ('clock', 0, 1, 4)]:
        capture.on_message(dict(voice=voice, action='transport',
                                transport=dict(beat=beat, playing=playing, epoch=epoch)))
    assert capture.status == 'rewinding'
    message = dict(voice='clock', action='transport', transport=dict(beat=0, playing=0, epoch=4))
    capture.on_message(message)
    capture.on_message(message)
    assert calls[-1] == ('clock', 'start', 2, 'both')
    assert calls.count(('clock', 'start', 2, 'both')) == 1
    report(capture, 'recording')
    assert capture.status == 'recording'
    capture.tick(finished=True)
    assert calls[-1] == ('clock', 'stop', 3, 'both')
    report(capture, 'ready')
    assert capture.status == 'ready'


def test_errors_timeouts_and_busy_state_do_not_start_recording():
    capture, calls, now = setup()
    with pytest.raises(ValueError, match='preparare'):
        capture.control('record_start')
    capture.control('record_audio')
    with pytest.raises(ValueError, match='corrente'):
        capture.control('record_midi')
    capture.on_message(dict(voice='clock', action='recording_status',
                            report=dict(request=0, status='ready')))
    assert capture.status == 'preparing'
    report(capture, 'error', error='routing assente')
    assert capture.snapshot()['error'] == 'routing assente'
    capture.control('record_midi')
    now[0] = 61
    capture.tick()
    assert capture.status == 'error'
    assert not any(isinstance(call, tuple) and call[1] == 'start' for call in calls)


def test_stop_from_live_is_reflected_and_old_ack_is_ignored():
    capture, _, _ = setup()
    capture.control('record_audio')
    report(capture, 'ready', tracks=[dict(name='synth_AUDIO_REC')])
    capture.control('record_start')
    capture.on_message(dict(voice='clock', action='hello', transport=dict(beat=0, playing=0, epoch=4)))
    report(capture, 'recording')
    report(capture, 'ready')
    assert capture.status == 'ready'
    report(capture, 'recording')
    assert capture.status == 'ready'
