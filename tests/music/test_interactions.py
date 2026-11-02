from dataclasses import replace

import pytest

from desnivel.music.coordinator import MusicCoordinator, Voice
from desnivel.music.arrangement import Assignment
from desnivel.music.interactions import GestureSpan, RhythmRelation, VoicePlan
from desnivel.music.phrases import Note, Phrase
from desnivel.music.rhythm import PreparedRhythm, RhythmReference, shape_rhythm


def phrase(beat=0):
    return Phrase(4, (Note(beat, 60, .25, 80),))


class Part:
    def __init__(self, span=4):
        self.accepted = 0
        self.span = span
        self.fail = False
        self.silent = False
        self.requests = []

    def stage(self, request):
        self.requests.append(request)
        if self.fail:
            raise ValueError('failed')
        start = request.start//self.span*self.span
        return VoicePlan(Phrase(4, ()) if self.silent else phrase(), self.accepted+1,
                         gestures=(GestureSpan(start, start+self.span),))

    def accept(self, result):
        self.accepted = result.state

    def voice(self, **kwargs):
        return Voice(lambda r: phrase(), supported_roles=('line',), stage=self.stage,
                     accept=self.accept, rhythmic_roles=('line',), **kwargs)


def relation(**kwargs):
    return RhythmRelation(**dict(dict(id='reply', source='a', target='b', lookback_beats=16,
                                     fragment_beats=4, strength=.5), **kwargs))


def test_staging_failure_retry_duplicate_and_reset_are_atomic():
    a, b = Part(), Part()
    c = MusicCoordinator({'a': a.voice(), 'b': b.voice(dependencies=('a',))}, relations=(relation(),))
    b.fail = True
    with pytest.raises(ValueError, match='failed'):
        c.plan(0, 4)
    assert a.accepted == b.accepted == 0
    assert not c.history and c.last_plan is None
    assert a.requests[-1].observation.available_beats == 0
    b.fail = False
    result = c.plan(0, 4)
    assert a.accepted == b.accepted == 1
    assert len(c.history) == 2
    assert c.plan(0, 4) == result
    assert a.accepted == b.accepted == 1
    with pytest.raises(ValueError, match='sovrapposte'):
        c.plan(2, 4)
    with pytest.raises(ValueError, match='reset'):
        c.plan(0, 2)
    epoch = c.epoch
    c.reset()
    assert c.epoch == epoch+1 and not c.history and c.last_plan is None
    c.plan(0, 4)
    assert b.requests[-1].relations[0].gesture is None


def test_observation_includes_accepted_parts_of_incomplete_gestures_and_is_shared():
    a, b = Part(span=16), Part(span=16)
    c = MusicCoordinator({'a': a.voice(), 'b': b.voice(dependencies=('a',))}, relations=(relation(),))
    c.plan(0, 4)
    assert not c.history  # Il gesto non è ancora completo.
    b.fail = True
    with pytest.raises(ValueError):
        c.plan(4, 4)
    b.fail = False
    result = c.plan(4, 4)
    observation = a.requests[-1].observation
    assert observation is b.requests[-1].observation
    assert observation.available_beats == 4
    assert observation.voices['a'].attacks == 1
    assert c.plan(4, 4) == result
    c.plan(8, 4)
    assert a.requests[-1].observation.available_beats == 8
    assert a.requests[-1].observation.voices['a'].attacks == 2
    c.reset()
    c.plan(0, 4)
    assert a.requests[-1].observation.available_beats == 0


def test_complete_gestures_only_and_no_same_window_history_leak_or_reuse():
    a, b = Part(8), Part()
    c = MusicCoordinator({'a': a.voice(), 'b': b.voice()}, relations=(relation(),))
    c.plan(0, 4)
    assert b.requests[-1].relations[0].unavailable_reason == 'missing'
    assert all(g.voice != 'a' for g in c.history)
    c.plan(4, 4)
    assert b.requests[-1].relations[0].unavailable_reason == 'incomplete'
    assert next(g for g in c.history if g.voice == 'a').phrase.notes[1].beat == 4
    c.plan(8, 4)
    resolved = b.requests[-1].relations[0]
    assert resolved.gesture.span == GestureSpan(0, 8)
    assert resolved.phrase == phrase()
    c.plan(12, 4)
    assert b.requests[-1].relations[0].unavailable_reason == 'consumed'


def test_presence_silence_is_stored_as_silence_and_memory_expires():
    a, b = Part(), Part()
    c = MusicCoordinator({'a': a.voice(), 'b': b.voice()},
                         relations=(relation(lookback_beats=8),), history_beats=8)
    c.plan(0, 4, assignments={'a': Assignment('line', {}, 0), 'b': Assignment('line', {})})
    assert next(g for g in c.history if g.voice == 'a').phrase.notes == ()
    c.plan(4, 4)
    assert b.requests[-1].relations[0].unavailable_reason == 'silent'
    c.plan(20, 4)
    assert b.requests[-1].relations[0].unavailable_reason == 'missing'
    assert all(g.span.end > 12 for g in c.history)


@pytest.mark.parametrize('policy', ['independent', 'silence', 'error'])
def test_unavailable_policy(policy):
    a, b = Part(), Part()
    c = MusicCoordinator({'a': a.voice(), 'b': b.voice()}, relations=(relation(on_unavailable=policy),))
    if policy == 'error':
        with pytest.raises(ValueError, match='nessun gesto'):
            c.plan(0, 4)
        assert a.accepted == b.accepted == 0
    else:
        result = c.plan(0, 4)
        assert bool(result['b'].notes) == (policy == 'independent')


def test_reference_is_immutable_and_shared_even_when_producer_not_assigned():
    source, target = Part(), Part()
    points = [[0, 1], [2, .8]]
    reference = RhythmReference(4, 4, 0, points)
    points[0][0] = 3
    assert reference.points[0] == (0, 1)
    c = MusicCoordinator({'a': source.voice(prepare_reference=lambda r: PreparedRhythm(reference)),
                          'b': target.voice()}, rhythm_source='a')
    c.plan(100, 4, assignments={'b': Assignment('line', {})})
    assert target.requests[-1].rhythm is reference
    assert target.requests[-1].logical_start == 0
    assert source.accepted == 0


def test_rhythmic_shaping_keeps_material_and_order_and_bounds_movement():
    original = Phrase(4, tuple(Note(b, p, .3, 90) for b, p in [(.25, 60), (1.25, 64), (2.25, 67)]))
    assert shape_rhythm(original, [(((0., 1.),), 0)]) is original
    guided = shape_rhythm(original, [(((0., 1.), (1., .8), (2., .9)), 1)])
    assert [n.beat for n in guided.notes] == [0, 1, 2]
    assert [(n.pitch, n.velocity) for n in guided.notes] == [(n.pitch, n.velocity) for n in original.notes]
    dense = Phrase(4, tuple(Note(i/32, 60, 1/32, 90) for i in range(128)))
    result = shape_rhythm(dense, [(((0., 1.), (2., 1.)), 1)])
    assert len(result.notes) == 128
    assert all(abs(a.beat-b.beat) <= .5 for a, b in zip(dense.notes, result.notes))
    assert all(a.beat < b.beat for a, b in zip(result.notes, result.notes[1:]))


def test_unsupported_relations_and_capabilities_fail_explicitly():
    data = dict(id='r', source='a', target='b', scope='history', aspects=['pitch'],
                lookback_beats=8, fragment_beats=4, strength=.5)
    with pytest.raises(ValueError, match='solo aspetto rhythm'):
        RhythmRelation.from_dict(data)
    with pytest.raises(ValueError, match='trasformazioni'):
        RhythmRelation.from_dict(dict(data, aspects=['rhythm'], transpose=2))
    with pytest.raises(ValueError, match='produttore'):
        MusicCoordinator({'a': Part().voice()}, rhythm_source='a')
    with pytest.raises(ValueError, match='destinatario'):
        MusicCoordinator({'a': Part().voice(), 'b': replace(Part().voice(), rhythmic_roles=())},
                         relations=(relation(),))
