"""Catalogo percussivo e comportamento nella sessione multivoce."""
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from desnivel.cli.generators import build_generator, percussion_definition
from desnivel.music.patterns import SCALES
from desnivel.music.percussion.catalog import MATERIAL_BY_ID, STYLE_BY_ID, HIT_ROLES
from desnivel.adapters.percussion import PAD_NOTES


def configuration(name):
    config = json.loads(Path('tests/fixtures/transport_runtime_session.json').read_text())
    config['generators']['percussion'] = json.loads(Path('tests/fixtures/percussion_phrase.json').read_text())
    config['voices']['voice_04'] = {
        'name': 'Drums', 'generator': 'percussion', 'destination': 'device_04',
        'dependencies': ['voice_01'], 'optional_dependencies': ['voice_02'],
    }
    config['rhythm_voice'] = 'voice_04'
    config['history_beats'] = 64
    config['relations'] = [{
        'id': 'drums_to_melody', 'source': 'voice_04', 'target': 'voice_01',
        'scope': 'history', 'aspects': ['rhythm'], 'roles': ['melody'],
        'lookback_beats': 32, 'fragment_beats': 4, 'strength': .4,
        'on_unavailable': 'independent',
    }]
    for section in config['sections']:
        section['assignments']['voice_04'] = {'role': 'rhythm'}
    config['generators']['motif']['settings']['groove_follow'] = .3
    config['generators']['accompaniment']['settings']['groove_follow'] = .7
    if name == 'dialogo':
        config['generators']['percussion'].update(material='spaced_dialogue', standard_material='regular_pulse_offbeats')
        config['generators']['percussion']['settings']['displacement_beats'] = .25
        config['generators']['atmosphere']['settings']['follow_source'] = 1
        config['sections'] = [dict(name='dialogue', from_progress=0, root=57, scale='dorian',
                                   assignments={n: {'role': r} for n, r in zip(config['voices'],
                                                ('melody', 'bass_line', 'harmony', 'rhythm'))})]
    return config


def capture_session_output(config, style):
    from desnivel.music.session import EnsembleSession
    generators = {key: build_generator(value).generator for key, value in config['generators'].items()}
    destinations = {v['destination']: lambda *args: None for v in config['voices'].values()}
    session = EnsembleSession(config, generators, destinations)
    result = []
    for i in range(32):
        session.set_parameters('voice_04', {'style': style, 'variation': .7, 'displacement_beats': .25})
        phrases = session.plan(i/32, i*4, 4)
        result.append({'phrases': {name: asdict(phrase) for name, phrase in phrases.items()},
                       'rhythm': session.coordinator.last_plan['rhythm']})
    return result


@pytest.mark.parametrize('name', ('organico', 'dialogo'))
def test_ensemble_output_keeps_the_arrangement_and_scale_of_each_section(name):
    output = capture_session_output(configuration(name), 'house_classic')
    assert len(output) == 32
    for index, window in enumerate(output):
        phrases = window['phrases']
        assert {'voice_01', 'voice_03', 'voice_04'} <= set(phrases)
        if name == 'organico' and index < 10:
            assert 'voice_02' not in phrases
            scale = 'minor'
        elif name == 'organico' and index < 24:
            assert 'voice_02' in phrases
            scale = 'dorian'
        elif name == 'organico':
            assert 'voice_02' in phrases
            scale = 'minor'
        else:
            assert 'voice_02' in phrases
            scale = 'dorian'
        allowed = {(57+interval) % 12 for interval in SCALES[scale]}
        for voice in ('voice_01', 'voice_02'):
            if voice in phrases:
                assert all(note['pitch'] % 12 in allowed for note in phrases[voice]['notes'])
        for phrase in phrases.values():
            assert phrase['length_beats'] == 4
            assert all(0 <= note['beat'] < 4 and 0 < note['duration'] <= 4-note['beat']
                       for note in phrase['notes'])


@pytest.mark.parametrize('name', ('organico', 'dialogo'))
def test_ensemble_percussion_style_changes_its_realization(name):
    plain = capture_session_output(configuration(name), 'none')
    styled = capture_session_output(configuration(name), 'house_classic')
    assert [window['phrases']['voice_04'] for window in plain] != [
        window['phrases']['voice_04'] for window in styled
    ]


def test_all_materials_have_known_roles_and_unique_explicit_identifiers():
    assert set(PAD_NOTES) == set(HIT_ROLES)
    assert len(set(PAD_NOTES.values())) == len(PAD_NOTES)
    assert len(MATERIAL_BY_ID) == 4
    for name, material in MATERIAL_BY_ID.items():
        assert material.name == name
        assert {hit.role for hit in material.hits} <= set(HIT_ROLES)
    assert MATERIAL_BY_ID['regular_pulse_eighths'].hits != MATERIAL_BY_ID['regular_pulse_offbeats'].hits
    for style in STYLE_BY_ID.values():
        assert {hit.role for variant in style.variants for hit in variant} <= set(HIT_ROLES)


@pytest.mark.parametrize('field,value', [('material','missing'), ('material',{}),
                                        ('standard_material','missing'), ('lanes',{'kick':36}),
                                        ('style_lanes',{'kick':'kick'})])
def test_unknown_references_and_inline_definitions_are_rejected(field, value):
    spec = configuration('organico')['generators']['percussion']
    spec[field] = value
    with pytest.raises(ValueError):
        build_generator(spec)


def test_resolving_a_material_never_mutates_the_catalog():
    spec = configuration('organico')['generators']['percussion']
    first = percussion_definition(spec)
    first['material']['hits'][0]['velocity'] = 1
    first['lanes']['kick'] = 1
    second = percussion_definition(spec)
    assert second['material']['hits'][0]['velocity'] != 1
    assert second['lanes']['kick'] == 36
