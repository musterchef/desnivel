from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from desnivel.adapters.voice_device import VoiceDeviceBridge
from desnivel.cli.snake_control import SnakeControlSession


def configuration(components):
    config = json.loads((Path(__file__).resolve().parents[2]/'presets/snake.json').read_text())
    config['components'] = components
    return config


def plan(start=0, intensity=None, change=None, persistence=None):
    return dict(start=start, length_beats=4, section_index=0, section='ascent', root=60, scale='minor',
                adaptive_context=dict(intensity=intensity, change=change, persistence=persistence), voices={})


def setup(components=None, configure=None):
    sent=[]
    def server(voices, port, *callbacks):
        return SimpleNamespace(bridge=VoiceDeviceBridge(voices,lambda *args: sent.append(args)),
                               server=SimpleNamespace(timeout=None), poll=lambda:None,close=lambda:None)
    config = configuration(components or {'snake_a':{'role':'melody','mode':'autonomous','source':'a'}})
    if configure:
        configure(config)
    session=SnakeControlSession(config, {'a':{'name':'lead'}},server_factory=server)
    def receive(name='snake_a',serial=1,applied=-1):
        message=dict(version=1,voice=name,instance=name,reply_port=9201 if name=='snake_a' else 9202,
                     action='hello',serial=serial,capabilities=['bank_control'],device_state=dict(ready=True,source_protocol=1,has_instrument=False,applied=applied,error=None))
        session.server.bridge.handle(message)
        session.on_message(session.server.bridge,message)
    state=dict(state='playing',section=dict(index=0,name='ascent',root=60,scale='minor'),planning=dict(current=plan()))
    return session,sent,receive,state


def test_current_context_and_retries_are_isolated_between_instances():
    session,sent,receive,state=setup({'snake_a':{'role':'melody','mode':'autonomous','source':'a'},
                                     'snake_b':{'role':'sustained_texture','mode':'autonomous','source':'a'}})
    receive();receive('snake_b')
    original=deepcopy(state)
    session.tick(state)
    packets=[item for item in sent if item[2]['kind']=='parameters']
    assert [item[0] for item in packets]==[9201,9202]
    assert packets[0][2]['parameters']['Length_Min_ms'] < packets[1][2]['parameters']['Length_Min_ms']
    session.tick(state)
    assert sent[-1][2] == packets[-1][2]  # Same revision until acknowledged.
    receive(serial=2,applied=packets[0][2]['serial'])
    receive('snake_b',serial=2,applied=packets[1][2]['serial'])
    before=len(sent);session.tick(state)
    assert len(sent)==before and state==original
    state['state']='paused';session.tick(state)
    assert set(sent[-1][2]['parameters'].values())=={0}


def test_role_and_manual_controls_remain_distinct_and_coordination_uses_current_plan():
    session,sent,receive,state=setup();receive()
    spec=session.server.bridge.voices['snake_a']
    spec.apply_parameter('velocity',70)
    spec.apply_role('sustained_texture')
    values=spec.read_values()
    assert values['length_ms']==2500 and values['velocity']==70
    spec.apply_manual('velocity',False)
    assert spec.read_values()['velocity']==48
    spec.apply_parameter('mode','coordinated')
    state['planning']['current']=None
    session.tick(state)
    assert 'attesa' in session.components['snake_a']['notice']
    state['planning']['upcoming']=[dict(voices={'a':{'notes':[dict(beat=0,pitch=90,duration=4,velocity=90)]}})]
    session.tick(state)
    assert set(sent[-1][2]['parameters'].values())=={0}
    state['planning']['current']={**plan(), 'voices':{'a':{'notes':[dict(beat=0,pitch=67,duration=4,velocity=90)]}}}
    session.tick(state)
    assert (sent[-1][2]['parameters']['Note_01']+24)%12==7


def test_configuration_validation_does_not_open_network_in_preview():
    with pytest.raises(ValueError):
        SnakeControlSession({'port':0,'components':{}},{'a':{'name':'lead'}},server_factory=None)
    session=SnakeControlSession(configuration({
        'snake':{'role':'melody','mode':'autonomous','source':'a'}}),{'a':{'name':'lead'}},server_factory=None)
    assert session.server is None
    session.close()


@pytest.mark.parametrize('section,value', [('music', {}), ('paths', [15])])
def test_invalid_recipes_are_rejected_before_opening_the_server(section, value):
    config = configuration({'snake':{'role':'melody','mode':'autonomous','source':'a'}})
    config[section] = value
    def server(*args):
        pytest.fail('la configurazione deve essere validata prima di aprire il server')
    with pytest.raises(ValueError, match=section):
        SnakeControlSession(config, {'a':{'name':'lead'}}, server_factory=server)


@pytest.mark.parametrize('source', [None, [], {}, 1])
def test_invalid_component_sources_raise_configuration_errors(source):
    config = configuration({'snake':{'role':'melody','mode':'autonomous','source':source}})
    with pytest.raises(ValueError, match='componente Snake'):
        SnakeControlSession(config, {'a':{'name':'lead'}}, server_factory=None)


def test_configured_recipe_reaches_device_banks_without_changing_other_sessions():
    def configure(config):
        config['paths'] = [14]
        music = config['music']
        music['roles']['melody'] = {
            'parameters': dict(octave=0, activity=.25, velocity=70, length_ms=400, movement=0.),
            'pulse': dict(slowest='8n', fastest='8n'),
            'response': dict(activity=.125, velocity=0., articulation=0.)}
        music['adaptation'] = {key: 4. if key == 'transition_beats' else 0.
                               for key in music['adaptation']}
        music['phrasing'] = dict(accents=[0.], velocity_accent=0., velocity_movement=0.,
                                 length_accent=0., length_movement=0.)
    session,sent,receive,state = setup(configure=configure)
    receive()
    for start, gates in ((0, 5), (4, 5), (8, 5)):
        state['planning']['current'] = plan(start,1.,1.,0.)
        session.tick(state)
        packet = sent[-1][2]['parameters']
        assert sum(packet[f'Gate_{i:02}'] for i in range(1,17)) == gates
        assert packet['Notes_Sequencer_Speed'] == 2  # 8n anche nel tratto intenso.
        assert packet['Notes_Sequencer_Snake_Shape'] == 13
        assert packet['Length_Min_ms'] == packet['Length_Max_ms'] == 400
        assert {packet[f'Velocity_{i:02}'] for i in range(1,17)} == {70}
    other,_,_,_ = setup()
    assert other.music['roles']['melody']['parameters']['activity'] == .4
    assert other.paths == (1,7,5,11,9)


@pytest.mark.parametrize('role,slow,fast', [('melody',2,1), ('bass_line',3,1), ('sustained_texture',4,2)])
@pytest.mark.parametrize('intensity', [0., 1.])
def test_first_window_already_selects_pulse_from_journey_and_role(role, slow, fast, intensity):
    session,sent,receive,state = setup({'snake_a':{'role':role,'mode':'autonomous','source':'a'}})
    receive()
    state['planning']['current'] = plan(0,intensity)
    session.tick(state)
    parameters = sent[-1][2]['parameters']
    for lane in ('Notes','Gates','Velocities'):
        assert parameters[f'{lane}_Sequencer_Speed'] == (fast if intensity else slow)


def test_gates_fill_before_the_faster_grid_and_compensate_its_double_speed():
    session,sent,receive,state = setup()
    receive()
    for index, (intensity, speed, count) in enumerate(((0.,2,4), (.15,2,6), (.3,2,8), (.32,1,4), (1.,1,8))):
        for offset in (0,4,8,12):
            state['planning']['current'] = plan(index*16+offset,intensity)
            session.tick(state)
        parameters = sent[-1][2]['parameters']
        assert parameters['Notes_Sequencer_Speed'] == speed
        assert sum(parameters[f'Gate_{i:02}'] for i in range(1,17)) == count


def test_density_transition_precedes_a_change_of_grid_after_an_intense_window():
    session,_,receive,state = setup()
    receive()
    rates = []
    for start, intensity in ((0,0.), (4,1.), (8,1.), (12,1.)):
        state['planning']['current'] = plan(start,intensity)
        session.tick(state)
        rates.append(session.components['snake_a']['decisions']['attack_rate']['effective'])
    assert rates == pytest.approx([.56,.56,1.32,2.08])


@pytest.mark.parametrize('control,value', [('activity',.25), ('pulse','2n')])
def test_one_manual_rhythm_control_disables_compensation_and_remains_fixed(control, value):
    session,sent,receive,state = setup()
    receive()
    voice = session.server.bridge.voices['snake_a']
    voice.apply_parameter(control,value)
    for start, intensity in ((0,0.), (4,1.), (8,1.), (12,1.)):
        state['planning']['current'] = plan(start,intensity)
        session.tick(state)
        assert voice.read_values()[control] == value
        assert 'attack_rate' not in session.components['snake_a']['decisions']
        if control == 'activity':
            packet = sent[-1][2]['parameters']
            assert sum(packet[f'Gate_{i:02}'] for i in range(1,17)) == 4
    voice.apply_manual(control,False)
    state['planning']['current'] = plan(16,1.)
    session.tick(state)
    assert 'attack_rate' in session.components['snake_a']['decisions']


def test_missing_intensity_and_disabled_adaptation_report_the_slow_limit():
    session,_,receive,state = setup()
    receive()
    session.tick(state)
    assert session.server.bridge.voices['snake_a'].read_values()['pulse'] == '8n'
    assert 'intensità non disponibile' in session.components['snake_a']['notice']
    state['planning']['current'] = plan(4,1.)
    state['adaptation_enabled'] = False
    session.tick(state)
    assert session.server.bridge.voices['snake_a'].read_values()['pulse'] == '8n'
    assert 'adattamento disattivato' in session.components['snake_a']['notice']


def test_real_component_handshake_and_parameter_packet_use_only_its_receive_port():
    import json
    import socket
    from pythonosc.udp_client import SimpleUDPClient
    from pythonosc.osc_packet import OscPacket
    from desnivel.adapters.voice_device import CONTROL_ADDRESS

    # Bind an ephemeral backend port, without changing production port validation.
    from desnivel.cli.voice_device import VoiceDeviceServer
    def factory(voices, port, *callbacks):
        return VoiceDeviceServer(voices,0,*callbacks)
    session=SnakeControlSession(configuration({
        'snake':{'role':'melody','mode':'autonomous','source':'a'}}), {'a':{'name':'lead'}},server_factory=factory)
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as receiver:
        receiver.bind(('127.0.0.1',0));receiver.settimeout(1)
        client=SimpleUDPClient('127.0.0.1',session.server.server.server_address[1])
        message=dict(version=1,voice='snake',instance='component',reply_port=receiver.getsockname()[1],
                     serial=1,action='hello',capabilities=['bank_control'],device_state=dict(ready=True,source_protocol=1,applied=-1,error=None))
        client.send_message(CONTROL_ADDRESS,list(json.dumps(message).encode()))
        import select
        assert select.select([session.server.server], [], [], 1)[0]
        try:
            session.tick(dict(state='playing',section=dict(index=0,name='level',root=60,scale='minor'),planning={'current':plan()}))
            messages=[]
            fragments={}
            while len(messages)<2:
                packet=OscPacket(receiver.recv(65535))
                params=packet.messages[0].message.params
                if params[0]==-1:
                    identity=tuple(params[1:3])
                    chunks=fragments.setdefault(identity,{})
                    chunks[params[3]]=params[5:]
                    if sum(map(len,chunks.values()))!=params[4]:
                        continue
                    params=[byte for offset in sorted(chunks) for byte in chunks[offset]]
                messages.append(json.loads(bytes(params).decode()))
            assert [m['kind'] for m in messages]==['state','parameters']
            assert messages[1]['voice']=='snake' and messages[1]['instance']=='component'
            assert messages[1]['parameters']['Note_01']==36
        finally:
            session.close()
            client._sock.close()


def test_setup_readiness_requires_connection_banks_and_instrument():
    session,_,receive,_=setup()
    assert 'collegato' in session.setup_missing()['snake_a']
    receive()
    assert 'strumento' in session.setup_missing()['snake_a']
    session.components['snake_a']['has_instrument']=True
    assert session.setup_missing()=={}
    session.components['snake_a']['error']='Snake incompatibile'
    assert session.setup_missing()['snake_a']=='Snake incompatibile'


@pytest.mark.parametrize('role', ('melody', 'bass_line', 'sustained_texture'))
def test_journey_changes_all_banks_and_paths_for_each_role_with_stable_polling(role):
    session,sent,receive,state=setup({'snake_a':{'role':role,'mode':'autonomous','source':'a'}})
    receive()
    def advance(start, intensity, change, persistence):
        state['planning']['current']=plan(start,intensity,change,persistence)
        session.tick(state)
        return deepcopy(sent[-1][2])
    for start in (0,4,8):
        calm=advance(start,0.,0.,1.)
    # Upcoming material never changes the currently sounding interpretation.
    state['planning']['upcoming']=[plan(12,1.,1.,0.)]
    session.tick(state)
    assert sent[-1][2]==calm
    for start in (12,16,20,24):
        active=advance(start,1.,1.,0.)
    a,b=calm['parameters'],active['parameters']
    limits = {'melody': (4, 8), 'bass_line': (3, 6), 'sustained_texture': (1, 3)}
    assert (sum(a[f'Gate_{i:02}'] for i in range(1,17)),
            sum(b[f'Gate_{i:02}'] for i in range(1,17))) == limits[role]
    assert sum(v for k,v in b.items() if k.startswith('Gate_')) > sum(v for k,v in a.items() if k.startswith('Gate_'))
    for prefix in ('Velocity_', 'Length_'):
        assert {k:v for k,v in a.items() if k.startswith(prefix)} != {k:v for k,v in b.items() if k.startswith(prefix)}
    assert a['Notes_Sequencer_Snake_Shape'] != b['Notes_Sequencer_Snake_Shape']
    assert a['Notes_Sequencer_Speed'] != b['Notes_Sequencer_Speed']
    assert b['Notes_Sequencer_Speed'] >= 1  # L'automatismo non raggiunge i 32n.
    assert len({v for k,v in b.items() if k.startswith('Velocity_')}) > 1
    assert b['Length_Max_ms'] > b['Length_Min_ms']
    session.tick(state)
    assert sent[-1][2]==active


@pytest.mark.parametrize('pulse,speed', [('2n', 4), ('32n', 0)])
def test_manual_overrides_survive_terrain_changes_and_return_to_auto(pulse, speed):
    session,sent,receive,state=setup();receive()
    spec=session.server.bridge.voices['snake_a']
    for name,value in dict(activity=.25,velocity=64,length_ms=500,movement=0.,pulse=pulse).items():
        spec.apply_parameter(name,value)
    for start in (0,4,8,12):
        state['planning']['current']=plan(start,1.,1.,0.)
        session.tick(state)
    values=spec.read_values()
    assert {k:values[k] for k in ('activity','velocity','length_ms','movement','pulse')} == dict(
        activity=.25,velocity=64,length_ms=500,movement=0.,pulse=pulse)
    packet=sent[-1][2]['parameters']
    assert sum(packet[f'Gate_{i:02}'] for i in range(1,17))==4
    assert packet['Notes_Sequencer_Snake_Shape']==0 and packet['Notes_Sequencer_Speed']==speed
    spec.apply_manual('activity',False)
    for start in (16,20,24):
        state['planning']['current']=plan(start,1.,1.,0.)
        session.tick(state)
    assert .4 < spec.read_values()['activity'] <= .52
    assert spec.read_values()['velocity']==64


def test_environment_uses_accepted_intent_and_disabled_adaptation_preserves_role_baseline():
    session,_,receive,state=setup();receive()
    for start in (0,4,8,12):
        current=plan(start,.5,0.,.5)
        current['adaptive_context'].update(dynamic_pressure=1.,material_change=1.)
        state['planning']['current']=current
        session.tick(state)
    values=session.server.bridge.voices['snake_a'].read_values()
    assert values['velocity'] > 85 and values['movement'] > .25
    state['adaptation_enabled']=False
    session.tick(state)
    values=session.server.bridge.voices['snake_a'].read_values()
    assert values['velocity']==85 and values['movement']==.25


def test_accepted_forecasts_hold_banks_until_their_windows_finish_and_require_new_ack():
    from desnivel.music.sources import MusicalSource
    from desnivel.music.phrases import Phrase, Note
    session,sent,receive,state=setup();receive()
    state['planning']['current']=plan(0,0.,0.,1.)
    session.tick(state)
    component=session.components['snake_a'];component['has_instrument']=True
    class Observed:
        def project(self,role,start,length,**kwargs):
            return MusicalSource(role,Phrase(length,(Note(0,67,length,80),)))
        def invalidate(self,reason):pass
    component['forecast']=Observed()
    component['applied']=component['payload']['serial']
    first=session.forecasts(4,4,beat=0,bpm=120,epoch=0)['snake_a']
    assert first.phrase.notes[0].pitch==67 and component['hold_until']==8
    before=len(sent)
    state['transport']={'beat':4}
    state['planning']['current']=plan(4,1.,1.,0.)
    session.tick(state)
    assert component['pending'] and len(sent)==before
    unavailable=session.forecasts(8,4,beat=4,bpm=120,epoch=0)['snake_a']
    assert unavailable.phrase is None and 'attesa' in unavailable.unavailable_reason
    assert component['hold_until']==8  # No indefinite extension while waiting for a revision.
    state['transport']['beat']=8
    state['planning']['current']=plan(8,1.,1.,0.)
    session.tick(state)
    assert not component['pending'] and len(sent)>before
    assert session.forecasts(12,4,beat=8,bpm=120,epoch=0)['snake_a'].phrase is None
    component['applied']=component['payload']['serial']
    assert session.forecasts(12,4,beat=8,bpm=120,epoch=0)['snake_a'].phrase is not None


def test_silent_startup_packets_do_not_lock_out_the_initial_musical_material():
    session,_,receive,state=setup();receive()
    state['planning']['current']=None;session.tick(state)
    component=session.components['snake_a'];component['has_instrument']=True
    component['applied']=component['payload']['serial']
    assert session.forecasts(4,4,beat=0,bpm=120,epoch=0)['snake_a'].phrase is None
    assert component['hold_until']==0
