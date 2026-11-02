import pytest

from desnivel.music.observation import MusicalMemory
from desnivel.music.phrases import Note, Phrase


def test_missing_history_silence_and_unassigned_voice_are_distinct():
    memory = MusicalMemory()
    initial = memory.before(8, ('a', 'b'))
    assert initial.available_beats == 0
    assert initial.voices['a'].attacks_per_beat is None
    memory = memory.accepted(8, 4, {'a': Phrase(4, ())})
    observation = memory.before(12, ('a', 'b'))
    assert observation.available_beats == 4
    assert observation.voices['a'].attacks_per_beat == 0
    assert observation.voices['a'].occupied_ratio == 0
    assert observation.voices['a'].assigned_beats == 4
    assert observation.voices['b'].assigned_beats == 0


def test_long_notes_polyphony_and_attacks_use_distinct_measures():
    memory = MusicalMemory().accepted(0, 4, {'a': Phrase(4, (
        Note(0, 60, 4, 80), Note(1, 67, 2, 80), Note(2, 72, 1, 80)))})
    voice = memory.before(4, ('a',)).voices['a']
    assert voice.attacks == 3 and voice.attacks_per_beat == .75
    assert voice.occupied_ratio == 1
    assert voice.register == (60, 72)


def test_history_is_clipped_to_16_beats_and_uses_only_accepted_past():
    memory = MusicalMemory().accepted(0, 20, {'a': Phrase(20, (
        Note(0, 60, 10, 80), Note(5, 67, 1, 80), Note(19, 72, 1, 80)))})
    assert memory.before(19, ('a',)).available_beats == 0
    observation = memory.before(20, ('a',))
    assert observation.start_beat == 4 and observation.available_beats == 16
    voice = observation.voices['a']
    assert voice.attacks == 2  # La nota che inizia prima dell'intervallo non è un nuovo attacco.
    assert voice.occupied_ratio == 7/16
    assert voice.register == (60, 72)
    assert memory.before(40, ('a',)).available_beats == 0
    with pytest.raises(TypeError):
        observation.voices['b'] = voice


def test_gap_does_not_become_observed_silence_and_phrases_are_reused():
    phrase = Phrase(4, (Note(0, 60, 1, 80),))
    memory = MusicalMemory().accepted(4, 4, {'a': phrase}).accepted(12, 4, {'a': phrase})
    assert memory.windows[-1].phrases['a'] is phrase
    observation = memory.before(16, ('a',))
    assert observation.available_beats == 8
    assert observation.voices['a'].attacks_per_beat == .25
    assert observation.to_dict()['coverage_ratio'] == .5
