import pytest

from desnivel.music.coordinator import PlanningRequest
from desnivel.music.director import MusicalContext
from desnivel.music.melodic.generator import MotifGenerator
from desnivel.music.texture.generator import TextureGenerator


def request(role='melody', start=0, **parameters):
    return PlanningRequest(start, 4, MusicalContext(0, 'test', 60, 'major'), {}, role, parameters)


def test_melody_continues_motif_and_texture_sustains_one_note():
    generator = MotifGenerator([0, 2, 4, 1, 3, 2])
    assert [n.pitch for n in generator(request()).notes] == [60, 64, 67, 62]
    assert [n.pitch for n in generator(request(start=4)).notes] == [65, 64, 60, 64]
    held = generator(request('sustained_texture'))
    assert len(held.notes) == 1 and held.notes[0].duration == 4
    low = generator(request('bass_line', octave=-2))
    assert [n.pitch for n in low.notes] == [36, 40, 43, 38]


def test_motif_sustained_role_matches_texture_generator_for_equivalent_inputs():
    motif = MotifGenerator([2, 4, 1])
    texture = TextureGenerator(2)
    for start in (0, 4, 8):
        req = request('sustained_texture', start=start, octave=1, velocity=70)
        assert motif(req) == texture(req)


def test_no_silent_unknown_controls_or_out_of_range_notes():
    generator = MotifGenerator([0, 7])
    with pytest.raises(ValueError):
        generator(request(unknown=1))
    with pytest.raises(ValueError):
        generator(request(octave=5))


def test_development_retains_identity_builds_period_and_is_reproducible():
    settings = dict(development=.7, activity=.75, phrase_windows=4, seed=7)
    a = MotifGenerator([0, 2, 4, 1, 3, 2, 1, 0], settings)
    b = MotifGenerator([0, 2, 4, 1, 3, 2, 1, 0], settings)
    phrases, phases, cells, endings = [], [], [], []
    for i in range(24):
        req = request(start=4+i*4)
        phrase = a(req)
        assert phrase == b(req)
        phrases.append(phrase)
        phases.append(a.last_decision['phase'])
        cells.append(a.last_decision['cell'])
        endings.append(a.last_decision['ending'])
        assert [n.pitch for n in phrase.notes[:len(a.last_decision['anchor_pitches'])]] == a.last_decision['anchor_pitches']
    assert phases[0] == 'statement'
    assert {'recall', 'continuation'} <= set(phases)
    assert set(cells) == {0, 1}
    assert not any(a == b == c for a, b, c in zip(cells, cells[1:], cells[2:]))
    assert any(endings[i] != 'tonic' for i in range(3, len(endings), 4))
    assert len({tuple(n.pitch for n in p.notes) for p in phrases}) > 8
    assert len({tuple(n.beat for n in p.notes) for p in phrases}) > 1
    pitches = [n.pitch for p in phrases for n in p.notes]
    assert max(abs(x-y) for x,y in zip(pitches,pitches[1:])) <= 7
    assert all(n.pitch % 12 in (0,2,4,5,7,9,11) for p in phrases for n in p.notes)
    assert len({n.velocity for p in phrases for n in p.notes}) > 3
    assert any(sum(n.duration for n in p.notes) < 3 for p in phrases)


def test_restart_begins_statement_and_seed_changes_development():
    a = MotifGenerator([0, 2, 4, 1], dict(development=.8, seed=1))
    first = a(request(start=100))
    assert a.last_decision['phase'] == 'statement'
    a(request(start=104))
    a.reset()
    assert a(request(start=4)) == first
    b = MotifGenerator([0, 2, 4, 1], dict(development=.8, seed=2))
    assert b(request(start=4)) != first


def test_development_expresses_scale_colour_and_literal_mode_is_unchanged():
    from desnivel.music.coordinator import PlanningRequest
    minor = MotifGenerator([0,2,4,1,3,2,1,0], dict(development=.7, seed=7))
    dorian = MotifGenerator([0,2,4,1,3,2,1,0], dict(development=.7, seed=7))
    minor_notes, dorian_notes = [], []
    for i in range(16):
        base = request(start=i*4)
        minor_notes += list(minor(PlanningRequest(base.start,4,MusicalContext(0,'test',60,'minor'),{},'melody',{})).notes)
        dorian_notes += list(dorian(PlanningRequest(base.start,4,MusicalContext(0,'test',60,'dorian'),{},'melody',{})).notes)
    assert any(n.pitch % 12 == 8 for n in minor_notes)
    assert any(n.pitch % 12 == 9 for n in dorian_notes)
    assert [n.pitch for n in minor_notes] != [n.pitch for n in dorian_notes]
    literal = MotifGenerator([0,2,4,1])
    assert literal(request(start=0)) == literal(request(start=4))
