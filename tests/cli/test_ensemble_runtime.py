import json
from pathlib import Path

import numpy as np
import pytest

from desnivel.adapters.voice_device import VoiceDeviceBridge
from desnivel.cli.ensemble_runtime import EnsembleRuntime
from desnivel.trip.track import Track


def transport_config():
    config = json.loads(Path('presets/organico.json').read_text())
    config.pop('rhythm_voice')
    config.pop('relations')
    for name in ('motif', 'accompaniment'):
        config['generators'][name]['settings']['groove_follow'] = 0
    return config


def setup():
    now, sent = [0.], []
    bridge = VoiceDeviceBridge({}, lambda *args: sent.append(args), clock=lambda: now[0])
    track = Track('test', np.array([0., 10.]), {'cum_dist_m': np.array([0., 100.])})
    config = transport_config()
    # Queste prove isolano trasporto e organico variabile con due voci.
    # La configurazione completa a quattro è verificata in test_trip_direction.
    config['voices'] = {name: spec for name, spec in config['voices'].items() if name in ('voice_01', 'voice_02')}
    for section in config['sections']:
        section['assignments'] = {name: spec for name, spec in section['assignments'].items() if name in config['voices']}
        for spec in section['assignments'].values():
            spec['presence'] = 1  # Isola le prove di trasporto dalle scelte dell'assetto di ascolto.
    runtime = EnsembleRuntime(track, config, bridge, speed=2, clock=lambda: now[0])
    serials = {}
    def receive(voice='voice_01', beat=0., playing=1, epoch=0, bpm=None):
        serials[voice] = serials.get(voice, 0)+1
        msg = dict(version=1, voice=voice, instance=voice, reply_port=9101 if voice=='voice_01' else 9102,
                   serial=serials[voice], action='transport' if serials[voice]>1 else 'hello',
                   transport=dict(beat=beat, playing=playing, epoch=epoch, bpm=bpm))
        bridge.handle(msg)
        runtime.on_message(bridge, msg)
    return runtime, bridge, now, sent, receive


def test_planned_linear_context_uses_live_tempo_without_changing_parameters():
    runtime, _, _, _, receive = setup()
    before = runtime.session.parameters_at('voice_01', 0)
    receive(bpm=120)
    runtime.tick()
    local = runtime.last_decisions['local_trip']
    assert (local['start_active_s'], local['end_active_s']) == (4, 8)
    assert (local['parts'][0]['start_distance_m'], local['parts'][0]['end_distance_m']) == (40, 80)
    assert runtime.progress == 0  # Il contesto riguarda la finestra futura, non il cursore attuale.
    assert runtime.session.parameters_at('voice_01', 0) == before
    snapshot = runtime.snapshot()
    assert snapshot['transport']['bpm'] == 120
    assert snapshot['decisions']['coordinator']['observation']['available_beats'] == 0
    json.dumps(snapshot, allow_nan=False)


def test_missing_tempo_is_explicit_and_invalid_tempo_does_not_mutate_transport():
    runtime, bridge, _, _, receive = setup()
    receive()
    runtime.tick()
    assert runtime.last_decisions['local_trip']['reason'] == 'tempo_unavailable'
    receive(bpm=120)
    with pytest.raises(ValueError, match='BPM'):
        receive(bpm=0)
    assert runtime.bpm == 120
    assert bridge.status()['voice_01']['connected']


def test_display_tracks_sent_current_and_future_plans_without_recomposing():
    runtime, _, _, sent, receive = setup()
    receive(bpm=120)
    runtime.tick()
    first = runtime.last_decisions
    before = len(sent)
    status = runtime.snapshot()['planning']
    assert status['current'] is None
    assert status['upcoming'] == [first]
    assert len(sent) == before
    receive(beat=first['start'])
    runtime.tick()
    status = runtime.snapshot()['planning']
    assert status['current'] == first
    assert status['upcoming'][0]['start'] > first['start']
    assert status['current']['section'] == first['section']
    receive(beat=first['start']+first['length_beats'])
    runtime.tick()
    assert runtime.snapshot()['planning']['current'] != first
    runtime.control('restart')
    status = runtime.snapshot()['planning']
    assert status['current'] is None and status['upcoming'] == []


def test_waiting_then_continuous_plans_sections_roles_and_status():
    runtime, bridge, now, sent, receive = setup()
    runtime.tick()
    assert runtime.state == 'waiting_for_transport'
    receive(); receive('voice_02')
    runtime.tick()
    assert runtime.state == 'playing'
    assert set(bridge.last_plans) == {'voice_01'}
    count = len(sent)
    runtime.tick()
    assert len(sent) == count  # Nessuna rigenerazione dello stesso intervallo.
    now[0] = 1.6
    receive(beat=4)
    runtime.tick()
    assert runtime.progress == pytest.approx(.32)
    assert set(bridge.last_plans) == {'voice_01', 'voice_02'}
    status = runtime.snapshot()
    assert status['section']['name'] == 'development'
    assert status['voices']['voice_02']['dependencies'] == ['voice_01']
    assert status['voices']['voice_01']['supported_roles'] == ['melody', 'sustained_texture', 'bass_line']
    json.dumps(status, allow_nan=False)
    # Override valido anche durante i successivi cambi di sezione.
    runtime.session.set_role('voice_01', 'sustained_texture')
    now[0] = 2
    receive(beat=8)
    runtime.tick()
    assert bridge.last_plans['voice_01']['notes'] == 1


def test_stop_pauses_trip_and_seek_replans_without_rewinding_trip():
    runtime, bridge, now, _, receive = setup()
    receive(); runtime.tick()
    now[0] = .5
    receive(beat=1, playing=0, epoch=1)
    runtime.tick()
    elapsed = runtime.elapsed
    assert not bridge.last_plans
    now[0] = 1
    runtime.tick()
    assert runtime.elapsed == elapsed
    receive(beat=0, playing=1, epoch=2)
    runtime.tick()
    assert runtime.elapsed == elapsed
    assert bridge.last_plans['voice_01']['start'] == 4
    now[0] = 1.1
    receive(beat=0, playing=1, epoch=3)
    runtime.tick()
    assert runtime.elapsed >= elapsed
    assert runtime.elapsed < 2


def test_missing_active_device_pauses_trip_and_lost_transport_cancels_plans():
    runtime, bridge, now, _, receive = setup()
    receive(); runtime.tick()
    now[0] = 1.6
    receive(beat=4); runtime.tick()
    assert runtime.state == 'waiting_for_devices'
    elapsed = runtime.elapsed
    now[0] = 2
    runtime.tick()
    assert runtime.elapsed == elapsed
    receive('voice_02'); receive(beat=5)
    runtime.tick()
    assert runtime.state == 'playing'
    now[0] = 6
    runtime.tick()
    assert runtime.state == 'waiting_for_transport'
    assert not runtime.sounding


def test_manual_parameters_reflected_in_status_and_applied_to_next_plan():
    runtime, bridge, now, sent, receive = setup()
    receive(); runtime.tick()
    bridge.handle(dict(version=1, voice='voice_01', instance='voice_01', reply_port=9101,
                       serial=2, action='parameter', parameter='velocity', value=45))
    # Usa il seriale successivo per il trasporto.
    bridge.handle(dict(version=1, voice='voice_01', instance='voice_01', reply_port=9101,
                       serial=3, action='hello'))
    assert runtime.snapshot()['voices']['voice_01']['controls']['velocity']['value'] == 45
    phrases = runtime.session.plan(0, 8, 4)
    assert all(35 <= n.velocity <= 53 for n in phrases['voice_01'].notes)


def test_invalid_controls_do_not_mutate_manual_values():
    runtime, _, _, _, _ = setup()
    before = runtime.session.parameters_at('voice_01', 0)
    with pytest.raises(ValueError):
        runtime.session.set_parameters('voice_01', {'velocity': 300})
    assert runtime.session.parameters_at('voice_01', 0) == before
    assert not runtime.session.manual('voice_01', 'velocity')


def test_control_applicability_tracks_section_role_and_manual_mode():
    runtime, bridge, _, _, receive = setup()
    receive()
    controls = bridge.status()['voice_01']['controls']
    assert 'inactive_reason' not in controls['activity']
    runtime.session.set_role('voice_01', 'sustained_texture')
    controls = bridge.status()['voice_01']['controls']
    assert 'inactive_reason' in controls['activity']
    assert 'inactive_reason' not in controls['velocity']
    runtime.session.set_role('voice_01', None)
    runtime.session.set_parameters('voice_01', {'development': 0})
    controls = bridge.status()['voice_01']['controls']
    assert 'inactive_reason' in controls['activity']
    assert 'inactive_reason' not in controls['step_beats']
    assert controls['activity']['value'] == .75


def test_device_presence_command_is_dynamic_and_reflected_in_session_status():
    runtime, bridge, now, sent, receive = setup()
    receive(); runtime.tick()
    assert runtime.snapshot()['voices']['voice_01']['presence']['effective'] == 1
    reply = bridge.handle(dict(version=1, voice='voice_01', instance='voice_01', reply_port=9101,
                               serial=2, action='presence', value=0))
    assert reply['presence'] == dict(automatic=1, multiplier=0, effective=0)
    # Il piano già inviato rimane valido, le prossime frasi sono silenziose.
    assert bridge.last_plans['voice_01']['notes'] > 0
    assert not runtime.session.plan(0, 8, 4)['voice_01'].notes
    assert runtime.snapshot()['voices']['voice_01']['presence']['effective'] == 0
    runtime.control('restart')
    assert runtime.session.presence_state('voice_01', 0)['multiplier'] == 0


def test_inactive_reason_and_decisions_match_section_and_executed_plan():
    runtime, bridge, now, _, receive = setup()
    receive(); receive('voice_02'); runtime.tick()
    status = runtime.snapshot()
    part = status['voices']['voice_02']
    assert part['connected'] and not part['active']
    assert part['inactive_reason'] == 'not_assigned_to_section'
    assert part['next_entry_progress'] == .3
    assert status['decisions']['director']['until_progress'] == .3
    assert status['decisions']['coordinator']['order'] == ['voice_01']
    now[0] = 1.6
    receive(beat=4); runtime.tick()
    status = runtime.snapshot()
    plan = status['decisions']['coordinator']
    assert plan['order'] == ['voice_01', 'voice_02']
    assert plan['voices']['voice_02']['dependencies'] == ['voice_01']
    assert len(plan['voices']['voice_02']['notes']) == bridge.last_plans['voice_02']['notes']
    assert status['decisions']['director']['assignments']['voice_02']['source'] == 'section'
    runtime.session.set_role('voice_01', 'sustained_texture')
    assert runtime.snapshot()['decisions']['director']['assignments']['voice_01']['source'] == 'manual'


def allocated_setup():
    runtime, bridge, now, sent, receive = setup()
    # Ricostruisce il runtime con macrosezioni sintetiche e lo stesso trasporto.
    config = transport_config()
    config['voices'] = {k: v for k, v in config['voices'].items() if k in ('voice_01', 'voice_02')}
    for i, section in enumerate(config['sections']):
        section['assignments'] = {k: v for k, v in section['assignments'].items() if k in config['voices']}
        section['trip'] = {'start_distance_m': i*10, 'end_distance_m': (i+1)*10}
    config['timeline'] = {'target_beats': 24, 'min_windows': 2, 'distance_exponent': .5}
    runtime = EnsembleRuntime(runtime.track, config, bridge, clock=lambda: now[0], timing='allocated')
    serial = [0]
    def receive(beat=0, playing=1, epoch=0):
        for voice in config['voices']:
            serial[0] += 1
            message = dict(version=1, voice=voice, instance=voice, reply_port=9100+int(voice[-1]),
                           serial=serial[0], action='hello',
                           transport=dict(beat=beat, playing=playing, epoch=epoch))
            bridge.handle(message)
            runtime.on_message(bridge, message)
    return runtime, bridge, now, sent, receive


def test_allocated_plays_every_window_and_finishes_only_after_last_end():
    runtime, bridge, now, sent, receive = allocated_setup()
    sections = []
    for beat in (0, 4, 8, 12, 16, 20):
        now[0] += .1
        receive(beat)
        runtime.tick()
        sections.append(runtime.last_decisions['section'])
        local = runtime.last_decisions['local_trip']
        expected = runtime.window_context.allocated(runtime.timeline.timeline,
                                                   runtime.section_sources, runtime.next_window-1)
        assert local == expected
    assert sections == ['opening', 'opening', 'development', 'development', 'closing', 'closing']
    assert runtime.timeline.window_index == 4
    assert runtime.state == 'playing'
    assert runtime.next_window == 6
    receive(24); runtime.tick()
    assert runtime.state == 'playing'
    assert runtime.timeline.window_index == 5
    receive(28); runtime.tick()
    assert runtime.state == 'finished'
    assert runtime.progress == 1
    assert runtime.snapshot()['timeline']['beat'] == 24
    assert not runtime.sounding


def test_allocated_stop_and_loop_reanchor_without_skipping_windows():
    runtime, bridge, now, sent, receive = allocated_setup()
    receive(); runtime.tick()
    receive(8); runtime.tick()
    assert runtime.timeline.window_index == 1
    receive(9, playing=0); runtime.tick()
    assert runtime.next_window == 1
    now[0] = 100
    runtime.tick()
    assert runtime.timeline.window_index == 1
    receive(0, epoch=1); runtime.tick()
    assert runtime.next_window == 2
    assert runtime.last_decisions['section'] == 'opening'
    assert runtime.planned_start == 4
    receive(0, epoch=2); runtime.tick()
    assert runtime.timeline.window_index == 1
    assert runtime.next_window == 2


def test_allocated_wall_clock_and_forward_seek_do_not_skip_unplanned_sections():
    runtime, bridge, now, sent, receive = allocated_setup()
    receive(); runtime.tick()
    now[0] = .1
    receive(100); runtime.tick()
    assert runtime.timeline.window_index == 1
    assert runtime.next_window == 2
    assert runtime.last_decisions['section'] == 'opening'
    assert runtime.elapsed == 0


def test_allocated_missing_device_freezes_cursor_and_replans_current_window():
    runtime, bridge, now, sent, receive = allocated_setup()
    receive(); runtime.tick()
    receive(8); runtime.tick()
    receive(12); runtime.tick()
    assert runtime.last_decisions['section'] == 'development'
    now[0] = 5
    runtime.tick()
    assert runtime.state == 'waiting_for_transport'
    index = runtime.timeline.window_index
    assert runtime.next_window == index
    assert not runtime.pending_windows
    receive(0, epoch=1); runtime.tick()
    assert runtime.timeline.window_index == index
    assert runtime.next_window == index+1


def test_pause_freezes_linear_trip_and_restart_resets_position_and_generator_memory():
    runtime, _, now, _, receive = setup()
    receive(); runtime.tick()
    now[0] = .5
    runtime.control('pause')
    elapsed = runtime.elapsed
    assert runtime.paused and runtime.state == 'paused'
    assert not runtime.sounding
    now[0] = 50
    receive(beat=20)
    runtime.tick()
    assert runtime.elapsed == elapsed
    runtime.control('resume')
    runtime.tick()
    assert runtime.state == 'playing'
    runtime.control('restart')
    assert runtime.progress == 0 and runtime.elapsed == 0
    assert runtime.last_decisions is None and not runtime.sounding
    assert runtime.snapshot()['controls']['restart_count'] == 1


def test_allocated_restart_after_end_waits_for_play_before_repeating_the_trip():
    runtime, _, now, _, receive = allocated_setup()
    receive(); runtime.tick()
    runtime.timeline.seek_window(runtime.timeline.timeline.total_windows)
    runtime.tick()
    assert runtime.state == 'finished'
    runtime.control('restart')
    assert runtime.progress == 0
    assert runtime.next_window == runtime.timeline.window_index == 0
    receive(0, playing=0, epoch=1); runtime.tick()
    assert runtime.last_decisions is None
    assert runtime.state == 'stopped'
    receive(0, playing=1, epoch=2); runtime.tick()
    assert runtime.last_decisions['section'] == 'opening'
    runtime.control('pause')
    index, progress = runtime.timeline.window_index, runtime.progress
    now[0] += 100
    receive(80); runtime.tick()
    assert runtime.timeline.window_index == index and runtime.progress == progress
    assert runtime.state == 'paused'


@pytest.mark.parametrize('allocated', [False, True])
def test_restart_rewinds_and_stays_stopped_until_a_new_live_play(allocated):
    runtime, bridge, now, _, receive = allocated_setup() if allocated else setup()
    receive(); runtime.tick()
    now[0] += .5
    receive(beat=8); runtime.tick()
    runtime.session.set_parameter('voice_01', 'velocity', 62)
    runtime.control('restart')
    assert runtime.elapsed == runtime.progress == runtime.beat == 0
    assert not runtime.playing and not runtime.paused
    assert runtime.last_decisions is None and not runtime.pending_windows
    assert not runtime.sounding
    if allocated:
        assert runtime.timeline.window_index == runtime.next_window == 0
    # Un messaggio già in volo non deve riavviare la simulazione.
    now[0] += 10
    receive(beat=9, playing=1, epoch=0); runtime.tick()
    assert runtime.state == 'stopped'
    assert runtime.elapsed == runtime.progress == runtime.beat == 0
    assert runtime.last_decisions is None
    # La conferma di Stop mantiene lo zero, anche col trascorrere del tempo.
    receive(beat=0, playing=0, epoch=1); runtime.tick()
    now[0] += 100
    receive(beat=0, playing=0, epoch=1)
    runtime.tick()
    assert runtime.state == 'stopped' and runtime.progress == 0
    assert runtime.last_decisions is None
    assert runtime.session.parameters_at('voice_01', 0)['velocity'] == 62
    # La pressione di Play in Live apre una nuova epoca e consente la ripartenza.
    receive(beat=0, playing=1, epoch=2); runtime.tick()
    assert runtime.state == 'playing'
    assert runtime.last_decisions['section'] == 'opening'
