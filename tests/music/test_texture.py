from dataclasses import replace

import pytest

from desnivel.cli.generators import build_generator
from desnivel.music.coordinator import PlanningRequest
from desnivel.music.director import MusicalContext
from desnivel.music.phrases import Note, Phrase
from desnivel.music.texture.generator import TextureGenerator
from desnivel.music.texture.progression import HarmonicProgressionGenerator


def progressions(*items):
    return [dict(id=identifier, label=identifier.replace('_', ' '), steps=steps)
            for identifier, steps in items]


def request(start=0, notes=(), **parameters):
    return PlanningRequest(start, 4, MusicalContext(0, 'section', 60, 'major'),
                           {'melody': Phrase(4, tuple(notes))}, 'harmony', parameters)


def test_independent_texture_uses_section_degree_register_and_velocity():
    generator = TextureGenerator(2)
    phrase = generator(request(octave=1, velocity=45))
    assert phrase == Phrase(4, (Note(0, 76, 4, 45), Note(0, 79, 4, 45), Note(0, 83, 4, 45)))
    minor = replace(request(), context=MusicalContext(1, 'minor', 62, 'minor'))
    assert [note.pitch for note in generator(minor).notes] == [65, 69, 72]
    assert generator(replace(request(), dependencies={})).notes


def test_repeated_note_realization_uses_configurable_step_and_articulation():
    generator = TextureGenerator(settings={'realization': 'repeated_note',
                                           'step_beats': .5, 'articulation': .6})
    phrase = generator(request())
    assert phrase.notes == tuple(Note(beat, 60, .3, 85) for beat in (0, .5, 1, 1.5, 2, 2.5, 3, 3.5))


def test_chord_support_keeps_section_chord_tones_outside_source_register():
    generator = TextureGenerator(settings={'support_source': 1})
    phrase = generator(request(notes=(Note(0, 60, 4, 90),)))
    assert [note.pitch for note in phrase.notes] == [48, 52, 55]
    assert all(note.pitch % 12 in (0, 4, 7) for note in phrase.notes)


def test_follow_source_uses_salience_and_continuity_and_replanning_is_stable():
    generator = TextureGenerator(settings={'follow_source': 1, 'realization': 'repeated_note'})
    first = request(notes=(Note(0, 60, .1, 80), Note(1, 67, 3, 100)), realization='repeated_note')
    assert generator(first).notes[0].pitch == 67
    equal = request(start=4, notes=(Note(0, 60, 1, 90), Note(1, 67, 1, 90)),
                    realization='repeated_note')
    held = generator(equal)
    assert held.notes[0].pitch == 67
    assert generator(equal) == held
    assert generator.last_decision['source'] == 'melody'
    assert generator.last_decision['register'] == [60, 71]
    generator.reset()
    assert generator(equal).notes[0].pitch == 60
    generator(first)
    assert generator(replace(equal, start=20)).notes[0].pitch == 60


def test_follow_source_chords_change_at_melodic_notes_and_hold_until_the_next_change():
    generator = TextureGenerator(settings={'follow_source': 1, 'realization': 'chord'})
    phrase = request(notes=(Note(0, 60, 1, 85), Note(1, 64, 1, 85),
                           Note(2, 67, 1, 85), Note(3, 60, 1, 85)))

    result = generator(phrase)

    assert result.notes == (
        Note(0, 60, 1, 85), Note(0, 64, 1, 85), Note(0, 67, 1, 85),
        Note(1, 64, 1, 85), Note(1, 67, 1, 85), Note(1, 71, 1, 85),
        Note(2, 67, 1, 85), Note(2, 71, 1, 85), Note(2, 74, 1, 85),
        Note(3, 60, 1, 85), Note(3, 64, 1, 85), Note(3, 67, 1, 85),
    )
    assert generator.last_decision['chords'] == [
        {'beat': 0, 'pitches': [60, 64, 67]},
        {'beat': 1, 'pitches': [64, 67, 71]},
        {'beat': 2, 'pitches': [67, 71, 74]},
        {'beat': 3, 'pitches': [60, 64, 67]},
    ]


def test_switch_keeps_independent_mode_available_and_follows_source_silence():
    generator = TextureGenerator(settings={'realization': 'repeated_note'})
    source = request(notes=(Note(0, 67, 4, 100),))
    assert generator(source).notes[0].pitch == 60
    assert generator(replace(source, parameters={'follow_source': 1,
                                                  'realization': 'repeated_note'})).notes[0].pitch == 67
    assert not generator(request(4, follow_source=1, realization='repeated_note')).notes
    assert generator.last_decision['silence_reason'] == 'source_silent'
    assert generator(request(8, realization='repeated_note')).notes[0].pitch == 60
    assert not generator(replace(request(12, follow_source=1, realization='repeated_note'), dependencies={})).notes
    assert generator.last_decision['silence_reason'] == 'source_unavailable'


def test_follow_source_respects_register_and_reports_incompatible_inputs():
    generator = TextureGenerator()
    phrase = generator(request(notes=(Note(0, 48, 4, 90),), octave=1, follow_source=1,
                               realization='repeated_note'))
    assert phrase.notes[0].pitch == 72
    with pytest.raises(ValueError, match='una sola sorgente'):
        generator(replace(request(follow_source=1, realization='repeated_note'),
                          dependencies={'a': Phrase(4, ()), 'b': Phrase(4, ())}))
    with pytest.raises(ValueError, match='nessuna altezza sorgente'):
        generator(replace(request(notes=(Note(0, 60, 4, 90),), follow_source=1,
                               realization='repeated_note'),
                          context=MusicalContext(0, 'high', 126, 'major')))
    with pytest.raises(ValueError, match='registro MIDI'):
        generator(replace(request(octave=5), context=MusicalContext(0, 'high', 72, 'major')))


def test_support_source_avoids_overlapping_register_and_lightens_with_source_activity():
    generator = TextureGenerator(settings={'support_source': 1, 'realization': 'repeated_note'})
    phrase = generator(request(notes=(Note(0, 55, 2, 90), Note(2, 65, 2, 90)),
                               realization='repeated_note'))
    assert phrase.notes[0].pitch == 48 and phrase.notes[0].velocity == 1
    assert generator.last_decision['source_register'] == [55, 65]
    quieter = generator(request(start=4, notes=(Note(0, 55, 1, 90),), realization='repeated_note'))
    assert quieter.notes[0].pitch == 48 and quieter.notes[0].velocity == 64


def test_support_source_uses_independent_pitch_and_velocity_when_source_is_silent():
    generator = TextureGenerator(settings={'support_source': 1})
    phrase = generator(request())
    assert phrase == Phrase(4, (Note(0, 60, 4, 85), Note(0, 64, 4, 85), Note(0, 67, 4, 85)))
    assert generator.last_decision['source_register'] is None


def test_support_source_requires_single_dependency_and_reports_unavailable_source():
    generator = TextureGenerator(settings={'support_source': 1})
    with pytest.raises(ValueError, match='una sola sorgente'):
        generator(replace(request(), dependencies={'a': Phrase(4, ()), 'b': Phrase(4, ())}))
    assert not generator(replace(request(), dependencies={})).notes
    assert generator.last_decision['silence_reason'] == 'source_unavailable'


def test_support_source_is_silent_when_the_whole_register_is_contested():
    generator = TextureGenerator(settings={'support_source': 1, 'realization': 'repeated_note'})
    phrase = generator(request(notes=(Note(0, 0, 2, 100), Note(2, 127, 2, 100))))
    assert not phrase.notes
    assert generator.last_decision['silence_reason'] == 'register_contested'


@pytest.mark.parametrize('parameters', [{'follow_source': .5}, {'follow_source': True},
                                        {'follow_source': 2}, {'velocity': 0}, {'octave': 1.5},
                                        {'activity': .5}, {'support_source': 2},
                                        {'realization': 'arpeggio'}, {'step_beats': .1},
                                        {'articulation': 1.1},
                                        {'follow_source': 1, 'support_source': 1}])
def test_invalid_parameters_are_rejected(parameters):
    with pytest.raises(ValueError):
        TextureGenerator().validate('harmony', parameters)


def test_texture_registration_exposes_only_its_controls_and_saves_mode_in_presets():
    registered = build_generator({'type': 'sustained_texture', 'settings': {'octave': 1},
                                  'presets': {'coordinated': {'follow_source': 1}}})
    assert set(registered.controls) == {'octave', 'velocity', 'realization', 'step_beats', 'articulation',
                                        'follow_source', 'support_source'}
    assert registered.controls['follow_source'].toggle
    assert registered.controls['realization'].choices == (
        ('chord', 'accordi di sezione'), ('repeated_note', 'nota ripetuta'))
    assert registered.presets['coordinated']['follow_source'] == 1


def test_autonomous_harmonic_progression_cycles_degrees_and_retries_identically():
    generator = HarmonicProgressionGenerator(progressions(('test', [
        {'degree': 0, 'beats': 8}, {'degree': 5, 'beats': 8}, {'degree': 3, 'beats': 8},
    ])), {'articulation': 1})
    first = generator(request(0))
    second = generator(request(4))
    changed = generator(request(8))
    assert [note.pitch for note in first.notes] == [60, 64, 67]
    assert [note.pitch for note in second.notes] == [60, 64, 67]
    assert [note.pitch for note in changed.notes] == [69, 72, 76]
    assert generator(request(8)) == changed
    assert generator.last_decision['chords'] == [{'beat': 0, 'degree': 5, 'pitches': [69, 72, 76]}]


def test_autonomous_harmonic_progression_handles_changes_inside_a_window_and_resets_at_section():
    generator = HarmonicProgressionGenerator(progressions(('test', [
        {'degree': 0, 'beats': 2}, {'degree': 4, 'beats': 2},
    ])), {'articulation': 1})
    phrase = generator(request())
    assert phrase.notes == (
        Note(0, 60, 2, 85), Note(0, 64, 2, 85), Note(0, 67, 2, 85),
        Note(2, 67, 2, 85), Note(2, 71, 2, 85), Note(2, 74, 2, 85),
    )
    minor = replace(request(4), context=MusicalContext(1, 'minor', 62, 'minor'))
    assert [note.pitch for note in generator(minor).notes] == [62, 65, 69, 69, 72, 76]


@pytest.mark.parametrize('catalog', [[], [dict(id='a', label='a', steps=[{'degree': 0}])],
                                      [dict(id='a', label='a', steps=[{'degree': -1, 'beats': 1}])],
                                      [dict(id='a', label='a', steps=[{'degree': 0, 'beats': 0}])],
                                      [dict(id='a', label='a', steps=[{'degree': 0, 'beats': 1, 'x': 2}])],
                                      [dict(id='a', label='a', steps=[]), dict(id='a', label='b', steps=[{'degree': 0, 'beats': 1}])]])
def test_autonomous_harmonic_progression_rejects_invalid_catalog(catalog):
    with pytest.raises(ValueError):
        HarmonicProgressionGenerator(catalog)


def test_harmonic_progression_registration_exposes_only_performance_controls():
    registered = build_generator({'type': 'harmonic_progression',
                                  'progressions': progressions(('test', [
                                      {'degree': 0, 'beats': 8}, {'degree': 4, 'beats': 8},
                                  ]))})
    assert set(registered.controls) == {'progression', 'octave', 'velocity', 'articulation'}
    assert registered.controls['progression'].choices == (('test', 'test'),)
    assert registered.generator.supported_roles == ('harmony',)


def test_autonomous_harmonic_progression_switches_catalog_entry_at_the_next_window():
    generator = HarmonicProgressionGenerator(progressions(
        ('first', [{'degree': 0, 'beats': 8}]), ('second', [{'degree': 4, 'beats': 8}]),
    ), {'articulation': 1})
    generator(request())
    switched = generator(request(4, progression='second'))
    assert [note.pitch for note in switched.notes] == [67, 71, 74]
    assert generator.last_decision['progression'] == 'second'
