import json
from pathlib import Path

import numpy as np
import pytest

from desnivel.adapters.voice_device import VoiceDeviceBridge
from desnivel.cli.ensemble_runtime import EnsembleRuntime
from desnivel.cli.trip_direction import prepare_trip_config
from desnivel.trip.track import Track


def setup(adaptive=True, timing='allocated'):
    slopes = np.array([0.]*6+[.04]*6+[.08]*6+[-.04]*6)
    distances = np.arange(len(slopes)+1)*100.
    track = Track('adaptive', np.arange(len(distances))*10.,
                  {'cum_dist_m': distances, 'ele': np.r_[100., 100+np.cumsum(slopes)*100]})
    config = json.loads(Path('presets/organico.json').read_text())
    config['timeline'] = dict(target_beats=128, min_windows=2, distance_exponent=.5)
    config = prepare_trip_config(track, config, Path('presets/direzione-viaggio.json'))
    now, serial = [0.], [0]
    bridge = VoiceDeviceBridge({}, lambda *args: None, clock=lambda: now[0])
    runtime = EnsembleRuntime(track, config, bridge, clock=lambda: now[0], timing=timing, adaptive=adaptive)
    def tick(index, bpm=120):
        now[0] = index*.25
        for name in config['voices']:
            serial[0] += 1
            message = dict(version=1, voice=name, instance=name, reply_port=9100+int(name[-1]),
                           serial=serial[0], action='hello', transport=dict(beat=index*4, playing=1, epoch=0, bpm=bpm))
            bridge.handle(message)
            runtime.on_message(bridge, message)
        runtime.tick()
        return runtime.last_decisions
    return runtime, tick


def test_all_four_voices_change_parameters_and_midi_and_ui_uses_the_playing_plan():
    automatic, tick = setup()
    fixed, tick_fixed = setup(False)
    values, differences, variation_by_section = {}, set(), {}
    for i in range(24):
        plan, baseline = tick(i), tick_fixed(i)
        for name, fields in plan['automation'].items():
            for parameter, details in fields.items():
                values.setdefault((name, parameter), set()).add(round(details['effective'], 6))
                assert details['effective'] == plan['voices'][name]['parameters'][parameter]
            if plan['voices'][name]['notes'] != baseline['voices'][name]['notes']:
                differences.add(name)
        section = plan['section']
        variation_by_section.setdefault(section, set()).add(round(plan['voices']['voice_04']['parameters']['variation'], 6))
        visible = automatic.bridge.status()
        for name, voice in visible.items():
            playing = automatic.session.coordinator.parameter_states_at(name, automatic.beat)
            for parameter, details in playing.items():
                assert voice['controls'][parameter]['value'] == details['effective']
        json.dumps(automatic.snapshot(), allow_nan=False)
    for name in ('voice_01', 'voice_02', 'voice_03', 'voice_04'):
        assert any(v == name and len(samples) > 1 for (v, _), samples in values.items())
    assert differences == set(automatic.registry)
    assert any(len(samples) > 1 for samples in variation_by_section.values())
    assert all(tick_fixed(i)['voices']['voice_04']['parameters']['variation'] == .7 for i in range(24, 26))


def test_one_manual_control_holds_while_others_adapt_and_release_is_gradual():
    runtime, tick = setup()
    runtime.session.set_parameter('voice_04', 'variation', .95)
    changed = set()
    for i in range(8):
        plan = tick(i)
        assert plan['voices']['voice_04']['parameters']['variation'] == .95
        changed.add(plan['voices']['voice_04']['parameters']['velocity_ratio'])
    assert len(changed) > 1
    runtime.session.set_manual('voice_04', 'variation', False, progress=runtime.progress, beat=runtime.beat)
    assert tick(8)['voices']['voice_04']['parameters']['variation'] == .95
    after = tick(9)['voices']['voice_04']['parameters']['variation']
    assert .7 < after < .95
    assert runtime.bridge.status()['voice_04']['controls']['variation']['manual'] is False


def test_pinning_all_controls_matches_disabled_adaptation():
    a, tick_a = setup()
    b, tick_b = setup(False)
    for runtime in (a, b):
        for name, registered in runtime.registry.items():
            runtime.session.set_parameters(name, registered.values)
    for i in range(12):
        pa, pb = tick_a(i), tick_b(i)
        assert {n: v['notes'] for n, v in pa['voices'].items()} == {n: v['notes'] for n, v in pb['voices'].items()}


def test_manual_switch_captures_the_visible_value_instead_of_a_future_plan():
    runtime, tick = setup()
    tick(0)
    tick(1)
    visible = runtime.bridge.status()['voice_01']['controls']['velocity']['value']
    future = runtime.session.coordinator.parameter_states_at('voice_01')['velocity']['effective']
    assert visible != future
    runtime.bridge.voices['voice_01'].apply_manual('velocity', True)
    assert tick(2)['voices']['voice_01']['parameters']['velocity'] == visible


def test_manual_literal_mode_keeps_activity_inactive():
    runtime, tick = setup()
    runtime.session.set_parameter('voice_01', 'development', 0)
    plan = tick(0)
    assert 'activity' not in plan['automation']['voice_01']
    assert plan['voices']['voice_01']['composition']['method'] == 'literal_motif'
    assert runtime.bridge.status()['voice_01']['controls']['activity']['inactive_reason']


def test_missing_tempo_keeps_route_contributions_unavailable_and_dialogue_active():
    runtime, tick = setup(timing='linear')
    for index in range(4):
        plan = tick(index, bpm=None)
        assert plan['adaptive_context']['intensity'] is None
        assert plan['adaptive_context']['unavailable_reason'] == 'tempo_unavailable'
        velocity = plan['automation']['voice_01']['velocity']
        assert velocity['target'] == velocity['base']
    assert runtime.adaptation_enabled
    assert plan['observation']['available_beats'] > 0


@pytest.mark.parametrize('style', ['house_classic', 'boom_bap_90s', 'breakbeat_house'])
def test_style_and_smooth_style_transition_work_with_automatic_variation(style):
    runtime, tick = setup()
    runtime.session.set_parameter('voice_04', 'style', style)
    variations = set()
    for index in range(16):
        if index == 8:
            runtime.session.set_parameter('voice_04', 'style', 'breakbeat_house' if style != 'breakbeat_house' else 'house_classic')
        plan = tick(index)
        variations.add(plan['voices']['voice_04']['parameters']['variation'])
        composition = plan['voices']['voice_04']['composition']
        assert composition['style'] == plan['voices']['voice_04']['parameters']['style']
        assert composition['style_weights']
        assert runtime.session.manual('voice_04', 'style')
        assert not runtime.session.manual('voice_04', 'variation')
    assert len(variations) > 1
