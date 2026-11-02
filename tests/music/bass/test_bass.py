import pytest
from dataclasses import replace

from desnivel.music.bass.generator import BassSettings, generate_bass
from desnivel.music.phrases import Note, Phrase
from desnivel.cli.compose_bass import main


def test_bass_preserves_attacks_classes_and_silence():
    melody = Phrase(4, (Note(0,60,.5,100), Note(.25,67,.25,80), Note(2,62,1,90)))
    bass = generate_bass(melody, BassSettings(strategy="follow"))
    assert [n.beat for n in bass.notes] == [0,2]
    assert [n.pitch % 12 for n in bass.notes] == [0,2]
    assert bass.notes[0].beat+bass.notes[0].duration < 2
    assert all(28 <= n.pitch <= 47 for n in bass.notes)
    assert generate_bass(Phrase(4,())).notes == ()


def test_density_register_and_continuity_are_configurable():
    melody = Phrase(2, (Note(0,60,1,100), Note(.5,62,1,100)))
    bass = generate_bass(melody, BassSettings(36,59,.25,1,1,strategy="follow"), previous_pitch=50)
    assert [n.pitch for n in bass.notes] == [48,50]
    assert bass.notes[0].duration == .5
    assert bass.notes[1].velocity == 100


def test_cli_generates_readable_phrase_and_refuses_overwrite(tmp_path):
    source = tmp_path/'melody.json'
    source.write_text('{"length_beats":4,"notes":[{"beat":0,"pitch":60,"duration":1,"velocity":90}]}')
    output = tmp_path/'bass.json'
    assert main(['--melody',str(source),'--output',str(output)]) == 0
    import json
    bass = Phrase.from_dict(json.loads(output.read_text()))
    assert bass.notes[0].pitch % 12 == 0
    with pytest.raises(SystemExit):
        main(['--melody',str(source),'--output',str(output)])


def test_responsive_varies_phrases_but_is_repeatable():
    melody=Phrase(4,tuple(Note(i*.5,[60,64,67,62][i%4],.2,100) for i in range(8)))
    phrases=[generate_bass(melody,phrase_index=i) for i in range(4)]
    assert len(set(p.notes for p in phrases))>1
    assert phrases[2]==generate_bass(melody,phrase_index=2)
    assert phrases[0]!=generate_bass(melody,phrase_index=4)
    assert any(n.duration>.2 for p in phrases for n in p.notes)
    for p in phrases:
        assert all(n.pitch%12 in {0,2,4,7} and 28<=n.pitch<=47 for n in p.notes)
        assert all(a.beat+a.duration<=b.beat for a,b in zip(p.notes,p.notes[1:]))
        assert all(n.beat+n.duration<=4 for n in p.notes)


def test_responsive_handles_silence_and_single_note_without_inventing_harmony():
    assert generate_bass(Phrase(4,())).notes==()
    melody=Phrase(4,(Note(1,61,.1,70),))
    bass=generate_bass(melody)
    assert bass.notes[0].beat==1
    assert all(n.pitch%12==1 for n in bass.notes)


def test_responsive_density_and_dynamics_are_controls():
    melody=Phrase(4,tuple(Note(i*.25,60+i%5,.2,100) for i in range(16)))
    sparse=generate_bass(melody,BassSettings(min_spacing=2))
    dense=generate_bass(melody,BassSettings(min_spacing=.5))
    assert len(dense.notes)>len(sparse.notes)
    assert len({n.velocity for n in dense.notes})>1


def test_presets_are_values_and_explicit_controls_override_them():
    melody = Phrase(4, tuple(Note(i * .5, 60, .2, 90) for i in range(8)))
    settings = BassSettings(highest=59, strategy='slap')
    # Cambiare il nome senza cambiare valori non cambia il generatore.
    assert generate_bass(melody, settings) == generate_bass(
        melody, replace(settings, strategy='responsive'))
    quiet = generate_bass(melody, BassSettings(strategy='slap', density=0))
    assert quiet.notes == ()
    assert BassSettings(strategy='slap', min_spacing=2).min_spacing == 2


def test_session_bass_rejects_initial_preset_selector_as_runtime_parameter():
    from desnivel.cli.generators import build_generator
    registered = build_generator({'type': 'responsive_line', 'settings': {'strategy': 'slap'}})
    assert registered.values['density'] == 1.8
    with pytest.raises(ValueError, match='soltanto in settings'):
        registered.generator.validate('bass_line', {'strategy': 'responsive'})
    registered.generator.validate('bass_line', {'lowest': 24, 'density': .5})


def test_density_reports_saturation_without_changing_the_composed_phrase():
    from desnivel.music.bass.generator import plan_bass
    melody = Phrase(4, tuple(Note(i, 60, .2, 90) for i in range(4)))
    settings = BassSettings(rhythm_follow=1, min_spacing=1, variation=0, density=1.8)
    phrase, density = plan_bass(melody, settings)
    assert phrase == generate_bass(melody, replace(settings, density=1))
    assert density['selected_attacks'] == density['capacity_attacks'] == 4
    assert density['saturated'] is True
    sparse, density = plan_bass(melody, replace(settings, density=.5))
    assert len(sparse.notes) == density['selected_attacks'] == 2
    assert density['capacity_attacks'] == 4 and density['saturated'] is False


def test_density_above_one_can_still_matter_in_a_short_interval():
    from desnivel.music.bass.generator import plan_bass
    melody = Phrase(3.2, tuple(Note(i, 60, .1, 90) for i in range(4)))
    settings = BassSettings(rhythm_follow=1, min_spacing=1, variation=0, density=1)
    first, _ = plan_bass(melody, settings)
    second, density = plan_bass(melody, replace(settings, density=1.2))
    assert len(first.notes) == 3 and len(second.notes) == 4
    assert density['capacity_attacks'] == 4 and density['active_beats'] == 3.2


def test_density_and_syncopation_control_different_dimensions():
    melody = Phrase(4, (Note(0, 60, 4, 100),))
    settings = BassSettings(density=.75, min_spacing=.5, rhythm_follow=0,
                            syncopation=0, variation=0)
    straight = generate_bass(melody, settings)
    syncopated = generate_bass(melody, replace(settings, syncopation=1))
    dense = generate_bass(melody, replace(settings, density=2))
    assert len(straight.notes) == len(syncopated.notes) == 3
    assert all(n.beat % 1 == 0 for n in straight.notes)
    assert sum(n.beat % 1 != 0 for n in syncopated.notes) == 2
    assert len(dense.notes) == 8


def test_rhythmic_and_melodic_links_are_independent():
    melody = Phrase(4, (Note(.25, 60, .1, 100), Note(1.25, 62, .1, 100),
                        Note(2.25, 67, .1, 100), Note(3.25, 64, .1, 100)))
    settings = BassSettings(density=4, min_spacing=.25, rhythm_follow=1,
                            melody_follow=1, variation=0)
    bass = generate_bass(melody, settings)
    assert [n.beat for n in bass.notes] == [n.beat for n in melody.notes]
    assert [n.pitch % 12 for n in bass.notes] == [n.pitch % 12 for n in melody.notes]
    independent_rhythm = generate_bass(melody, replace(settings, rhythm_follow=0))
    assert any(n.beat not in {m.beat for m in melody.notes} for n in independent_rhythm.notes)
    assert all(n.pitch % 12 in {0, 2, 7, 4} for n in independent_rhythm.notes)


def test_mobility_opens_octave_responses_without_forcing_them():
    melody = Phrase(4, (Note(0, 60, 4, 100),))
    settings = BassSettings(lowest=36, highest=59, density=2, min_spacing=.5,
                            rhythm_follow=0, melody_follow=1, mobility=0, variation=0)
    stable = generate_bass(melody, settings, previous_pitch=36)
    mobile = generate_bass(melody, replace(settings, mobility=1), previous_pitch=36)
    assert {n.pitch for n in stable.notes} == {36}
    assert {n.pitch for n in mobile.notes} == {36, 48}
    assert all(b.pitch - a.pitch == 12 for a, b in zip(mobile.notes[::2], mobile.notes[1::2]))


def test_variation_zero_is_stable_and_nonzero_is_reproducible():
    melody = Phrase(4, tuple(Note(i * .5, 60 + i % 3, .2, 90) for i in range(8)))
    settings = BassSettings(strategy='slap', highest=59, variation=0)
    assert generate_bass(melody, settings, phrase_index=0) == generate_bass(melody, settings, phrase_index=7)
    varied = replace(settings, variation=1)
    phrases = [generate_bass(melody, varied, phrase_index=i) for i in range(8)]
    assert len({p.notes for p in phrases}) > 1
    assert phrases[5] == generate_bass(melody, varied, phrase_index=5)


@pytest.mark.parametrize('control,value', [
    ('density', -1), ('density', float('inf')), ('syncopation', 1.01),
    ('rhythm_follow', -.1), ('melody_follow', float('nan')),
    ('mobility', 2), ('variation', -1), ('min_spacing', 0),
])
def test_invalid_controls_are_rejected(control, value):
    with pytest.raises(ValueError):
        BassSettings(**{control: value})


def test_cli_accepts_preset_alias_and_overrides(tmp_path):
    import json
    source = tmp_path / 'melody.json'
    source.write_text('{"length_beats":4,"notes":[{"beat":0,"pitch":60,"duration":4,"velocity":90}]}')
    for option in ('--preset', '--strategy'):
        output = tmp_path / (option + '.json')
        assert main(['--melody', str(source), '--output', str(output), option, 'slap',
                     '--density', '0', '--syncopation', '.3']) == 0
        assert json.loads(output.read_text())['notes'] == []


def test_interpolated_controls_preserve_register_and_endpoints():
    from desnivel.music.bass.generator import interpolate_settings
    first = BassSettings(lowest=29, highest=40, density=.5, mobility=0)
    last = BassSettings(lowest=37, highest=48, density=1.5, mobility=1)
    assert interpolate_settings(first, last, 0) == first
    assert interpolate_settings(first, last, 1) == last
    middle = interpolate_settings(first, last, .5)
    assert middle.density == 1 and middle.mobility == .5
    assert middle.highest - middle.lowest >= 11
    with pytest.raises(ValueError):
        interpolate_settings(first, last, float('nan'))


@pytest.mark.parametrize('preset', ['responsive', 'follow', 'slap'])
def test_all_presets_respect_limits_with_explicit_controls(preset):
    melody = Phrase(3.7, (Note(.2, 60, .15, 70), Note(1.3, 61, .6, 110),
                          Note(3.1, 67, .2, 90)))
    settings = BassSettings(strategy=preset, lowest=40, highest=51,
                            density=3, min_spacing=.3, grid=.25,
                            articulation=1, max_hold=.7, variation=.8)
    bass = generate_bass(melody, settings, phrase_index=13)
    assert bass.notes
    assert all(40 <= n.pitch <= 51 and n.pitch % 12 in {0, 1, 7} for n in bass.notes)
    assert all(0 < n.duration <= .7 and n.beat + n.duration <= 3.7 for n in bass.notes)
    assert all(b.beat - a.beat >= .3 - 1e-9 and a.beat + a.duration <= b.beat
               for a, b in zip(bass.notes, bass.notes[1:]))
    assert generate_bass(Phrase(4, ()), settings).notes == ()
