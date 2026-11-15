from dataclasses import replace

import pytest

from desnivel.music.coordinator import MusicCoordinator, PlanningRequest, Voice
from desnivel.music.arrangement import Assignment
from desnivel.music.director import MusicalContext
from desnivel.music.melodic.development import motif_cells
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
@pytest.mark.parametrize('seed', [0, 7, 17])
def test_tonic_closures_are_two_to_four_participating_periods_apart(windows, seed):
    g = MotifGenerator(MOTIF, dict(development=.7, seed=seed, phrase_windows=windows))
    closures, sounded_periods = [], []
    for period in range(24):
        sounding = period not in (0, 3, 7, 8, 15)
        if sounding:
            sounded_periods.append(period)
        for window in range(windows):
            # Anche i periodi con l'ultima finestra silenziata contano.
            audible = sounding and (period % 3 != 1 or window != windows-1)
            phrase = g(request((period*windows+window)*4, participating=audible))
            if g.last_decision['ending'] == 'tonic':
                assert audible and phrase.notes[-1].pitch % 12 == 0
                closures.append(len(sounded_periods))
    assert len(closures) >= 4
    assert 2 <= closures[0] <= 4
    assert all(2 <= b-a <= 4 for a, b in zip(closures, closures[1:]))


def test_transposition_keeps_cell_intervals_and_recall_restores_source_degrees():
    g = generator()
    transposed = recalled = False
    for i in range(80):
        phrase = g(request(i*4))
        d = g.last_decision
        cell = d['cell_degrees']
        anchor = phrase.notes[:len(cell)]
        assert tuple(cell) in motif_cells(MOTIF)
        assert [n.pitch for n in anchor] == d['anchor_pitches']
        if d['phase'] == 'transpose':
            transposed = True
            assert d['degree_shift'] != 0
        if d['phase'] == 'recall':
            recalled = True
            assert d['degree_shift'] == 0
    assert transposed and recalled


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


def test_context_and_period_changes_keep_material_and_adapt_scale():
    g = generator()
    g(request())
    last_pitch = g._development.last_pitch
    new_context = MusicalContext(1, 'changed', 62, 'minor')
    phrase = g(request(4, context=new_context, velocity=49, step_beats=.5))
    assert abs(phrase.notes[0].pitch-last_pitch) <= 7
    assert all(n.pitch % 12 in (2, 4, 5, 7, 9, 10, 0) for n in phrase.notes)
    assert g._development.period_start == 0
    plan = g.stage(request(8, context=new_context, phrase_windows=2))
    assert plan.gestures[0].start == 8 and plan.gestures[0].end == 16
    assert plan.decision['window'] == 1
    g.accept(plan)
    g(request(12, context=new_context, phrase_windows=2))


def test_role_exit_interrupts_the_melodic_sentence_and_reentry_recalls_a_cell():
    g = generator()
    g(request())
    g(replace(request(4), role='harmony'))
    assert g._development is None
    plan = g.stage(request(8))
    assert plan.decision['phase'] == 'statement'
    assert plan.gestures[0].start == 8


def test_coordinator_presence_does_not_advance_closure_count_or_create_false_closures():
    g = generator(phrase_windows=2)
    c = MusicCoordinator({'m': Voice(g, supported_roles=('melody',), stage=g.stage, accept=g.accept)})
    for start in range(0, 32, 4):
        result = c.plan(start, 4, MusicalContext(0, 'test', 60, 'major'),
                        assignments={'m': Assignment('melody', {}, 0)})
        assert not result['m'].notes
    assert g._development.completed_since_close == 0
    assert g._development.last_pitch is None
    c.plan(32, 4, MusicalContext(0, 'test', 60, 'major'), assignments={'m': Assignment('melody', {})})
    assert g.last_decision['phase'] == 'statement'


def test_single_cell_high_steps_and_full_articulation_fit_the_window():
    for degrees in ([0], [0, 2], MOTIF):
        g = MotifGenerator(degrees, dict(development=1, step_beats=8, articulation=1))
        for i in range(16):
            phrase = g(request(i*4))
            assert phrase.notes and all(n.beat+n.duration <= 4 for n in phrase.notes)


def test_silence_preserves_the_last_heard_material_and_the_need_for_a_new_opening():
    g = generator(phrase_windows=2)
    i = 0
    while True:
        g(request(i*4))
        i += 1
        if g.last_decision['ending'] == 'tonic':
            break
        assert i < 32
    state = g._development
    g(request(i*4, participating=False))
    assert g._development.last_pitch == state.last_pitch
    assert g._development.closed_last and g._development.cell == state.cell
    assert g._development.repetitions == state.repetitions
    g(request((i+1)*4))
    assert g.last_decision['phase'] == 'statement'


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
