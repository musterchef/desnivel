from types import SimpleNamespace

import pytest

from desnivel.cli.snake_setup import CHECK_INTERVAL_S, SnakeSetup


def setup():
    now=[0.];calls=[];missing={'snake_01':'controllo non collegato'}
    session=SimpleNamespace(components={'snake_01':{}},port=9007,
        tick=lambda state: calls.append(('tick',state['state'])) or {},
        setup_missing=lambda:dict(missing), close=lambda:calls.append('close'))
    def create(*args):
        calls.append('create');return session
    guide=SnakeSetup('presets/snake.json',{'lead':{}},9006,clock=lambda:now[0],
                     create_session=create,connect=lambda port:calls.append(('connect',port)))
    return guide,now,calls,missing


def test_default_does_not_open_component_server_and_begin_is_nonblocking():
    guide,_,calls,_=setup()
    assert guide.snapshot()['status']=='idle'
    assert guide.tick({'state':'playing'})=={} and calls==[]
    guide.begin(playing=False)
    assert guide.waiting and calls==['create']
    assert 'traccia MIDI' in guide.snapshot()['instructions'][0]
    assert '9201' in guide.snapshot()['instructions'][1]
    guide.tick({'state':'playing'})
    assert ('tick','preparing') in calls
    assert ('connect',9201) in calls
    assert 'controllo non collegato' in guide.snapshot()['notice']


def test_timer_and_enter_probe_without_reopening_server_and_ready_needs_no_confirmation():
    guide,now,calls,missing=setup();guide.begin(playing=False)
    guide.tick({'state':'paused'})
    now[0]=CHECK_INTERVAL_S-1;guide.tick({'state':'paused'})
    assert calls.count(('connect',9201))==1
    guide.confirm();guide.tick({'state':'paused'})
    assert calls.count(('connect',9201))==2
    now[0]+=CHECK_INTERVAL_S;guide.tick({'state':'paused'})
    assert calls.count(('connect',9201))==3
    missing['snake_01']='inserisci uno strumento dopo il controllo'
    guide.confirm();guide.tick({'state':'paused'})
    assert 'strumento' in guide.snapshot()['notice'] and guide.waiting
    missing.clear();guide.tick({'state':'paused'})
    assert guide.snapshot()['status']=='ready' and not guide.waiting
    guide.begin(playing=False)
    assert calls.count('create')==1


def test_cancel_and_retry_clean_up_only_the_component_service():
    guide,_,calls,_=setup();guide.begin(playing=False)
    guide.cancel()
    assert guide.session is None and not guide.waiting and 'close' in calls
    assert guide.snapshot()['instructions']==[]
    guide.confirm();guide.cancel()
    guide.begin(playing=False)
    assert guide.waiting and calls.count('create')==2
    guide.close();assert guide.session is None


@pytest.mark.parametrize('playing,busy',[(True,False),(False,True)])
def test_setup_rejects_playback_and_recording_without_opening_anything(playing,busy):
    guide,_,calls,_=setup()
    with pytest.raises(ValueError,match='ferma Live'):
        guide.begin(playing=playing,recording_busy=busy)
    assert calls==[]


@pytest.mark.parametrize('complete',[False,True])
def test_normal_ensemble_guides_setup_and_stops_an_unexpected_play_without_advancing(tmp_path,monkeypatch,complete):
    import json
    import numpy as np
    from copy import deepcopy
    from desnivel.adapters.voice_device import VoiceDeviceBridge
    from desnivel.cli import ensemble, voice_device, snake_control, snake_setup
    from desnivel.trip import loader
    from tests.cli.test_journey_view import track

    source=track();source.samples['cum_dist_m']=np.array([0.,10.,10.,20.])
    monkeypatch.setattr(loader,'load_track',lambda *args,**kwargs:source)
    monkeypatch.setattr('desnivel.cli.weather_context.prepare_weather_context',lambda *args,**kwargs:None)
    sent=[];servers=[];frames=[];probes=[]
    class Server:
        def __init__(self,voices,port,*callbacks):
            self.bridge=VoiceDeviceBridge(voices,lambda *args:sent.append(args))
            self.server=self;self.port=port;self.count=0;self.closed=False;servers.append(self)
            if callbacks:self.on_message=callbacks[0]
        def poll(self):pass
        def close(self):self.closed=True
        def handle_request(self):
            self.count+=1
            if self.count==5:raise KeyboardInterrupt
            if self.count in (2,3):
                message=dict(version=1,voice='voice_01',instance='clock',reply_port=9101,
                    serial=self.count,action='hello',capabilities=['transport_control'],
                    transport=dict(beat=0.,playing=1 if self.count==2 else 0,epoch=self.count,bpm=120))
                self.bridge.handle(message);self.on_message(self.bridge,message)
            if self.count==3 and complete:
                component=dict(version=1,voice='snake_01',instance='snake',reply_port=9201,serial=1,action='hello',
                    capabilities=['bank_control'],device_state=dict(ready=True,source_protocol=1,has_instrument=True,applied=-1,error=None))
                servers[1].bridge.handle(component);servers[1].on_message(servers[1].bridge,component)
    monkeypatch.setattr(voice_device,'VoiceDeviceServer',Server)
    original=snake_setup.SnakeSetup
    def create_session(path,sources,main_port):
        return snake_control.SnakeControlSession(json.loads(path.read_text()),sources,server_factory=Server)
    def create_guide(*args):
        return original(*args,create_session=create_session,connect=lambda port:probes.append(port))
    monkeypatch.setattr(snake_setup,'SnakeSetup',create_guide)
    class Keys:
        def __enter__(self):self.count=0;return self
        def __exit__(self,*args):pass
        def poll(self):
            self.count+=1
            if self.count==1:
                assert len(servers)==1  # Four default voices; no Snake server at startup.
                return ['snake_setup']
            return ['setup_check'] if self.count==2 else [] if complete or self.count==4 else ['setup_cancel']
    monkeypatch.setattr('desnivel.cli.session_controls.TerminalControls',Keys)
    class View:
        def update(self,state):frames.append(deepcopy(state))
    monkeypatch.setattr('desnivel.cli.session_view.TerminalSessionView',View)
    assert ensemble.main(['--track','unused.gpx','--config','presets/organico.json',
                          '--manual-sections','--status-file',str(tmp_path/'state.json')])==0
    assert [s.port for s in servers]==[9006,9007]
    expected='ready' if complete else 'cancelled'
    assert [f['setup']['status'] for f in frames]==['waiting','waiting',expected,expected]
    assert not frames[-1]['controls']['paused']
    assert all(len(f['voices'])==4 and f['trip']['progress']==0 for f in frames)
    assert any(packet.get('kind')=='transport' and packet['action']=='pause' for _,_,packet in sent)
    assert not any(packet.get('kind')=='plan' and not packet['plan'].get('reset') for _,_,packet in sent)
    assert probes==[9201,9201]
    assert all(s.closed for s in servers)
