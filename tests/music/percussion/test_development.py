"""Continuità del materiale, trasformazioni e silenzi nella voce percussiva."""
from copy import deepcopy
import json
import math
from pathlib import Path

import pytest

from desnivel.cli.generators import build_generator
from desnivel.music.coordinator import PlanningRequest
from desnivel.music.phrases import Note, Phrase
from desnivel.music.percussion.development import PercussionPhraseGenerator


def definition():
    return json.loads(Path('presets/organico.json').read_text())['generators']['percussion']


def generator(spec=None):
    spec = spec or definition()
    return PercussionPhraseGenerator(spec['lanes'], spec['material'], spec['anchor_beats'],
                                    spec['development'], spec['interaction'], spec.get('settings'),
                                    standard_material=spec.get('standard_material'))


def request(start=0, length=4, **parameters):
    notes = tuple(Note(i, 60, min(.1, length-i), 90) for i in range(0, math.ceil(length), 4))
    reference = Phrase(length, notes)
    return PlanningRequest(start, length, None, {'voice_01': reference, 'voice_02': reference}, 'percussion', parameters)


def signature(phrase, offset=0):
    return [(offset+n.beat, n.pitch, n.velocity) for n in phrase.notes]


def test_logical_phase_is_independent_of_live_start_and_request_partition():
    whole = generator()(request(start=100, length=64))
    compose = generator()
    pieces = [compose(request(start=100+i, length=4)) for i in range(0, 64, 4)]
    assert signature(whole) == [event for i, p in enumerate(pieces) for event in signature(p, i*4)]
    assert generator()(request(0)) == generator()(request(100))
    assert pieces[0] != pieces[1]  # Il materiale non riparte a ogni finestra.


@pytest.mark.parametrize('operation', ['subtract', 'displace', 'accent', 'silence'])
def test_transformations_preserve_anchors_except_explicit_suspension(operation):
    spec = definition()
    spec['development'] = ['statement', operation]
    spec['settings']['displacement_beats'] = .25
    compose = generator(spec)
    length = spec['material']['length_beats']
    original = compose(request(0, length, variation=1, velocity_ratio=1))
    changed = compose(request(length, length, variation=1, velocity_ratio=1))
    assert compose.last_decision['cycles'] == [{'cycle': 1, 'operation': operation}]
    anchors = [event for event in signature(original) if event[0] in spec['anchor_beats']]
    if operation == 'silence':
        assert not changed.notes
    else:
        assert all(event in signature(changed) for event in anchors)
        assert signature(changed) != signature(original)
    if operation == 'subtract':
        assert signature(changed) == anchors


def test_zero_variation_repeats_material_and_reset_restores_first_phrase():
    spec = definition()
    spec['development'] = ['statement', 'silence']
    compose = generator(spec)
    length = spec['material']['length_beats']
    initial = compose(request(40, length, variation=0))
    assert compose(request(40+length, length, variation=0)) == initial
    compose.reset()
    assert compose.position == 0 and compose.last_decision is None
    assert compose(request(100, length, variation=0)) == initial


def test_replanning_same_start_does_not_consume_material_twice():
    compose = generator()
    first = compose(request(0))
    assert compose(request(0)) == first
    assert compose.position == 4
    assert compose(request(0, velocity_ratio=.5)) != first
    assert compose.position == 4
    compose(request(4))
    assert compose.position == 8


def test_notes_are_bounded_and_registered_with_existing_device_controls():
    registered = build_generator(definition())
    assert registered.reset is not None
    assert 'pattern' not in registered.controls
    assert set(registered.controls) == {'style', 'transition_beats', 'conceptuality', 'variation', 'displacement_beats', 'velocity_ratio', 'gate_beats', 'seed',
                                         'support_tolerance_beats', 'answer_clearance_beats'}
    for start in range(0, 100, 4):
        phrase = registered.generator.generate(request(start, gate_beats=1))
        ends = {}
        for n in phrase.notes:
            assert 0 <= n.beat < 4 and n.beat+n.duration <= 4
            assert n.beat >= ends.get(n.pitch, 0)
            ends[n.pitch] = n.beat+n.duration
            assert n.pitch in definition()['lanes'].values() and 1 <= n.velocity <= 127
    assert registered.generator.describe()['method'] == 'percussion_phrase'


def test_control_applicability_distinguishes_standard_and_developed_material():
    compose = generator()
    standard = compose.describe_controls('percussion', {'conceptuality': 0})
    assert standard['conceptuality']['label'] == 'Concettualità'
    assert 'inactive_reason' in standard['seed']
    assert 'inactive_reason' in standard['support_tolerance_beats']
    assert 'velocity_ratio' not in standard and 'gate_beats' not in standard
    developed = compose.describe_controls('percussion', {'conceptuality': 1, 'variation': 0})
    assert 'inactive_reason' in developed['displacement_beats']
    assert 'seed' not in developed
    assert 'displacement_beats' not in compose.describe_controls('percussion', {'variation': 1})
    compose.development = ('statement', 'accent')
    assert 'inactive_reason' in compose.describe_controls('percussion', {'variation': 1})['displacement_beats']


@pytest.mark.parametrize('problem', ['unknown_operation', 'missing_statement', 'unknown_anchor', 'bad_settings'])
def test_invalid_material_development_is_rejected(problem):
    spec = deepcopy(definition())
    if problem == 'unknown_operation':
        spec['development'].append('unknown')
    elif problem == 'missing_statement':
        spec['development'] = ['silence']
    elif problem == 'unknown_anchor':
        spec['anchor_beats'] = [123]
    else:
        spec['settings']['variation'] = 2
    with pytest.raises(ValueError):
        generator(spec)


def test_listening_configuration_keeps_shared_grid_and_low_pulse_through_development():
    spec = definition()
    compose = generator(spec)
    assert spec['settings']['displacement_beats'] == 0
    support = {spec['lanes'][name] for name in spec['interaction']['support_lanes']}
    for start in range(0, 128, 4):
        phrase = compose(request(start))
        assert all(n.beat*4 == pytest.approx(round(n.beat*4)) for n in phrase.notes)
        operation = compose.last_decision['cycles'][0]['operation']
        if operation == 'silence':
            assert not phrase.notes
        else:
            assert any(n.pitch in support and n.beat == 0 for n in phrase.notes)


def test_phase_stays_on_common_window_boundary_when_live_planning_skips_a_window():
    compose = generator()
    first = compose(request(4))
    following = compose(request(12))
    low = definition()['lanes']['low']
    assert any(n.pitch == low and n.beat == 0 for n in first.notes)
    assert any(n.pitch == low and n.beat == 0 for n in following.notes)
    assert compose.last_decision['logical_start'] == 4


def ensemble_request(support_beats, melody_beats):
    support = Phrase(4, tuple(Note(b, 45, .1, 100) for b in support_beats))
    foreground = Phrase(4, tuple(Note(b, 69, .1, 80) for b in melody_beats))
    return PlanningRequest(0, 4, None, {'voice_01': foreground, 'voice_02': support}, 'percussion', {})


def test_support_follows_actual_reference_attacks_instead_of_fixed_material():
    compose = generator()
    first = compose(ensemble_request([0], [0]))
    shifted = compose(ensemble_request([.5], [0]))
    low = definition()['lanes']['low']
    assert [n.beat for n in first.notes if n.pitch == low] == [0]
    assert [n.beat for n in shifted.notes if n.pitch == low] == [.5]
    distant = compose(ensemble_request([2], [0]))
    assert not any(n.pitch == low for n in distant.notes)


def test_responses_leave_space_at_actual_foreground_attacks():
    compose = generator()
    first = compose(ensemble_request([0], [0]))
    crowded = compose(ensemble_request([0], [0, .75, 1.5, 2.5, 2.75]))
    assert len(crowded.notes) < len(first.notes)
    assert all(n.pitch == 36 or all(abs(n.beat-b) >= .25 for b in [0, .75, 1.5, 2.5, 2.75])
               for n in crowded.notes)
    assert compose.last_decision['interaction']['omitted_answer_hits'] > 0


def test_joint_rest_is_silent_and_missing_optional_support_does_not_invent_hits():
    compose = generator()
    assert not compose(ensemble_request([], [])).notes
    source = Phrase(4, (Note(0, 60, .1, 90),))
    phrase = compose(PlanningRequest(0, 4, None, {'voice_01': source}, 'percussion', {}))
    assert phrase.notes and all(n.pitch != 36 for n in phrase.notes)
    assert not compose.last_decision['interaction']['support_available']
    with pytest.raises(ValueError, match='riferimento richiesta'):
        compose(PlanningRequest(0, 4, None, {}, 'percussion', {}))


def test_full_palette_remains_available_and_both_support_lanes_follow_reference():
    spec = definition()
    length = spec['material']['length_beats']
    reference = Phrase(length, tuple(Note(b+.5, 45, .1, 90) for b in range(0, length, 4)))
    foreground = Phrase(length, (Note(0, 69, .1, 90),))
    phrase = generator()(PlanningRequest(0, length, None,
        {'voice_01': foreground, 'voice_02': reference}, 'percussion', {'variation': 0}))
    assert {n.pitch for n in phrase.notes} == set(spec['lanes'].values())
    support = {spec['lanes'][name] for name in spec['interaction']['support_lanes']}
    for pitch in support:
        attacks = [n.beat for n in phrase.notes if n.pitch == pitch]
        assert attacks and all(b % 4 == .5 for b in attacks)


def test_standard_mode_repeats_the_configured_groove_even_when_other_voices_rest():
    compose = generator()
    silent = Phrase(4, ())
    req = PlanningRequest(0, 4, None, {'voice_01': silent}, 'percussion', {'conceptuality': 0})
    first = compose(req)
    assert len(first.notes) == len(definition()['standard_material']['hits'])
    assert [n.beat for n in first.notes if n.pitch == 36] == [0, 2]
    assert [n.beat for n in first.notes if n.pitch == 38] == [1, 3]
    assert compose(PlanningRequest(4, 4, None, {}, 'percussion', {'conceptuality': 0})) == first
    assert not generator()(PlanningRequest(0, 4, None, {'voice_01': silent}, 'percussion', {'conceptuality': 1})).notes


def test_hybrid_changes_attacks_and_remains_reproducible_across_window_sizes():
    compose = generator()
    whole = compose(request(100, 32, conceptuality=.5))
    split = generator()
    # Le sorgenti hanno qui la stessa fase logica in ogni finestra.
    pieces = [split(request(100+i, 4, conceptuality=.5)) for i in range(0, 32, 4)]
    assert signature(whole) == [event for i, p in enumerate(pieces) for event in signature(p, i*4)]
    assert whole != generator()(request(100, 32, conceptuality=0))
    assert whole != generator()(request(100, 32, conceptuality=1))
    assert generator()(request(100, 32, conceptuality=.5)) == whole
    with pytest.raises(ValueError):
        generator()(request(conceptuality=1.1))
