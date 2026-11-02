import pytest

from desnivel.music.automation import AdaptiveContext, ParameterTarget, resolve_parameters
from desnivel.music.arrangement import Assignment
from desnivel.music.coordinator import MusicCoordinator, Voice
from desnivel.music.director import MusicalContext
from desnivel.music.interactions import VoicePlan
from desnivel.music.phrases import Note, Phrase


def resolve(start, previous=None, manual=None, targets=None):
    return resolve_parameters({'x': .2, 'y': 10}, targets or {
        'x': ParameterTarget(.8, 'test', 16),
        'y': ParameterTarget(15.4, 'test', 8, integer=True)},
        manual or {}, previous or {}, start=start, logical_start=start, scope=('line', 0))


def test_transitions_follow_beats_and_manual_release_is_continuous():
    values, state, _ = resolve(0)
    assert values == {'x': .2, 'y': 10}
    values, state, _ = resolve(4, state)
    assert values['x'] == pytest.approx(.35)
    values, state, decisions = resolve(8, state, {'x': .95})
    assert values == {'x': .95, 'y': 15}
    assert decisions['x']['source'] == 'manual' and decisions['y']['target'] == 15
    values, state, _ = resolve(12, state)
    assert values['x'] == .95  # Il rilascio non salta direttamente all'obiettivo .8.
    values, state, _ = resolve(16, state)
    assert .8 < values['x'] < .95
    assert values['y'] == 15


def test_update_cadence_and_partition_independent_interpolation():
    target = {'x': ParameterTarget(.8, 'test', 16, 16)}
    _, state, _ = resolve(0, targets=target)
    _, state, decisions = resolve(4, state, targets={'x': ParameterTarget(.3, 'changed', 16, 16)})
    assert decisions['x']['target'] == .8
    direct, _, _ = resolve(8, targets=target, previous=resolve(0, targets=target)[1])
    split, _, _ = resolve(8, targets=target, previous=state)
    assert direct == split
    _, _, decisions = resolve(16, state, targets={'x': ParameterTarget(.3, 'changed', 16, 16)})
    assert decisions['x']['target'] == .3


def test_stable_objective_reaches_a_stable_value():
    state = None
    for start in range(0, 65, 4):
        values, state, _ = resolve(start, state)
        if start >= 16:
            assert values == {'x': .8, 'y': 15}


def test_failed_plan_duplicate_and_reset_do_not_advance_automation():
    calls, accepted, fail = [], [], [False]
    def adapt(request):
        calls.append(request.observation)
        return {'amount': ParameterTarget(request.intent.intensity, 'intent', 8)}
    def stage(request):
        if fail[0] and request.role == 'second':
            raise ValueError('failed')
        return VoicePlan(Phrase(4, (Note(0, 60, 1, round(request.parameters['amount']*100)),)))
    parts = {name: Voice(lambda r: None, supported_roles=(role,), stage=stage,
                         accept=accepted.append, adapt=adapt)
             for name, role in [('a', 'first'), ('b', 'second')]}
    c = MusicCoordinator(parts)
    assignments = {'a': Assignment('first', {'amount': .2}), 'b': Assignment('second', {'amount': .2})}
    context = MusicalContext(0, 'one', 60, 'major')
    def plan(start):
        return c.plan(start, 4, context, assignments=assignments, adaptive_context=AdaptiveContext(.8))
    plan(0)
    fail[0] = True
    with pytest.raises(ValueError, match='failed'):
        plan(4)
    assert len(accepted) == 2
    assert c.parameter_states_at('a')['amount']['effective'] == .2
    assert calls[-1] is calls[-2]
    fail[0] = False
    result = plan(4)
    assert result['a'].notes[0].velocity == 50
    count = len(calls)
    assert plan(4) == result and len(calls) == count
    c.reset()
    assert not c.parameter_states_at('a')
    assert plan(0)['a'].notes[0].velocity == 20


@pytest.mark.parametrize('value', [-1, 1.1, float('nan')])
def test_invalid_musical_intent_is_rejected(value):
    with pytest.raises(ValueError):
        AdaptiveContext(value)
