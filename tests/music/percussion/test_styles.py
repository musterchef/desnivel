import json
from dataclasses import replace
from pathlib import Path

import pytest

from desnivel.cli.generators import build_generator
from desnivel.music.coordinator import PlanningRequest
from desnivel.music.percussion.styles import STYLE_BY_ID, style_events
from desnivel.music.phrases import Note, Phrase


def definition():
    return json.loads(Path('presets/dialogo.json').read_text())['generators']['percussion']


def request(start=0, length=4, silent=False, **parameters):
    foreground = Phrase(length, () if silent else tuple(Note(i, 60, .1, 90) for i in range(0, length, 4)))
    return PlanningRequest(start, length, None, {'voice_01': foreground, 'voice_02': Phrase(length, ())},
                           'percussion', parameters, start)


def compose(generator, req):
    prepared = generator.prepare_reference(req)
    result = generator.stage(replace(req, rhythm=prepared.reference, prepared_material=prepared.material))
    generator.accept(result)
    return result


def events(phrase, offset=0):
    return [(round(n.beat+offset, 8), n.pitch, n.velocity) for n in phrase.notes]


def test_none_preserves_existing_material_and_profiles_need_explicit_mapping():
    a, b = build_generator(definition()).generator.generate, build_generator(definition()).generator.generate
    for start in range(0, 64, 4):
        assert compose(a, request(start)).phrase == compose(b, request(start, style='none')).phrase
    spec = definition()
    del spec['style_lanes']
    g = build_generator(spec)
    with pytest.raises(ValueError, match='style_lanes'):
        g.generator.validate('percussion', {'style': 'house_classic'})
    assert g.describe_controls('percussion', {})['style']['inactive_reason']
    with pytest.raises(ValueError, match='sconosciuto'):
        a.validate('percussion', {'style': 'unknown'})


@pytest.mark.parametrize('style', STYLE_BY_ID)
@pytest.mark.parametrize('amount', [0, .5, 1])
def test_identity_survives_silent_sources_and_full_transformations(style, amount):
    spec = definition()
    spec['development'] = ['statement', 'subtract', 'displace', 'accent']
    spec['settings']['variation'] = 1
    gen = build_generator(spec).generator.generate
    for start in range(0, 32, 4):
        result = compose(gen, request(start, silent=True, style=style, conceptuality=amount, velocity_ratio=1))
        cores = [(round(b-start, 8), p, v) for b, p, v, core in
                 style_events(STYLE_BY_ID[style], gen.style_lanes, start, start+4, 7) if core]
        assert all(event in events(result.phrase) for event in cores)
        assert result.decision['style_weights'] == {style: 1}


@pytest.mark.parametrize('style', STYLE_BY_ID)
@pytest.mark.parametrize('amount', [0, .5, 1])
def test_phase_and_swing_are_independent_of_window_partition(style, amount):
    spec = definition()
    spec['development'] = ['statement', 'displace']
    # Isola fase e sviluppo: il filtro interattivo legge soltanto le note
    # della finestra corrente, non gli attacchi della finestra futura.
    spec['settings']['answer_clearance_beats'] = 0
    full, split = build_generator(spec).generator.generate, build_generator(spec).generator.generate
    whole = compose(full, request(length=16, style=style, conceptuality=amount)).phrase
    pieces = [compose(split, request(start, style=style, conceptuality=amount)).phrase for start in range(0, 16, 4)]
    assert events(whole) == [event for i, part in enumerate(pieces) for event in events(part, 4*i)]
    guide = full.prepare_reference(request(length=16, style=style)).reference
    sliced = [split.prepare_reference(request(start, style=style)).reference for start in range(0, 16, 4)]
    assert [(round(b, 8), w) for b, w in guide.points] == [(round(4*i+b, 8), w) for i, part in enumerate(sliced) for b, w in part.points]
    if STYLE_BY_ID[style].swing_delay:
        assert any(round(n.beat % 1, 2) == round(.5+STYLE_BY_ID[style].swing_delay, 2)
                   for n in compose(split, request(16, style=style, conceptuality=0)).phrase.notes)


def test_styles_are_distinct_and_guide_contains_the_selected_structural_rhythm():
    signatures = []
    for style in STYLE_BY_ID:
        gen = build_generator(definition()).generator.generate
        req = request(style=style, conceptuality=0, velocity_ratio=1)
        prepared = gen.prepare_reference(req)
        result = compose(gen, req)
        signatures.append(events(result.phrase))
        assert all((beat, pitch, velocity) in events(result.phrase) for beat, pitch, velocity, core, _ in prepared.material.events if core and 0 <= beat < req.length_beats)
        assert all(beat in dict(prepared.reference.points) for beat, _, _, _, _ in prepared.material.events if 0 <= beat < req.length_beats)
    assert all(a != b for i, a in enumerate(signatures) for b in signatures[i+1:])


def test_switch_keeps_position_and_other_controls_and_silence_is_explicit():
    gen = build_generator(definition()).generator.generate
    compose(gen, request(style='house_classic'))
    plan = compose(gen, request(4, style='boom_bap_90s', variation=.25, conceptuality=.7))
    assert gen.position == 8 and plan.decision['logical_start'] == 4
    assert gen.settings['variation'] == .7 and gen.settings['conceptuality'] == 1
    spec = definition()
    spec['development'] = ['statement', 'silence']
    gen = build_generator(spec).generator.generate
    assert not compose(gen, request(8, style='house_classic', conceptuality=1)).phrase.notes
    assert compose(gen, request(12, style='house_classic', conceptuality=0)).phrase.notes


def test_profiles_have_finite_consistent_events_without_unintended_duplicates():
    for style in STYLE_BY_ID.values():
        assert len(style.variants) >= 2
        for variant in style.variants:
            assert len({(h.beat, h.role) for h in variant}) == len(variant)
            assert all(0 <= h.beat < style.cycle_beats and 1 <= h.velocity <= 127 for h in variant)


def test_style_vocabulary_evolves_and_zero_variation_fixes_the_figure():
    for style in STYLE_BY_ID:
        varied, fixed = [], []
        a, b = build_generator(definition()).generator.generate, build_generator(definition()).generator.generate
        for start in range(0, 128, 4):
            varied.append(tuple(events(compose(a, request(start, style=style, conceptuality=0)).phrase)))
            fixed.append(tuple(events(compose(b, request(start, style=style, conceptuality=0, variation=0)).phrase)))
        assert len(set(varied)) >= 3
        assert len(set(fixed)) == 1
        assert any(p == 42 for _, p, _ in events(compose(a, request(128, style=style, silent=True)).phrase))


def test_transition_interpolates_common_anchors_swing_and_redirects_from_current_mix():
    from desnivel.music.percussion.styles import transition_events
    gen = build_generator(definition()).generator.generate
    compose(gen, request(style='house_classic', variation=0))
    req = request(4, style='boom_bap_90s', conceptuality=0, variation=0, velocity_ratio=1)
    prepared = gen.prepare_reference(req)
    # Preparare o scartare un tentativo non cambia lo stato accettato.
    assert gen.style_transition.target == 'house_classic'
    assert prepared == gen.prepare_reference(req)
    result = compose(gen, req)
    assert result.decision['style_weights'] == {'house_classic': 1}
    assert result.decision['transition_end_weights'] == {'house_classic': .75, 'boom_bap_90s': .25}
    hat = next(n for n in result.phrase.notes if n.pitch == 42 and .5 <= n.beat < 1)
    assert .5 < hat.beat < .58
    # Il levare comune è un solo evento, non due hat sovrapposti.
    assert sum(n.pitch == 42 and .5 <= n.beat < 1 for n in result.phrase.notes) == 1
    redirected = gen.prepare_reference(request(8, style='breakbeat_house', variation=0)).material
    assert redirected.transition.weights(8) == {'house_classic': .75, 'boom_bap_90s': .25}
    prior = transition_events(gen.style_transition, gen.style_lanes, 8, 12, 7, 0)
    current = transition_events(redirected.transition, gen.style_lanes, 8, 12, 7, 0)
    assert prior[0] == current[0]
    compose(gen, request(8, style='breakbeat_house', variation=0))
    end = compose(gen, request(24, style='breakbeat_house', variation=0))
    assert end.decision['style_weights'] == {'breakbeat_house': 1}
    gen.reset()
    assert gen.style_transition is None


def test_transition_is_independent_of_window_partition_and_zero_is_immediate():
    a, b = build_generator(definition()).generator.generate, build_generator(definition()).generator.generate
    for gen in (a, b):
        compose(gen, request(style='house_classic', conceptuality=0))
    whole = compose(a, request(4, length=16, style='boom_bap_90s', conceptuality=0)).phrase
    pieces = [compose(b, request(start, style='boom_bap_90s', conceptuality=0)).phrase for start in range(4, 20, 4)]
    assert events(whole) == [e for i, part in enumerate(pieces) for e in events(part, 4*i)]
    instant = compose(b, request(20, style='breakbeat_house', transition_beats=0))
    assert instant.decision['style_weights'] == {'breakbeat_house': 1}


def test_reference_state_commits_while_producer_is_not_assigned_and_failed_plan_does_not_commit():
    from desnivel.music.coordinator import MusicCoordinator, Voice
    from desnivel.music.arrangement import Assignment
    from desnivel.music.interactions import VoicePlan
    gen = build_generator(definition()).generator.generate
    failed = [False]
    def stage(req):
        if failed[0]:
            raise ValueError('errore di prova')
        return VoicePlan(Phrase(req.length_beats, ()), None, {}, ())
    coord = MusicCoordinator({
        'guide': Voice(gen, stage=gen.stage, accept=gen.accept,
                       prepare_reference=gen.prepare_reference, accept_reference=gen.accept_reference),
        'other': Voice(lambda req: Phrase(req.length_beats, ()), supported_roles=('test',),
                       stage=stage, accept=lambda plan: None),
    }, rhythm_source='guide')
    assignments = {'other': Assignment('test', {})}
    coord.plan(0, 4, assignments=assignments, rhythm_parameters={'style': 'house_classic'})
    assert gen.style_transition.target == 'house_classic'
    failed[0] = True
    with pytest.raises(ValueError, match='prova'):
        coord.plan(4, 4, assignments=assignments, rhythm_parameters={'style': 'boom_bap_90s'})
    assert gen.style_transition.target == 'house_classic'
    failed[0] = False
    coord.plan(4, 4, assignments=assignments, rhythm_parameters={'style': 'boom_bap_90s'})
    assert gen.style_transition.weights(8) == {'house_classic': .75, 'boom_bap_90s': .25}


def test_transition_entry_chooses_the_closest_structural_figure():
    from desnivel.music.percussion.styles import transition_for
    first = transition_for(None, 'boom_bap_90s', 0, 16)
    change = transition_for(first, 'breakbeat_house', 4, 16, seed=7, variation=1)
    source = {(h.beat, h.role): h.velocity for h in STYLE_BY_ID['boom_bap_90s'].variants[
        first.variant('boom_bap_90s', 1, 7, 1)] if h.structural}
    def distance(variant):
        target = {(h.beat, h.role): h.velocity for h in variant if h.structural}
        return sum(abs(source.get(k, 0)-target.get(k, 0)) for k in source.keys() | target.keys())
    style = STYLE_BY_ID['breakbeat_house']
    selected = change.variant(style.id, 1, 7, 1)
    assert distance(style.variants[selected]) == min(map(distance, style.variants))


def test_old_drum_presets_acquire_transition_duration_without_rewriting_files(tmp_path):
    from desnivel.adapters.voice_device import DeviceVoice
    from desnivel.cli.voice_presets import connect_preset_library
    from desnivel.sinks.voice_presets import VoicePresetLibrary
    registered = build_generator(definition())
    old = {k: v for k, v in registered.values.items() if k != 'transition_beats'}
    path = tmp_path / 'presets.json'
    contents = json.dumps({'version': 1, 'voices': {'drums': {'old': old}}})
    path.write_text(contents)
    voice = DeviceVoice(controls=registered.controls, values=registered.values,
                        preset_defaults=registered.preset_defaults, apply=lambda values: None)
    connect_preset_library(VoicePresetLibrary(path), {'drums': voice})
    assert voice.presets['old']['transition_beats'] == 16
    assert voice.preset_migrations == {'old': {'transition_beats': 16}}
    assert path.read_text() == contents
