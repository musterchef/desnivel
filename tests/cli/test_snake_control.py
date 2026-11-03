from copy import deepcopy
from types import SimpleNamespace

import pytest

from desnivel.adapters.voice_device import VoiceDeviceBridge
from desnivel.cli.snake_control import SnakeControlSession


def plan(start=0, intensity=None, change=None, persistence=None):
    return dict(start=start, length_beats=4, section_index=0, section='ascent', root=60, scale='minor',
                adaptive_context=dict(intensity=intensity, change=change, persistence=persistence), voices={})


def setup(components=None):
    sent=[]
    def server(voices, port, *callbacks):
        return SimpleNamespace(bridge=VoiceDeviceBridge(voices,lambda *args: sent.append(args)),
                               server=SimpleNamespace(timeout=None), poll=lambda:None,close=lambda:None)
    session=SnakeControlSession({'port':9007,'components':components or {
        'snake_a':{'role':'melody','mode':'autonomous','source':'a'}}}, {'a':{'name':'lead'}},server_factory=server)
    def receive(name='snake_a',serial=1,applied=-1):
        message=dict(version=1,voice=name,instance=name,reply_port=9201 if name=='snake_a' else 9202,
                     action='hello',serial=serial,capabilities=['bank_control'],device_state=dict(ready=True,has_instrument=False,applied=applied,error=None))
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
    session=SnakeControlSession({'port':9007,'components':{
        'snake':{'role':'melody','mode':'autonomous','source':'a'}}},{'a':{'name':'lead'}},server_factory=None)
    assert session.server is None
    session.close()


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
    session=SnakeControlSession({'port':9007,'components':{
        'snake':{'role':'melody','mode':'autonomous','source':'a'}}}, {'a':{'name':'lead'}},server_factory=factory)
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as receiver:
        receiver.bind(('127.0.0.1',0));receiver.settimeout(1)
        client=SimpleUDPClient('127.0.0.1',session.server.server.server_address[1])
        message=dict(version=1,voice='snake',instance='component',reply_port=receiver.getsockname()[1],
                     serial=1,action='hello',capabilities=['bank_control'],device_state=dict(ready=True,applied=-1,error=None))
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
    assert sum(v for k,v in b.items() if k.startswith('Gate_')) > sum(v for k,v in a.items() if k.startswith('Gate_'))
    for prefix in ('Velocity_', 'Length_'):
        assert {k:v for k,v in a.items() if k.startswith(prefix)} != {k:v for k,v in b.items() if k.startswith(prefix)}
    assert a['Notes_Sequencer_Snake_Shape'] != b['Notes_Sequencer_Snake_Shape']
    assert a['Notes_Sequencer_Speed'] != b['Notes_Sequencer_Speed']
    assert len({v for k,v in b.items() if k.startswith('Velocity_')}) > 1
    assert b['Length_Max_ms'] > b['Length_Min_ms']
    session.tick(state)
    assert sent[-1][2]==active


def test_manual_overrides_survive_terrain_changes_and_return_to_auto():
    session,sent,receive,state=setup();receive()
    spec=session.server.bridge.voices['snake_a']
    for name,value in dict(activity=.25,velocity=64,length_ms=500,movement=0.,pulse='2n').items():
        spec.apply_parameter(name,value)
    for start in (0,4,8,12):
        state['planning']['current']=plan(start,1.,1.,0.)
        session.tick(state)
    values=spec.read_values()
    assert {k:values[k] for k in ('activity','velocity','length_ms','movement','pulse')} == dict(
        activity=.25,velocity=64,length_ms=500,movement=0.,pulse='2n')
    packet=sent[-1][2]['parameters']
    assert sum(packet[f'Gate_{i:02}'] for i in range(1,17))==4
    assert packet['Notes_Sequencer_Snake_Shape']==0 and packet['Notes_Sequencer_Speed']==4
    spec.apply_manual('activity',False)
    for start in (16,20,24):
        state['planning']['current']=plan(start,1.,1.,0.)
        session.tick(state)
    assert spec.read_values()['activity'] > .65
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
