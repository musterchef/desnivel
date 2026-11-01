import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from desnivel.adapters.voice_device import VoiceDeviceBridge
from desnivel.cli.ensemble_runtime import EnsembleRuntime
from desnivel.trip.track import Track


def configuration():
    config = json.loads(Path('presets/organico.json').read_text())
    config['generators']['percussion'].update(material='spaced_dialogue', standard_material='regular_pulse_offbeats')
    config['generators']['percussion']['settings']['displacement_beats'] = .25
    config['generators']['atmosphere']['settings']['follow_source'] = 1
    config['sections'] = [dict(name='dialogue', from_progress=0, root=57, scale='dorian',
                               assignments={name: {'role': role} for name, role in zip(config['voices'],
                                            ('melody', 'bass_line', 'sustained_texture', 'percussion'))})]
    return config


def runtime(config=None):
    bridge = VoiceDeviceBridge({}, lambda *args: None)
    track = Track('test', np.array([0., 10.]), {'cum_dist_m': np.array([0., 100.])})
    return EnsembleRuntime(track, config or configuration(), bridge)


def test_real_generators_exchange_rhythm_in_both_directions():
    c = configuration()
    without_history = deepcopy(c)
    without_history['relations'] = []
    a, b = runtime(c), runtime(without_history)
    changed = []
    for start in range(0, 32, 4):
        pa, pb = a.session.plan(0, start, 4), b.session.plan(0, start, 4)
        if pa['voice_01'] != pb['voice_01']:
            changed.append(start)
        assert a.session.coordinator.last_plan['rhythm'] == b.session.coordinator.last_plan['rhythm']
    assert changed  # Gli stessi appoggi, ma drums precedenti diverse dalla sola guida.

    # La melodia cambia le risposte percussive correnti, senza cambiare il riferimento.
    a, b = runtime(), runtime()
    a.session.set_parameters('voice_01', {'development': 0, 'step_beats': .5})
    b.session.set_parameters('voice_01', {'development': 0, 'step_beats': 2})
    pa, pb = a.session.plan(0, 0, 4), b.session.plan(0, 0, 4)
    assert pa['voice_04'] != pb['voice_04']
    assert a.session.coordinator.last_plan['rhythm'] == b.session.coordinator.last_plan['rhythm']


def test_guide_changes_melodic_and_bass_attacks_without_changing_pitches():
    a, b = runtime(), runtime()
    for r, amount in [(a, 0), (b, 1)]:
        r.session.set_parameters('voice_01', {'development': 0, 'step_beats': .75, 'groove_follow': amount})
        r.session.set_parameters('voice_02', {'groove_follow': amount})
    pa, pb = a.session.plan(0, 0, 4), b.session.plan(0, 0, 4)
    assert [n.beat for n in pa['voice_01'].notes] != [n.beat for n in pb['voice_01'].notes]
    assert [n.pitch for n in pa['voice_01'].notes] == [n.pitch for n in pb['voice_01'].notes]
    # Isola l'effetto sul basso mantenendo invariata la melodia sorgente.
    a, b = runtime(), runtime()
    a.session.set_parameters('voice_02', {'groove_follow': 0})
    b.session.set_parameters('voice_02', {'groove_follow': 1})
    changed = False
    for start in range(0, 24, 4):
        pa, pb = a.session.plan(0, start, 4), b.session.plan(0, start, 4)
        changed |= pa['voice_02'] != pb['voice_02']
        assert [n.pitch for n in pa['voice_02'].notes] == [n.pitch for n in pb['voice_02'].notes]
    assert changed


def test_structural_drums_survive_absent_bass_and_guide_survives_absent_drums():
    c = configuration()
    del c['sections'][0]['assignments']['voice_02']
    r = runtime(c)
    p = r.session.plan(0, 0, 4)
    assert {(n.beat, n.pitch) for n in p['voice_04'].notes} >= {(0, 36), (2, 36)}
    del c['sections'][0]['assignments']['voice_04']
    r = runtime(c)
    p = r.session.plan(0, 0, 4)
    assert 'voice_04' not in p
    assert r.session.coordinator.last_plan['rhythm']['points']


def test_bass_has_section_support_when_foreground_is_silenced_and_reset_clears_history():
    r = runtime()
    r.session.set_presence_multiplier('voice_01', 0)
    p = r.session.plan(0, 0, 4)
    assert not p['voice_01'].notes
    assert p['voice_02'].notes
    assert r.session.coordinator.last_plan['voices']['voice_02']['composition']['material_source'] == 'section'
    epoch = r.session.coordinator.epoch
    r.reset()
    assert not r.session.coordinator.history
    assert r.session.coordinator.epoch == epoch+1
    assert r.session.plan(0, 0, 4) == p


def test_reference_required_for_settings_sections_and_live_controls():
    c = configuration()
    del c['rhythm_voice']
    with pytest.raises(ValueError, match='rhythm_voice'):
        runtime(c)
    c = json.loads(Path('presets/organico.json').read_text())
    del c['rhythm_voice']
    for name in ('motif', 'accompaniment'):
        c['generators'][name]['settings']['groove_follow'] = 0
    r = runtime(c)
    assert 'inactive_reason' in r.bridge.status()['voice_01']['controls']['groove_follow']
    with pytest.raises(ValueError, match='rhythm_voice'):
        r.session.set_parameters('voice_01', {'groove_follow': .5})
    c['sections'][0]['assignments']['voice_01']['parameters'] = {'groove_follow': .5}
    with pytest.raises(ValueError, match='rhythm_voice'):
        runtime(c)


def test_failure_of_last_voice_leaves_real_generators_ready_for_identical_retry():
    r, clean = runtime(), runtime()
    coordinator = r.session.coordinator
    original = coordinator._voices['voice_04']
    def reject(request):
        raise ValueError('last voice failed')
    coordinator._voices['voice_04'] = replace(original, stage=reject)
    with pytest.raises(ValueError, match='last voice failed'):
        r.session.plan(0, 0, 4)
    assert r.registry['voice_01'].generator.generate._origin is None
    assert r.registry['voice_02'].generator.generate.previous is None
    assert r.registry['voice_03'].generator.generate.previous_pitch is None
    assert r.registry['voice_04'].generator.generate.position == 0
    assert not coordinator.history
    coordinator._voices['voice_04'] = original
    assert r.session.plan(0, 0, 4) == clean.session.plan(0, 0, 4)


def test_style_selection_updates_guide_and_survives_preset_save_reload(tmp_path):
    from desnivel.cli.voice_presets import connect_preset_library
    from desnivel.sinks.voice_presets import VoicePresetLibrary
    r = runtime()
    r.session.set_parameters('voice_04', {'variation': .23})
    path = tmp_path / 'presets.json'
    connect_preset_library(VoicePresetLibrary(path), r.bridge.voices)
    base = dict(version=1, voice='voice_04', instance='device', reply_port=9104)
    r.bridge.handle(dict(base, serial=1, action='hello'))
    r.bridge.handle(dict(base, serial=2, action='parameter', parameter='style', value='house_classic'))
    values = r.session.parameters_at('voice_04', 0)
    assert values['style'] == 'house_classic' and values['variation'] == .23
    assert r.bridge.status()['voice_04']['controls']['style']['choices']
    r.session.plan(0, 0, 4)
    house = r.session.coordinator.last_plan['rhythm']
    r.bridge.handle(dict(base, serial=3, action='save_preset', preset='my house'))
    assert json.loads(path.read_text())['voices']['voice_04']['my house']['style'] == 'house_classic'
    other = runtime()
    connect_preset_library(VoicePresetLibrary(path), other.bridge.voices)
    other.bridge.handle(dict(base, serial=1, action='hello'))
    other.bridge.handle(dict(base, serial=2, action='preset', preset='my house'))
    assert {key: control['value'] for key, control in other.bridge.status()['voice_04']['controls'].items()} == {
        key: control['value'] for key, control in r.bridge.status()['voice_04']['controls'].items()}
    r.bridge.handle(dict(base, serial=4, action='parameter', parameter='style', value='boom_bap_90s'))
    r.session.plan(0, 4, 4)
    assert house != r.session.coordinator.last_plan['rhythm']
    assert r.session.coordinator.last_plan['voices']['voice_04']['composition']['logical_start'] == 4
    with pytest.raises(ValueError, match='scelta'):
        r.bridge.handle(dict(base, serial=5, action='parameter', parameter='style', value=1))
    assert r.session.parameters_at('voice_04', 0)['style'] == 'boom_bap_90s'


def test_old_drum_presets_get_explicit_none_migration(tmp_path):
    from desnivel.cli.voice_presets import connect_preset_library
    from desnivel.sinks.voice_presets import VoicePresetLibrary
    r = runtime()
    values = dict(r.bridge.voices['voice_04'].values)
    del values['style']
    path = tmp_path / 'old.json'
    original = json.dumps({'version': 1, 'voices': {'voice_04': {'saved': values}}})
    path.write_text(original)
    connect_preset_library(VoicePresetLibrary(path), r.bridge.voices)
    assert r.bridge.voices['voice_04'].presets['saved']['style'] == 'none'
    assert r.bridge.status()['voice_04']['preset_migrations'] == {'saved': {'style': 'none'}}
    assert path.read_text() == original


def test_single_controls_keep_section_changes_and_other_manual_overrides():
    config = json.loads(Path('presets/organico.json').read_text())
    families = json.loads(Path('presets/direzione-viaggio.json').read_text())['families']
    for family in families.values():
        family.update(root=57, scale='minor')
    config['sections'] = [dict(families['level'], name='level', from_progress=0),
                          dict(families['descent'], name='descent', from_progress=.5)]
    r = runtime(config)
    base = dict(version=1, voice='voice_01', instance='device', reply_port=9101)
    r.bridge.handle(dict(base, serial=1, action='hello'))
    r.bridge.handle(dict(base, serial=2, action='parameter', parameter='velocity', value=46))
    assert r.session.parameters_at('voice_01', .75) == {
        **r.registry['voice_01'].values, **families['descent']['assignments']['voice_01']['parameters'], 'velocity': 46}
    r.bridge.handle(dict(base, serial=3, action='parameter', parameter='articulation', value=.4))
    assert r.session.parameters_at('voice_01', 0)['velocity'] == 46
    r.elapsed = 8
    controls = r.bridge.status()['voice_01']['controls']
    assert controls['step_beats']['value'] == .5
    assert controls['activity']['value'] == .85
    assert controls['articulation']['value'] == .4
    assert controls['velocity']['value'] == 46
    r.session.plan(r.progress, 0, 4)
    assert r.session.coordinator.last_plan['voices']['voice_01']['parameters']['activity'] == .85
    before = r.session.parameters_at('voice_01', .75)
    with pytest.raises(ValueError):
        r.bridge.handle(dict(base, serial=4, action='parameter', parameter='velocity', value=200))
    assert r.session.parameters_at('voice_01', .75) == before
    r.session.clear_parameters('voice_01')
    assert r.session.parameters_at('voice_01', .75) == {**r.registry['voice_01'].values, **families['descent']['assignments']['voice_01']['parameters']}


def test_variation_remains_continuous_without_selecting_a_preset():
    r = runtime()
    base = dict(version=1, voice='voice_04', instance='device', reply_port=9104)
    r.bridge.handle(dict(base, serial=1, action='hello'))
    r.bridge.handle(dict(base, serial=2, action='parameter', parameter='style', value='house_classic'))
    r.bridge.handle(dict(base, serial=3, action='parameter', parameter='variation', value=.37))
    state = r.bridge.status()['voice_04']
    control = state['controls']['variation']
    assert control['label'] == 'Variazione' and control['value'] == .37
    assert control['minimum'] == 0 and control['maximum'] == 1 and not control['integer']
    assert 'choices' not in control and state['preset'] is None
    r.session.plan(0, 0, 4)
    composition = r.session.coordinator.last_plan['voices']['voice_04']['composition']
    assert composition['style'] == 'house_classic' and composition['variation'] == .37


def test_main_configuration_connects_rhythm_and_historical_dialogue():
    r = runtime(json.loads(Path('presets/organico.json').read_text()))
    assert r.session.coordinator.rhythm_source == 'voice_04'
    assert r.bridge.status()['voice_01']['controls']['groove_follow']['value'] == .3
    assert r.bridge.status()['voice_02']['controls']['groove_follow']['value'] == .7
    for start in range(0, 36, 4):
        r.session.plan(.4, start, 4)
    plan = r.session.coordinator.last_plan
    assert plan['rhythm']['points']
    assert plan['voices']['voice_01']['relations'][0]['status'] == 'resolved'


@pytest.mark.parametrize('conceptuality,variation,expected', [(0, .7, 0), (.5, .8, .4), (1, .7, .7)])
def test_legacy_drum_preset_migration_is_explicit_and_preserves_the_file(tmp_path, conceptuality, variation, expected):
    from desnivel.cli.voice_presets import connect_preset_library
    from desnivel.sinks.voice_presets import VoicePresetLibrary
    r = runtime()
    values = {**r.bridge.voices['voice_04'].values, 'conceptuality': conceptuality, 'variation': variation}
    path = tmp_path/'old.json'
    text = json.dumps({'version': 1, 'voices': {'voice_04': {'saved': values}}})
    path.write_text(text)
    connect_preset_library(VoicePresetLibrary(path), r.bridge.voices)
    spec = r.bridge.voices['voice_04']
    assert spec.presets['saved']['variation'] == expected
    assert 'conceptuality' not in spec.presets['saved']
    assert spec.preset_migrations['saved'] == {
        'removed_controls': {'conceptuality': conceptuality},
        'variation': {'previous': variation, 'value': expected}}
    assert path.read_text() == text
    base = dict(version=1, voice='voice_04', instance='device', reply_port=9104)
    r.bridge.handle(dict(base, serial=1, action='hello'))
    r.bridge.handle(dict(base, serial=2, action='preset', preset='saved'))
    assert r.session.parameters_at('voice_04', 0)['variation'] == expected


@pytest.mark.parametrize('field,value', [('conceptuality', 1.1), ('conceptuality', True), ('variation', -.1)])
def test_legacy_drum_preset_migration_rejects_invalid_values(tmp_path, field, value):
    from desnivel.cli.voice_presets import connect_preset_library
    from desnivel.sinks.voice_presets import VoicePresetLibrary
    r = runtime()
    values = {**r.bridge.voices['voice_04'].values, 'conceptuality': .5, field: value}
    path = tmp_path/'invalid.json'
    path.write_text(json.dumps({'version': 1, 'voices': {'voice_04': {'saved': values}}}))
    with pytest.raises(ValueError, match='fuori intervallo'):
        connect_preset_library(VoicePresetLibrary(path), r.bridge.voices)
