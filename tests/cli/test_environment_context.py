from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

from desnivel.adapters.voice_device import VoiceDeviceBridge
from desnivel.cli.ensemble_runtime import EnsembleRuntime
from desnivel.music.automation import AdaptiveContext
from desnivel.music.environment import weather_intent
from desnivel.trip.context import ContextSource, track_signature
from desnivel.trip.track import Track, TrackSegment


def setup(enabled=True, *, missing_wind=False, missing_rain=False):
    track = Track('test', np.array([0., 1000.]),
                  {'cum_dist_m': np.array([0., 10000.]), 'lat': np.array([44., 44.01]),
                   'lon': np.array([9., 9.01])}, segments=(TrackSegment(0, 2, 10000, 11000, 0, 1),))
    source = ContextSource(dict(version=1, source='weather', track_signature=track_signature(track), axis='time',
        units={'wind_speed_kmh': 'km/h', 'precipitation_mm': 'mm', 'precipitation_change_mm': 'mm'},
        provenance={'provider': 'fixture'}, records=[dict(segment=0, start=0, end=1000,
            values={'wind_speed_kmh': None if missing_wind else 40., 'precipitation_mm': 2.,
                    'precipitation_change_mm': None if missing_rain else 2.}, details={})]))
    config = json.loads(Path('presets/organico.json').read_text())
    # Un'unica sezione rende confrontabili le due esecuzioni per tutta la prova.
    config['sections'] = [config['sections'][0]]
    for assignment in config['sections'][0]['assignments'].values():
        assignment['presence'] = 1
    bridge = VoiceDeviceBridge({}, lambda *args: None, clock=lambda: 0.)
    runtime = EnsembleRuntime(track, config, bridge, clock=lambda: 0.,
                              context_sources=[(source, weather_intent, enabled)])
    def tick(beat):
        for name in config['voices']:
            msg = dict(version=1, voice=name, instance=name, reply_port=9101+list(config['voices']).index(name),
                       serial=beat+1, action='hello' if beat == 0 else 'transport',
                       transport=dict(beat=float(beat), bpm=120., playing=1, epoch=0))
            bridge.handle(msg)
            runtime.on_message(bridge, msg)
        runtime.tick()
        return deepcopy(runtime.last_decisions)
    return runtime, tick, source


def test_runtime_ab_changes_dynamic_and_material_targets_and_actual_music_reproducibly():
    on, tick_on, _ = setup()
    off, tick_off, _ = setup(False)
    repeat, tick_repeat, _ = setup()
    heard_difference = False
    for beat in range(0, 65, 4):
        active, control, same = tick_on(beat), tick_off(beat), tick_repeat(beat)
        assert active == same
        assert active['local_trip']['parts'] == control['local_trip']['parts']
        assert active['adaptive_context']['dynamic_pressure'] == 1
        assert control['adaptive_context']['dynamic_pressure'] is None
        assert not control['local_trip']['environment']['weather']['interpretation_enabled']
        assert (active['automation']['voice_01']['velocity']['target'] >
                control['automation']['voice_01']['velocity']['target'])
        assert 'development' in active['automation']['voice_01']
        heard_difference |= active['voices']['voice_01']['notes'] != control['voices']['voice_01']['notes']
    assert heard_difference
    json.dumps(on.snapshot(), allow_nan=False)


def test_manual_values_override_weather_and_restart_restores_deterministic_plans():
    runtime, tick, _ = setup()
    runtime.session.set_parameters('voice_01', {'velocity': 45, 'development': .1})
    for beat in (0, 4, 8):
        decisions = tick(beat)['automation']['voice_01']
        assert decisions['velocity']['effective'] == 45
        assert decisions['velocity']['source'] == 'manual'
        assert decisions['development']['effective'] == .1


def test_missing_channels_remain_independent_and_missing_context_is_not_zero():
    _, tick, source = setup(missing_wind=True)
    decision = tick(0)
    assert decision['adaptive_context']['dynamic_pressure'] is None
    assert decision['adaptive_context']['material_change'] == 1
    intent = weather_intent(AdaptiveContext(.6), source.describe([]))
    assert intent.intensity == .6
    assert intent.dynamic_pressure is None and intent.material_change is None


def test_device_weather_matches_current_plan_and_manual_flags_without_using_future_plan():
    runtime, tick, _ = setup()
    tick(0)
    assert runtime.bridge.status()['voice_01']['weather']['status'] == 'waiting'
    tick(4)
    state = runtime.snapshot()['voices']
    assert state['voice_01']['weather']['status'] == 'active'
    assert state['voice_02']['weather']['status'] == 'inactive'
    runtime.session.set_parameters('voice_01', {'velocity': 45, 'development': .1})
    assert runtime.bridge.status()['voice_01']['weather']['status'] == 'manual'
    runtime.reset()
    assert runtime.bridge.status()['voice_01']['weather']['status'] == 'waiting'
    _, tick_off, _ = setup(False)
    assert tick_off(0)['adaptive_context']['dynamic_pressure'] is None


def test_live_weather_toggle_keeps_accepted_plans_clock_and_music_memory():
    runtime, tick, _ = setup()
    tick(0)
    tick(4)
    queued = deepcopy(runtime._sent_plans)
    previous = runtime.session.coordinator.last_plan
    elapsed, beat = runtime.elapsed, runtime.beat
    runtime.toggle_context('weather')
    assert runtime._sent_plans == queued
    assert runtime.session.coordinator.last_plan is previous
    assert (runtime.elapsed, runtime.beat) == (elapsed, beat)
    state = runtime.snapshot()
    assert not state['controls']['contexts']['weather']['enabled']
    assert state['voices']['voice_01']['weather']['pending']
    assert state['voices']['voice_01']['weather']['status'] == 'active'
    assert tick(8)['adaptive_context']['dynamic_pressure'] is None
    assert tick(12)['voices']
    assert runtime.weather_status('voice_01')['status'] == 'disabled'
    runtime.toggle_context('weather')
    assert tick(16)['adaptive_context']['dynamic_pressure'] == 1
    tick(20)
    assert runtime.weather_status('voice_01')['status'] == 'active'
    assert runtime.snapshot()['controls']['contexts']['weather']['enabled']


def test_toggle_rejects_unloaded_source_without_changing_configuration():
    runtime, _, _ = setup()
    previous = runtime.context_sources
    with pytest.raises(ValueError, match='non caricato'):
        runtime.toggle_context('surface')
    assert runtime.context_sources == previous


def test_opposite_precipitation_changes_do_not_cancel_and_small_changes_are_ignored():
    _, _, source = setup()
    definition = deepcopy(source.data)
    definition['records'][0]['end'] = 500
    second = deepcopy(definition['records'][0])
    second.update(start=500, end=1000)
    second['values']['precipitation_change_mm'] = -2
    definition['records'].append(second)
    description = ContextSource(definition).describe([dict(travel_segment_index=0, start_active_s=0, end_active_s=1000)])
    assert description['channels']['precipitation_change_mm']['value'] == 0
    assert weather_intent(None, description).material_change == 1
    for record in definition['records']:
        record['values']['precipitation_change_mm'] = .1
    description = ContextSource(definition).describe([dict(travel_segment_index=0, start_active_s=0, end_active_s=1000)])
    assert weather_intent(None, description).material_change == 0


@pytest.mark.parametrize('field', ['dynamic_pressure', 'material_change'])
def test_invalid_environmental_indications_are_rejected(field):
    with pytest.raises(ValueError):
        AdaptiveContext(**{field: 1.1})
