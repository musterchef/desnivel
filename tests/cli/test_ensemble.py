import json

import pytest

from desnivel.music.session import EnsembleSession, Generator
from desnivel.music.bass.generator import generate_bass, BassSettings
from desnivel.music.phrases import Note, Phrase


def config():
    # Passaggio JSON: nessun oggetto Python incorporato nella configurazione.
    return json.loads('''{
      "selection_mode": "manual",
      "voices": {
        "a": {"generator": "source", "destination": "out_a"},
        "b": {"generator": "accompaniment", "destination": "out_b", "dependencies": ["a"]}
      },
      "sections": [
        {"name": "opening", "from_progress": 0, "root": 60, "scale": "major",
         "assignments": {"a": {"role": "melody", "parameters": {"velocity": 70}}}},
        {"name": "development", "from_progress": 0.5, "root": 62, "scale": "minor",
         "assignments": {"a": {"role": "melody", "parameters": {"velocity": 100}},
                         "b": {"role": "bass_line", "parameters": {"density": 0.5}}}}
      ]
    }''')


def setup(data=None):
    calls, sent = [], []

    def source(request):
        calls.append(('a', request))
        return Phrase(request.length_beats, (
            Note(0, request.context.root, 1, request.parameters['velocity']),))

    def accompaniment(request):
        calls.append(('b', request))
        return generate_bass(request.dependencies['a'], BassSettings(**request.parameters))

    generators = {
        'source': Generator(source, ('melody',)),
        'accompaniment': Generator(accompaniment, ('bass_line',)),
    }
    destinations = {
        'out_a': lambda start, phrase: sent.append(('a', start, phrase)),
        'out_b': lambda start, phrase: sent.append(('b', start, phrase)),
    }
    return EnsembleSession(data or config(), generators, destinations), calls, sent


def test_sections_change_active_voices_context_and_parameters_and_route_results():
    session, calls, sent = setup()
    opening = session.plan(0, 0, 4)
    assert set(opening) == {'a'}
    assert opening['a'].notes[0] == Note(0, 60, 1, 70)
    assert not sent
    development = session.plan(.5, 4, 4)
    assert set(development) == {'a', 'b'}
    assert development['a'].notes[0] == Note(0, 62, 1, 100)
    assert development['b'].notes
    assert [name for name, _ in calls] == ['a', 'a', 'b']
    assert calls[-1][1].dependencies['a'] is development['a']
    assert calls[-1][1].role == 'bass_line'
    session.send(4, development)
    assert sent == [('a', 4, development['a']), ('b', 4, development['b'])]
    # Tornare alla prima sezione non conserva le voci della seconda.
    assert set(session.plan(.1, 8, 4)) == {'a'}


def test_presence_controls_whole_phrases_and_dependencies_hear_the_actual_silence():
    session, calls, _ = setup()
    session.set_presence_multiplier('a', 0)
    result = session.plan(.5, 0, 4)
    assert not result['a'].notes
    assert calls[-1][1].dependencies['a'] is result['a']
    assert not result['b'].notes
    decision = session.coordinator.last_plan['voices']['a']
    assert decision['presence'] == 0 and not decision['participating']
    # Il generatore continua a ricevere le richieste anche se la voce è silenziosa.
    assert [name for name, _ in calls] == ['a', 'b']
    session.set_presence_multiplier('a', 1)
    assert session.plan(.5, 4, 4)['a'].notes


def test_automatic_presence_and_multiplier_are_separate_and_follow_section_changes():
    data = config()
    data['sections'][0]['assignments']['a']['presence'] = .4
    data['sections'][1]['assignments']['a']['presence'] = .7
    session, _, _ = setup(data)
    session.set_presence_multiplier('a', 2)
    assert session.presence_state('a', 0) == dict(automatic=.4, multiplier=2, effective=.8)
    assert session.presence_state('a', .5) == dict(automatic=.7, multiplier=2, effective=1)
    assert session.presence_state('b', 0) == dict(automatic=0, multiplier=1, effective=0)
    session.set_presence_multiplier('b', 10)
    assert session.presence_state('b', 0)['effective'] == 0
    assert 'b' not in session.plan(0, 0, 4)


@pytest.mark.parametrize('value', [-1, 1.1, float('nan'), True, '0.5'])
def test_invalid_automatic_presence_is_rejected(value):
    data = config()
    data['sections'][0]['assignments']['a']['presence'] = value
    with pytest.raises(ValueError, match='presence'):
        setup(data)


@pytest.mark.parametrize('value', [-1, 10.1, float('inf'), True, '1'])
def test_invalid_presence_multiplier_does_not_change_the_value(value):
    session, _, _ = setup()
    with pytest.raises(ValueError, match='moltiplicatore'):
        session.set_presence_multiplier('a', value)
    assert session.presence_state('a', 0)['multiplier'] == 1


def test_partial_presence_is_repeatable_and_does_not_thin_the_notes_inside_a_phrase():
    data = config()
    data['sections'][0]['assignments']['a']['presence'] = .4
    session, _, _ = setup(data)
    results = [session.plan(0, i*4, 4)['a'] for i in range(1000)]
    assert 330 < sum(bool(p.notes) for p in results) < 470
    assert results == [session.plan(0, i*4, 4)['a'] for i in range(1000)]
    assert all(p.length_beats == 4 and len(p.notes) in (0, 1) for p in results)


@pytest.mark.parametrize('failure', ['unsupported_role', 'inactive_dependency', 'cycle'])
def test_invalid_sections_rejected_during_loading(failure):
    data = config()
    assignments = data['sections'][1]['assignments']
    if failure == 'unsupported_role':
        assignments['a']['role'] = 'pulse'
    elif failure == 'inactive_dependency':
        del assignments['a']
    else:
        data['voices']['a']['dependencies'] = ['b']
    with pytest.raises(ValueError):
        setup(data)


def test_configuration_is_copied_and_request_parameters_cannot_be_replaced():
    data = config()
    session, calls, _ = setup(data)
    data['sections'][0]['assignments']['a']['parameters']['velocity'] = 120
    assert session.plan(0, 0, 4)['a'].notes[0].velocity == 70
    with pytest.raises(TypeError):
        calls[0][1].parameters['velocity'] = 1


def test_load_json_file_and_deliver_phrase(tmp_path):
    path = tmp_path / 'ensemble.json'
    data = config()
    del data['voices']['b']
    data['sections'] = data['sections'][:1]
    path.write_text(json.dumps(data))
    sent = []
    phrase = Phrase(4, (Note(0, 60, 1, 70),))
    session = EnsembleSession.from_file(
        path, {'source': Generator(lambda request: phrase, ('melody',))},
        {'out_a': lambda start, result: sent.append((start, result))})
    session.send(8, session.plan(0, 8, 4))
    assert sent == [(8, phrase)]


@pytest.mark.parametrize('optional', [['missing'], ['b', 'b'], ['a']])
def test_invalid_optional_dependencies_are_rejected(optional):
    data = config()
    data['voices']['b']['optional_dependencies'] = optional
    with pytest.raises(ValueError, match='facoltative'):
        setup(data)
