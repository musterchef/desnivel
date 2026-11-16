from dataclasses import replace

import pytest

from desnivel.music.coordinator import MusicCoordinator, PlanningRequest, Voice
from desnivel.music.arrangement import Assignment
from desnivel.music.director import MusicalContext
from desnivel.music.melodic.development import _fit_cell_rhythm, motif_cells
from desnivel.music.melodic.generator import MotifGenerator


MOTIF = [0, 2, 4, 1, 3, 2, 1, 0]


def generator(**settings):
    return MotifGenerator(MOTIF, dict(development=.7, seed=7, **settings))


def request(start=0, participating=True, context=None, **parameters):
    return PlanningRequest(start, 4, context or MusicalContext(0, 'test', 60, 'major'), {},
                           'melody', parameters, participating=participating)


def test_cells_are_derived_from_the_motif_including_short_and_oscillating_material():
    assert motif_cells(MOTIF) == ((0, 2, 4), (3, 2, 1, 0))
    assert motif_cells([2]) == ((2,),)
    assert motif_cells([0, 2]) == ((0, 2),)
    assert all(cell in ((0, 1, 0), (0, 1)) for cell in motif_cells([0, 1, 0, 1, 0, 1]))


@pytest.mark.parametrize('windows', [2, 4, 8])
def test_gesture_spans_group_windows_without_scheduled_tonic_closures(windows):
    g = MotifGenerator(MOTIF, dict(development=.7, phrase_windows=windows))
    for i in range(windows*4):
        plan = g.stage(request(i*4))
        gesture = i//windows
        assert plan.gestures[0].start == gesture*windows*4
        assert plan.gestures[0].end == (gesture+1)*windows*4
        assert all(note.beat+note.duration <= 4 for note in plan.phrase.notes)
        assert 'ending' not in plan.decision
        g.accept(plan)


def test_development_keeps_cell_identity_and_varies_its_melodic_operation():
    g = generator()
    operations = set()
    for i in range(80):
        phrase = g(request(i*4))
        d = g.last_decision
        operations.add(d['phase'])
        cell = d['cell_degrees']
        anchor = phrase.notes[:len(cell)]
        assert tuple(cell) in motif_cells(MOTIF)
        assert [n.pitch for n in anchor] == d['anchor_pitches']
        if d['phase'] == 'transpose':
            assert d['degree_shift'] != 0
    assert {'rhythm', 'transpose', 'fragment', 'continuation'} <= operations
    assert not operations & {'recall', 'extend'}


def test_state_is_prepared_without_mutation_and_identical_retries_do_not_advance():
    a, b = generator(), generator()
    first, again = a.stage(request()), a.stage(request())
    assert first == again and a._development is None
    a.accept(first)
    b(request())
    for i in range(1, 12):
        req = request(i*4)
        assert a(req) == b(req)
        state = a._development
        a(req)
        assert a._development == state
    with pytest.raises(ValueError, match='reset'):
        a(request(0))
    a.reset()
    assert a(request(100)) == first.phrase


def test_context_and_gesture_length_changes_keep_material_and_adapt_scale():
    g = generator()
    g(request())
    last_pitch = g._development.last_pitch
    new_context = MusicalContext(1, 'changed', 62, 'minor')
    phrase = g(request(4, context=new_context, velocity=49, step_beats=.5))
    assert abs(phrase.notes[0].pitch-last_pitch) <= 7
    assert all(n.pitch % 12 in (2, 4, 5, 7, 9, 10, 0) for n in phrase.notes)
    assert g._development.gesture_start == 0
    plan = g.stage(request(8, context=new_context, phrase_windows=2))
    assert plan.gestures[0].start == 8 and plan.gestures[0].end == 16
    assert plan.decision['window'] == 1
    g.accept(plan)
    g(request(12, context=new_context, phrase_windows=2))


def test_role_exit_interrupts_the_melodic_sentence_and_reentry_presents_a_cell():
    g = generator()
    g(request())
    g(replace(request(4), role='harmony'))
    assert g._development is None
    plan = g.stage(request(8))
    assert plan.decision['phase'] == 'statement'
    assert plan.gestures[0].start == 8


def test_coordinator_presence_does_not_advance_silenced_melodic_state():
    g = generator(phrase_windows=2)
    c = MusicCoordinator({'m': Voice(g, supported_roles=('melody',), stage=g.stage, accept=g.accept)})
    for start in range(0, 32, 4):
        result = c.plan(start, 4, MusicalContext(0, 'test', 60, 'major'),
                        assignments={'m': Assignment('melody', {}, 0)})
        assert not result['m'].notes
    assert g._development.last_pitch is None
    c.plan(32, 4, MusicalContext(0, 'test', 60, 'major'), assignments={'m': Assignment('melody', {})})
    assert g.last_decision['phase'] == 'statement'


def test_single_cell_high_steps_and_full_articulation_fit_the_window():
    for degrees in ([0], [0, 2], MOTIF):
        g = MotifGenerator(degrees, dict(development=1, step_beats=8, articulation=1))
        for i in range(16):
            phrase = g(request(i*4))
            assert phrase.notes and all(n.beat+n.duration <= 4 for n in phrase.notes)


def test_cell_rhythm_fits_using_available_figures_without_changing_a_fitting_rhythm():
    assert _fit_cell_rhythm([1., 1., 1.], 1., 4.) == [1., 1., 1.]
    assert _fit_cell_rhythm([1., 1., 1.], 1., 2.5) == [1., 1., .5]
    assert _fit_cell_rhythm([1., 1., 1., 1.], 8., 2.4) == [.5]*4


@pytest.mark.parametrize('step', [1., 1.5, 2., 2/3])
def test_developed_attacks_use_intentional_subdivisions_throughout_the_window(step):
    g = MotifGenerator(MOTIF, dict(development=.7, activity=.75, phrase_windows=4, seed=0,
                                  step_beats=step))
    rhythms = set()
    phases = set()
    for i in range(400):
        phrase = g(request(i*4))
        rhythms.add(tuple(round(n.beat, 6) for n in phrase.notes))
        phases.add(g.last_decision['phase'])
        for note in phrase.notes:
            subdivision = note.beat/(step/8)
            assert subdivision == pytest.approx(round(subdivision), abs=1e-8)
            assert note.duration > 0 and note.beat+note.duration <= 4
    assert not {'recall', 'extend'} & phases
    assert len(rhythms) > 1


def test_activity_changes_melodic_density():
    sparse = MotifGenerator(MOTIF, dict(development=.7, activity=.2, seed=3))
    active = MotifGenerator(MOTIF, dict(development=.7, activity=.9, seed=3))
    sparse_count = active_count = 0
    for i in range(120):
        sparse_count += len(sparse(request(i*4)).notes)
        active_count += len(active(request(i*4)).notes)
    assert active_count > sparse_count


@pytest.mark.parametrize('length,step', [(.3, 1.), (3.4, 1.5), (4., 8.)])
def test_fractional_windows_and_large_steps_keep_complete_nonoverlapping_cells(length, step):
    g = MotifGenerator(MOTIF, dict(development=.7, seed=3, step_beats=step, articulation=1))
    for i in range(80):
        phrase = g(replace(request(i*length), length_beats=length))
        decision = g.last_decision
        assert [n.pitch for n in phrase.notes[:len(decision['cell_degrees'])]] == decision['anchor_pitches']
        assert all(a.beat+a.duration <= b.beat+1e-10 for a, b in zip(phrase.notes, phrase.notes[1:]))
        assert all(n.duration > 0 and n.beat+n.duration <= length for n in phrase.notes)


def test_silence_preserves_the_last_heard_material_and_gesture_state():
    g = generator(phrase_windows=2)
    g(request())
    state = g._development
    g(request(4, participating=False))
    assert g._development.last_pitch == state.last_pitch
    assert g._development.cell == state.cell
    assert g._development.repetitions == state.repetitions
    g(request(8))
    assert g.last_decision['phase'] != 'statement'


def test_unavailable_transpositions_are_excluded_before_operation_selection():
    g = MotifGenerator([0, 63, 127], dict(development=1, seed=1))
    context = MusicalContext(0, 'wide', 0, 'chromatic')
    for i in range(32):
        phrase = g(request(i*4, context=context))
        assert all(0 <= note.pitch <= 127 for note in phrase.notes)
        assert g.last_decision['phase'] != 'transpose'


def test_fast_extensions_stay_near_the_motif_register_and_connect_periods():
    g = generator(step_beats=.25)
    last = None
    for i in range(48):
        phrase = g(request(i*4))
        assert all(48 <= note.pitch <= 79 for note in phrase.notes)
        if last is not None:
            assert abs(phrase.notes[0].pitch-last) <= 7
        last = phrase.notes[-1].pitch
