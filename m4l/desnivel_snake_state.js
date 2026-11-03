// Telemetria locale della mod Snake. Non modifica parametri o trasporto.
inlets = 1;
outlets = 1;
var serial = 0;
var phases = {}, epoch = 0, lastTick = -1, lastPlaying = 0;
var source = String(Date.now()) + '-' + String(Math.floor(Math.random()*1000000));
var root = this.patcher, seq = null, lengths = null, lastError = '';
var names = {notes:'Notes', gates:'Gates', velocities:'Velocities'};
var speeds = ['32n','16n','8n','4n','2n'];
var intervals = [0.125,0.25,0.5,1,2];
var deviceApi=null, active={}, durationMs=275, observing=false, exporting=false, observeUntil=0;
function initialize(){
    if(!deviceApi)deviceApi=new LiveAPI(null,'this_device');
    if(!(Number(deviceApi.id)>0))deviceApi.goto('this_device');
}
function subscribe(path,value){initialize();if(Number(deviceApi.id)>0 && path===String(deviceApi.unquotedpath))observe(value);}
function observe(value){observing=Number(value)!==0;observeUntil=Date.now()+2500;root.getnamed('desnivel_state_clock').message(Number(observing || exporting));}
function legacy(value){exporting=Number(value)!==0;root.getnamed('desnivel_state_clock').message(Number(observing || exporting));}
function duration(value){durationMs=Number(value);}
function note(pitch, velocity){
    pitch=Number(pitch);velocity=Number(velocity);
    if(velocity>0)active[pitch]={pitch:pitch,velocity:velocity,end_ms:Date.now()+durationMs};
    else delete active[pitch];
}
function publish(packet){
    packet.observation_version=1;
    initialize();
    packet.device=Number(deviceApi.id);packet.device_path=String(deviceApi.unquotedpath);packet.captured_ms=Date.now();
    var json=JSON.stringify(packet), binary=unescape(encodeURIComponent(json)), bytes=[];
    for(var i=0;i<binary.length;i++)bytes.push(binary.charCodeAt(i));
    if(observing && packet.device>0)messnamed('desnivel.snake.'+packet.device_path.replace(/ /g,'_'),'list',bytes);
    if(exporting)outlet(0,'/desnivel/v1/snake/state',json);
}
function scalar(p, name) {
    var box = p.getnamed(name);
    if (!box) throw new Error('controllo assente: '+name);
    if (box.maxclass === 'message') throw new Error('lettura message non ammessa: '+name);
    var value = box.getvalueof();
    if (value instanceof Array) value = value[0];
    value = Number(value);
    if (!isFinite(value)) throw new Error('valore non numerico: '+name);
    return value;
}
function phase(name, index, ticks) {
    phases[name] = {index:Number(index), ticks:Number(ticks)};
}
function snapshot(ticks, bpm, playing) {
    if(observing && Date.now()>observeUntil){observing=false;root.getnamed('desnivel_state_clock').message(Number(exporting));}
    if(!observing && !exporting)return;
    ticks=Number(ticks); playing=Number(playing);
    if (ticks < lastTick || playing !== lastPlaying) epoch++;
    lastTick=ticks;lastPlaying=playing;
    var packet={version:1, source:source, epoch:epoch, serial:++serial, beat:ticks/480, playing:playing};
    if (!playing) {phases={};active={};publish(packet);return;}
    try {
        if (!seq) seq=root.getnamed('desnivel_sequencer').subpatcher();
        if (!lengths) lengths=root.getnamed('Length_Bank').subpatcher();
        var state={notes:[],gates:[],velocities:[],lengths_ms:[],bpm:Number(bpm),midi_offset:0,swing:scalar(seq,'swing')};
        var lo=scalar(lengths,'Length_Min_ms'), hi=scalar(lengths,'Length_Max_ms');
        for(var i=1;i<=16;i++) {
            var suffix=(i<10?'0':'')+i;
            state.notes.push(scalar(seq,'desnivel_pitch_'+suffix));
            state.gates.push(scalar(seq,'Gate_'+suffix));
            state.velocities.push(Math.round(scalar(seq,'Velocity_'+suffix)));
            state.lengths_ms.push(Math.min(lo,hi)+scalar(lengths,'Length_'+suffix)/127*Math.abs(hi-lo));
        }
        for(var lane in names) {
            var prefix=names[lane]+'_Sequencer_', speed=scalar(seq,prefix+'Speed');
            var direction=scalar(seq,prefix+'Direction'), steps=scalar(seq,prefix+'Length');
            var shift=scalar(seq,'desnivel_shift_'+lane);
            if (shift!==1) throw new Error('Shift deve essere 1: '+lane+' (letto '+shift+')');
            if (direction!==0 && direction!==1) throw new Error('direzione non ancora supportata: '+lane);
            var ph=phases[lane], interval=intervals[speed];
            if(!ph || ph.ticks>ticks || ticks-ph.ticks>interval*480+20) throw new Error('attendo fase aggiornata: '+lane);
            var index=direction===0?ph.index:steps-1-ph.index;
            if(index<0 || index>=steps) throw new Error('attendo step valido: '+lane);
            var elapsed=packet.beat-Math.floor(ph.ticks/480/interval+0.000001)*interval;
            state[lane+'_lane']={shape:scalar(seq,prefix+'Snake_Shape')+1,speed:speeds[speed],steps:steps,
                direction:direction===0?'forwards':'backwards',phase_beats:index*interval+elapsed};
        }
        packet.state=state;packet.active_notes=[];
        for(var pitch in active){
            var remaining=active[pitch].end_ms-Date.now();
            if(remaining<=0){delete active[pitch];continue;}
            packet.active_notes.push({pitch:active[pitch].pitch,velocity:active[pitch].velocity,remaining_ms:remaining});
        }
        lastError='';
    } catch(e) {packet.error=String(e);if(packet.error!==lastError){post('Snake state: '+packet.error+'\n');lastError=packet.error;}}
    publish(packet);
}
