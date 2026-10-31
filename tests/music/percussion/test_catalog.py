"""Identità musicale rispetto al motore prima della centralizzazione."""
import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from desnivel.cli.generators import build_generator, percussion_definition
from desnivel.music.coordinator import PlanningRequest
from desnivel.music.phrases import Note, Phrase
from desnivel.music.percussion.catalog import MATERIAL_BY_ID, STYLE_BY_ID, HIT_ROLES
from desnivel.adapters.percussion import PAD_NOTES


PERCUSSION_BEFORE = {
    ('organico', 'none', 0): '4d2e139615ebfb376dd0cc486f867eb6869c09cd87a6e65fd2baf6b0fa30ce9b',
    ('organico', 'none', 0.5): 'b5f5d69a9f1eb4582dcb74e0823210b5b5aca304a4d4b1404f9444fd14495118',
    ('organico', 'none', 1): '1437f3d8aeed2336542a1c095d84aa6eff274c8fd683d5b3304b6a078249a79f',
    ('organico', 'house_classic', 0): '01488c956b22146ab0d7ec8003db387fff2472f3e22179e7f62a0ee006ce3125',
    ('organico', 'house_classic', 0.5): '914845ad6ec257217cab14617bb249d0f23e7806a3780955b34bcf5f0dfb45c5',
    ('organico', 'house_classic', 1): '9a19012ef38b46c146b5e46fc1b737514369dab8cb3cf6a887fa516dcda65bd0',
    ('organico', 'boom_bap_90s', 0): '8e387abb336bca0d1ada405d1e197664b8056a7be6f87436bc495cb9fd36a9d8',
    ('organico', 'boom_bap_90s', 0.5): 'f6b22a9ea2fdd89c1d0171ced5993f7273f82f168e28dee2314b9d9716987751',
    ('organico', 'boom_bap_90s', 1): '7d5d5f75466f8ca8be392d8fff9412a95f41ac3b7ad0be561e5a6556f1df659f',
    ('organico', 'breakbeat_house', 0): '6ed0c0dcb5531824cd148dbc9784bc12ea7057f3e356fcbf60b376342ac314ec',
    ('organico', 'breakbeat_house', 0.5): '1473b3e89d6a2e7bbed08c3748bb6c24189b454302ade4206dc33e146a6e3570',
    ('organico', 'breakbeat_house', 1): '885abef24c8624a73bb60ada0974731d74a5ab8dabb2e83ca66f43c1ad613507',
    ('dialogo', 'none', 0): '16f081031ae8971d82c3a27e381a459a9898247078d11d189ab369399ba8f52c',
    ('dialogo', 'none', 0.5): 'ec24d33f789fd74f99bf43d02e08e1255847e22f9dba3adf065d4ea489fc48e7',
    ('dialogo', 'none', 1): '23f81215b4d1895c7c7d8f00ba0bafb3f7e9d23ae5535a2339cbe2515394fc45',
    ('dialogo', 'house_classic', 0): '01488c956b22146ab0d7ec8003db387fff2472f3e22179e7f62a0ee006ce3125',
    ('dialogo', 'house_classic', 0.5): '8bd298a028a7ac19ca4ecb2a494195c5e2423afb053206dc471422051d069594',
    ('dialogo', 'house_classic', 1): '3802b0c8ce3c506868c0f4c9d827bbfda6d201e104f8a518fbe9ca28fe9b3e1c',
    ('dialogo', 'boom_bap_90s', 0): '8e387abb336bca0d1ada405d1e197664b8056a7be6f87436bc495cb9fd36a9d8',
    ('dialogo', 'boom_bap_90s', 0.5): 'ea5f4579c2343f3e4ddb21ffd996595894ed8ce9c3a9e849b54b8fe6712ceb41',
    ('dialogo', 'boom_bap_90s', 1): '5eecf6810fcdd7a539ae9eb075166b20d8d20872847401380c396a9b060cffdc',
    ('dialogo', 'breakbeat_house', 0): '6ed0c0dcb5531824cd148dbc9784bc12ea7057f3e356fcbf60b376342ac314ec',
    ('dialogo', 'breakbeat_house', 0.5): 'f2d4a54ddbeb4c3b9bae039bb4f8a0a83e8ea2b2512fd1f18f865074bc5c5819',
    ('dialogo', 'breakbeat_house', 1): 'fbca764a322d7f9fd074406c7ffdf0a7b5a4d12cd7cba366744efe085ff6c2bc',
}

SESSIONS_BEFORE = {
    ('organico', 'none'): 'f22d64c342d5874d3e26a9974a0bd753e4ff5c070fa130f3b0d592ddb3431c6f',
    ('organico', 'house_classic'): 'a9b59c883446e936b386181c8a5c1f0ec784d0c704473067dab74a5bda755f2e',
    ('organico', 'boom_bap_90s'): '6de83afad643df351f113a8cf8a501e0246490de73ddac841a3a1286e8230fe0',
    ('organico', 'breakbeat_house'): 'd29482d738e2aa7e1bda92258bcffcc2a0bd5aa9f47d7fa1eec3e31eaadeabc7',
    ('dialogo', 'none'): 'cf0b938334d4fef8df0adff396e4ef27052670f85893ed5f08f578a6a5200f47',
    ('dialogo', 'house_classic'): '3ae64619dd018cc16f87ef048cc96b67ebf194a3207be1e7549a4cea5d5e9722',
    ('dialogo', 'boom_bap_90s'): 'a8d6c9e4c13b9445e0b7501ba8d32aeb6b8fcb7da8ddcff8c8db7a11673e864f',
    ('dialogo', 'breakbeat_house'): '7dc32f05542398f23e4710876669b9ce6bed3f2e46fc2eac5b3651996b661e32',
}


def configuration(name):
    config = json.loads(Path('presets/organico.json').read_text())
    if name == 'dialogo':
        config['generators']['percussion'].update(material='spaced_dialogue', standard_material='regular_pulse_offbeats')
        config['generators']['percussion']['settings']['displacement_beats'] = .25
        config['generators']['atmosphere']['settings']['follow_source'] = 1
        config['sections'] = [dict(name='dialogue', from_progress=0, root=57, scale='dorian',
                                   assignments={n: {'role': r} for n, r in zip(config['voices'],
                                                ('melody', 'bass_line', 'sustained_texture', 'percussion'))})]
    return config


def capture(spec, style, variation):
    gen = build_generator(spec).generator.generate
    output = []
    styles = ('house_classic', 'boom_bap_90s', 'breakbeat_house')
    for index in range(32):
        beat = index*4
        requested = style if style == 'none' else styles[(styles.index(style)+index//3) % 3]
        melody = Phrase(4, () if index % 5 == 0 else (
            Note(0, 60, .7, 90), Note(1.5, 64, .5, 80), Note(3, 67, .8, 85)))
        bass = Phrase(4, () if index % 7 == 0 else (Note(.5, 36, .8, 90), Note(2.5, 40, .7, 80)))
        req = PlanningRequest(beat, 4, None, {'voice_01': melody, 'voice_02': bass}, 'percussion',
                              {'style': requested, 'variation': variation, 'displacement_beats': .25}, beat)
        prepared = gen.prepare_reference(req)
        plan = gen.stage(replace(req, rhythm=prepared.reference, prepared_material=prepared.material))
        gen.accept(plan)
        output.append({'phrase': asdict(plan.phrase), 'reference': asdict(prepared.reference),
                       'gestures': [asdict(span) for span in plan.gestures]})
    return hashlib.sha256(json.dumps(output, sort_keys=True, allow_nan=False).encode()).hexdigest()


def capture_session(config, style):
    from desnivel.cli.ensemble import EnsembleSession
    generators = {key: build_generator(value).generator for key, value in config['generators'].items()}
    destinations = {v['destination']: lambda *args: None for v in config['voices'].values()}
    session = EnsembleSession(config, generators, destinations)
    result = []
    for i in range(32):
        session.set_parameters('voice_04', {'style': style, 'variation': .7, 'displacement_beats': .25})
        phrases = session.plan(i/32, i*4, 4)
        result.append({'phrases': {name: asdict(phrase) for name, phrase in phrases.items()},
                       'rhythm': session.coordinator.last_plan['rhythm']})
    return hashlib.sha256(json.dumps(result, sort_keys=True, allow_nan=False).encode()).hexdigest()


@pytest.mark.parametrize('name,style,variation', PERCUSSION_BEFORE)
def test_centralized_catalog_preserves_notes_references_and_gestures(name, style, variation):
    assert capture(configuration(name)['generators']['percussion'], style, variation) == PERCUSSION_BEFORE[name,style,variation]


@pytest.mark.parametrize('name,style', SESSIONS_BEFORE)
def test_centralization_preserves_the_whole_ensemble_dialogue(name, style):
    assert capture_session(configuration(name), style) == SESSIONS_BEFORE[name,style]


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
