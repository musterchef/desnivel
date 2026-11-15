"""Frasi percussive, fase fra finestre e compatibilità con il player comune."""
from copy import deepcopy

import pytest

from desnivel.adapters.voice_device import DeviceVoice, VoiceDeviceBridge
from desnivel.cli.generators import build_generator
from desnivel.music.coordinator import PlanningRequest
from desnivel.music.percussion.generator import PercussionGenerator


def definition():
    return {'type': 'percussion_pattern', 'lanes': {'kick': 36, 'snare': 38, 'hat': 42},
            'patterns': [
                {'name': 'first', 'length_beats': 4,
                 'hits': [{'beat': 0, 'lane': 'kick', 'velocity': 90}]},
                {'name': 'single', 'length_beats': 4,
                 'hits': [{'beat': 0, 'lane': 'kick', 'velocity': 90}]},
                {'name': 'quarters', 'length_beats': 4,
                 'hits': [{'beat': i*.25, 'lane': 'hat', 'velocity': 60} for i in range(16)]}],
            'settings': {'pattern': 0, 'velocity_ratio': .85, 'gate_beats': .1},
            'presets': {'quarters': {'pattern': 2}}}


def generator(spec=None):
    spec = spec or definition()
    return PercussionGenerator(spec['lanes'], spec['patterns'], spec.get('settings'))


def request(start=0, length=4, **parameters):
    return PlanningRequest(start, length, None, {}, 'rhythm', parameters)


def test_patterns_follow_json_hits_midi_map_and_velocity():
    spec = definition()
    compose = generator(spec)
    for index, pattern in enumerate(spec['patterns']):
        phrase = compose(request(pattern=index, velocity_ratio=1))
        assert sorted((note.beat, note.pitch, note.velocity) for note in phrase.notes) == sorted(
            (hit['beat'], spec['lanes'][hit['lane']], hit['velocity']) for hit in pattern['hits'])
        assert all(note.duration == pytest.approx(.1) for note in phrase.notes)
        assert compose.last_decision['pattern'] == pattern['name']


def test_pattern_phase_is_independent_of_request_partition_and_seek():
    compose = generator()
    whole = compose(request(start=0, length=8, pattern=1))
    partitions = [compose(request(start=offset, length=2, pattern=1)) for offset in (0, 2, 4, 6)]
    assert [(n.beat, n.pitch) for n in whole.notes] == [
        (offset+n.beat, n.pitch) for offset, phrase in zip((0, 2, 4, 6), partitions) for n in phrase.notes]
    assert compose(request(16, pattern=1)) == compose(request(0, pattern=1))


def test_gate_is_clipped_before_next_same_pitch_and_phrase_end():
    compose = generator()
    phrase = compose(request(start=0, length=4, pattern=2, gate_beats=1))
    end_by_pitch = {}
    for note in phrase.notes:
        assert note.beat >= end_by_pitch.get(note.pitch, 0)
        end_by_pitch[note.pitch] = note.beat+note.duration
        assert note.beat+note.duration <= phrase.length_beats
    assert max(n.duration for n in phrase.notes if n.pitch == 42) == .25


def test_percussion_uses_registered_controls_and_common_device_destination():
    registered = build_generator(definition())
    assert registered.generator.supported_roles == ('rhythm',)
    assert set(registered.controls) == {'pattern', 'velocity_ratio', 'gate_beats'}
    assert registered.presets['quarters']['pattern'] == 2
    sent = []
    bridge = VoiceDeviceBridge({'part': DeviceVoice()}, lambda *args: sent.append(args))
    bridge.handle(dict(version=1, voice='part', instance='test', reply_port=9104, serial=1, action='hello'))
    phrase = registered.generator.generate(request(pattern=2))
    bridge.destination('part')(4, phrase)
    assert sent[-1][0] == 9104
    assert len(sent[-1][2]['plan']['phrase']['notes']) == 16


@pytest.mark.parametrize('problem', ['unknown_lane', 'duplicate_pitch', 'duplicate_hit', 'outside_cycle',
                                     'bad_velocity', 'bad_cycle', 'unknown_parameter', 'bad_pattern'])
def test_invalid_definitions_and_settings_are_rejected(problem):
    spec = deepcopy(definition())
    if problem == 'unknown_lane':
        spec['patterns'][0]['hits'][0]['lane'] = 'missing'
    elif problem == 'duplicate_pitch':
        spec['lanes']['hat'] = spec['lanes']['kick']
    elif problem == 'duplicate_hit':
        spec['patterns'][0]['hits'].append(deepcopy(spec['patterns'][0]['hits'][0]))
    elif problem == 'outside_cycle':
        spec['patterns'][0]['hits'][0]['beat'] = 4
    elif problem == 'bad_velocity':
        spec['patterns'][0]['hits'][0]['velocity'] = 0
    elif problem == 'bad_cycle':
        spec['patterns'][0]['length_beats'] = 0
    elif problem == 'unknown_parameter':
        spec['settings']['unknown'] = 1
    else:
        spec['settings']['pattern'] = 99
    with pytest.raises(ValueError):
        generator(spec)


def test_excessive_event_count_and_unsupported_role_are_rejected():
    compose = generator()
    with pytest.raises(ValueError, match='128'):
        compose(request(length=100, pattern=2))
    with pytest.raises(ValueError, match='ruolo'):
        compose.validate('melody', {})
