const vm=require('vm'),fs=require('fs'),assert=require('assert');
let output=[],uiMessages={},uiObjects={};
const patch={getnamed:name=>(uiObjects[name]??={
 message:(...a)=>(uiMessages[name]??=[]).push(a),
 setboxattr:(nameAttr,value)=>(uiMessages[name]??=[]).push([nameAttr,value])})};
const c={patcher:patch,outlet:(...a)=>output.push(a),arrayfromargs:a=>Array.from(a)};
vm.createContext(c);c.include=name=>vm.runInContext(fs.readFileSync('m4l/'+name,'utf8'),c);
vm.runInContext(fs.readFileSync('m4l/desnivel_voice.js','utf8'),c);
function packet(message){return [...Buffer.from(JSON.stringify(message),'utf8')];}
function control(entry){
 assert.equal(entry[1][0],'/desnivel/v1/voice/control');
 const bytes=Array.from(entry[1]).slice(1);assert(bytes.every(n=>Number.isInteger(n)&&n>=0&&n<=255));
 return JSON.parse(Buffer.from(bytes).toString('utf8'));
}
// Il test usa oggetti leggibili; il confine Max riceve soltanto byte.
const receiveBytes=c.receive;
c.receive=text=>receiveBytes.apply(c,packet(JSON.parse(text)));
c.voice('part_a');c.receiveport(9101);c.connect();
let hello=control(output.find(a=>a[0]===0));
assert.equal(hello.voice,'part_a');assert.equal(hello.reply_port,9101);
const state={version:1,kind:'state',voice:'part_a',instance:c.instance,serial:1,session:'python-1',
 role:'melody',preset:null,presets:['soft'],controls:{velocity:{minimum:1,maximum:127,integer:true,value:80,manual:false}}};
c.receive(JSON.stringify({...state,instance:'other'}));assert.equal(c.state,null);
c.receive(JSON.stringify(state));assert.equal(c.state.role,'melody');
assert.deepStrictEqual(uiMessages.weather_display.at(-2),['set','meteo: stato non disponibile']);
c.receive(JSON.stringify({...state,weather:{configured:true,enabled:true,status:'active',label:'in uso · velocity',parameters:['velocity'],blocked_parameters:[]}}));
assert.deepStrictEqual(uiMessages.weather_display.at(-2),['set','meteo: in uso · velocity']);
c.receive(JSON.stringify({...state,weather:{configured:true,enabled:false,status:'disabled',label:'disattivato',parameters:[],blocked_parameters:[]}}));
assert.deepStrictEqual(uiMessages.weather_display.at(-2),['set','meteo: disattivato']);
c.receive(JSON.stringify(state));
assert.deepStrictEqual(uiMessages.manual_toggle.at(-1),['set',0]);
assert.deepStrictEqual(uiMessages.manual_display.at(-1),['set','auto']);
let beforeMode=output.filter(a=>a[0]===0).length;
c.receive(JSON.stringify({...state,controls:{velocity:{...state.controls.velocity,manual:true}}}));
assert.deepStrictEqual(uiMessages.manual_toggle.at(-1),['set',1]);
assert.deepStrictEqual(uiMessages.manual_display.at(-1),['set','manual']);
assert.equal(output.filter(a=>a[0]===0).length,beforeMode); // Un aggiornamento Python non diventa una modifica utente.
c.manual(0);assert.equal(control(output.at(-1)).action,'manual');
assert.equal(control(output.at(-1)).parameter,'velocity');
assert.strictEqual(control(output.at(-1)).value,false);
c.receive(JSON.stringify({version:1,kind:'error',voice:'part_a',instance:c.instance,error:'rejected'}));
assert.deepStrictEqual(uiMessages.manual_toggle.at(-1),['set',1]);
c.manual(1);assert.strictEqual(control(output.at(-1)).value,true);
beforeMode=output.length;c.manual(2);assert.equal(output.length,beforeMode);
c.receive(JSON.stringify({...state,controls:{velocity:{...state.controls.velocity,manual:null}}}));
assert.deepStrictEqual(uiMessages.manual_display.at(-1),['set','—']);
beforeMode=output.length;c.manual(1);assert.equal(output.length,beforeMode);
c.receive(JSON.stringify(state));
c.receive(JSON.stringify({...state,controls:{
 velocity:{...state.controls.velocity,manual:true},
 activity:{minimum:0,maximum:1,value:.5,manual:false}}}));
beforeMode=output.filter(a=>a[0]===0).length;
c.parameter(1);assert.deepStrictEqual(uiMessages.manual_display.at(-1),['set','auto']);
assert.equal(output.filter(a=>a[0]===0).length,beforeMode);
c.manual(1);assert.equal(control(output.at(-1)).parameter,'activity');
c.parameter(0);assert.deepStrictEqual(uiMessages.manual_display.at(-1),['set','manual']);
c.receive(JSON.stringify(state));
const beforePresence=output.filter(a=>a[0]===0).length;
c.receive(JSON.stringify({...state,presence:{automatic:.4,multiplier:2,effective:.8}}));
assert(uiMessages.presence_display.at(-1)[1].includes('40%'));
assert(uiMessages.presence_display.at(-1)[1].includes('80%'));
assert.deepStrictEqual(uiMessages.presence_multiplier.at(-1),['set',2]);
assert.deepStrictEqual(uiMessages.presence_slider.at(-1),['set',200]);
assert.equal(output.filter(a=>a[0]===0).length,beforePresence); // La visualizzazione non rimanda comandi.
c.presence_slider(50);assert.equal(control(output.at(-1)).action,'presence');
assert.equal(control(output.at(-1)).value,.5);
const afterPresence=output.length;
c.presence(11);assert.equal(output.length,afterPresence);
// Connect ripetuto conserva identità, seriali e note già pianificate.
const identity=c.instance, beforeSerial=c.serial;
const panics=output.filter(a=>a[0]===1&&a[1]==='panic').length;
c.connect();
const reconnect=control(output.at(-1));
assert.equal(reconnect.instance,identity);assert(reconnect.serial>beforeSerial);
assert.equal(output.filter(a=>a[0]===1&&a[1]==='panic').length,panics);
c.receive(JSON.stringify({...state,serial:2,supported_roles:['melody','sustained_texture'],role_mode:'section',active:true}));
c.receive(JSON.stringify({...state,serial:2,supported_roles:['melody'],role_mode:'section',active:false,next_entry_progress:.3}));
assert(uiMessages.role_display.at(-1)[1].includes('enters at 30%'));
c.receive(JSON.stringify({...state,serial:2,supported_roles:['melody','sustained_texture'],role_mode:'section',active:true,next_entry_progress:null}));
c.choose_role(2);assert.equal(control(output.at(-1)).role,'sustained_texture');
c.receive(JSON.stringify({...state,serial:3,supported_roles:['melody','sustained_texture'],role:'sustained_texture',role_mode:'manual',active:true}));
assert.deepStrictEqual(uiMessages.role_menu.at(-1),['set',2]);
c.choose_role(0);assert.equal(control(output.at(-1)).role,null);
c.receive(JSON.stringify({version:1,kind:'error',voice:'part_a',instance:c.instance,error:'unsupported'}));
assert.deepStrictEqual(uiMessages.role_menu.at(-1),['set',2]); // Ripristina la scelta confermata.
c.preset(0);assert.equal(control(output.at(-1)).preset,'soft');
c.value(50);assert.equal(control(output.at(-1)).value,50);
c.receive(JSON.stringify({...state,serial:4,can_save_presets:true,editable_presets:[]}));
c.preset_name('my','groove');c.save_preset(0);
assert.equal(control(output.at(-1)).preset,'my groove');
assert.equal(control(output.at(-1)).overwrite,false);
c.save_preset(1);assert.equal(control(output.at(-1)).overwrite,true);
c.slidervalue(500);assert.equal(control(output.at(-1)).value,64);
c.slidervalue(0);assert.equal(control(output.at(-1)).value,1);
c.slidervalue(1000);assert.equal(control(output.at(-1)).value,127);
// Le etichette descrittive e lo stato inattivo non cambiano le chiavi inviate.
c.receive(JSON.stringify({...state,serial:4,controls:{velocity:{...state.controls.velocity,
 label:'Intensità MIDI',inactive_reason:'Modalità di prova'}}}));
assert.deepStrictEqual(uiMessages.parameter_menu.at(-3),['append','[inattivo] intensità midi']);
assert(uiMessages.range_display.at(-1)[1].includes('inattivo'));
assert.deepStrictEqual(uiMessages.parameter_slider.at(-1),['annotation','velocity — intensità midi: Modalità di prova']);
c.value(55);assert.equal(control(output.at(-1)).parameter,'velocity');
assert.equal(control(output.at(-1)).value,55);
c.receive(JSON.stringify({...state,serial:4,controls:{velocity:{...state.controls.velocity,
 value_hint:'4/4 attacchi · saturo',description:'riepilogo dell’ultimo piano'}}}));
assert(uiMessages.range_display.at(-1)[1].includes('4/4 attacchi · saturo'));
assert(uiMessages.parameter_value.at(-1)[1].includes('riepilogo dell’ultimo piano'));
c.receive(JSON.stringify({...state,serial:4,controls:{velocity:{...state.controls.velocity,
 automation:{base:80,target:76,effective:80,source:'adaptive',reason:'contesto di prova'}}}}));
assert(uiMessages.range_display.at(-1)[1].includes('→ 76'));
assert(uiMessages.parameter_value.at(-1)[1].includes('base 80, obiettivo 76, effettivo 80'));
c.value(55);assert.equal(control(output.at(-1)).parameter,'velocity');
c.receive(JSON.stringify({...state,serial:4}));
assert(!uiMessages.range_display.at(-1)[1].includes('inattivo'));
assert.deepStrictEqual(uiMessages.parameter_toggle.slice(-2,-1)[0],['set',80]);
c.receive(JSON.stringify({...state,serial:4,controls:{follow_source:{minimum:0,maximum:1,integer:true,
 value:0,toggle:true,label:'Segui sorgente'}}}));
assert.equal(uiObjects.parameter_slider.hidden,true);
assert.equal(uiObjects.parameter_toggle.hidden,false);
c.value(1);assert.equal(control(output.at(-1)).parameter,'follow_source');
assert.equal(control(output.at(-1)).value,1);
const beforeInvalidToggle=output.filter(a=>a[0]===0).length;c.value(.5);
assert.equal(output.filter(a=>a[0]===0).length,beforeInvalidToggle);
c.receive(JSON.stringify({...state,serial:4}));
assert.equal(uiObjects.parameter_slider.hidden,false);
assert.equal(uiObjects.parameter_toggle.hidden,true);
// Le scelte nominali restano identificativi testuali anche riordinando il menu.
const choiceState={...state,serial:4,controls:{style:{label:'Stile',value:'house',
 choices:[['none','Nessuno'],['house','House classica'],['boom','Boom bap']]}}};
c.receive(JSON.stringify(choiceState));
assert.equal(uiObjects.parameter_choice.hidden,false);
assert.equal(uiObjects.parameter_value.hidden,true);
assert.equal(uiObjects.parameter_slider.hidden,true);
assert.equal(uiObjects.parameter_toggle.hidden,true);
assert.deepStrictEqual(uiMessages.parameter_choice.slice(-2,-1)[0],['set',1]);
c.choice(2);assert.equal(control(output.at(-1)).parameter,'style');
assert.equal(control(output.at(-1)).value,'boom');
const beforeBadChoice=output.filter(a=>a[0]===0).length;
c.choice(-1);c.choice(99);c.choice(.5);c.value(1);c.slidervalue(500);
assert.equal(output.filter(a=>a[0]===0).length,beforeBadChoice);
c.receive(JSON.stringify({...choiceState,controls:{style:{...choiceState.controls.style,
 choices:[['boom','Boom bap'],['none','Nessuno'],['house','House classica']]}}}));
c.choice(0);assert.equal(control(output.at(-1)).value,'boom');
c.receive(JSON.stringify(state)); // seriale vecchio: conserva la selezione corrente.
assert.equal(uiObjects.parameter_choice.hidden,false);
c.receive(JSON.stringify({...state,serial:4}));
assert.equal(uiObjects.parameter_choice.hidden,true);
assert.equal(uiObjects.parameter_value.hidden,false);
let count=output.filter(a=>a[0]===0).length;c.value(999);
assert.equal(output.filter(a=>a[0]===0).length,count);
let plan={version:1,kind:'plan',voice:'part_a',instance:c.instance,plan:{version:1,reset:true}};
c.receive(JSON.stringify({...plan,voice:'part_b'}));assert.notEqual(output.at(-1)[1][0],'planbytes');
c.receive(JSON.stringify(plan));assert.equal(output.at(-1)[1][0],'planbytes');
const liveCommand={version:1,kind:'transport',voice:'part_a',instance:c.instance,session:'python-1',serial:100,action:'restart'};
const rewindEpoch=c.epoch;
c.receive(JSON.stringify(liveCommand));
assert.equal(c.epoch,rewindEpoch); // La conferma attende il clock di Live fermo a zero.
assert.deepStrictEqual(output.filter(a=>a[0]===3),[
 [3,'call','stop_playing'],[3,'set','start_time',0],[3,'set','current_song_time',0]]);
c.clock(4800,0);assert.equal(c.epoch,rewindEpoch);
c.clock(0,0);assert.equal(c.epoch,rewindEpoch+1);
c.clock(0,0);assert.equal(c.epoch,rewindEpoch+1);
const liveCount=output.filter(a=>a[0]===3).length;
c.receive(JSON.stringify(liveCommand));assert.equal(output.filter(a=>a[0]===3).length,liveCount);
c.receive(JSON.stringify({...liveCommand,serial:101,action:'pause'}));
assert.deepStrictEqual(output.at(-1),[3,'call','stop_playing']);
c.receive(JSON.stringify({...state,serial:5,session:'python-2'}));
c.receive(JSON.stringify({...liveCommand,session:'python-2',serial:1,action:'resume'}));
assert.deepStrictEqual(output.at(-1),[3,'call','continue_playing']);
const afterNewSession=output.filter(a=>a[0]===3).length;
c.receive(JSON.stringify({...liveCommand,serial:102,action:'pause'}));
assert.equal(output.filter(a=>a[0]===3).length,afterNewSession);
c.lastReply=0;c.heartbeat();assert(output.some(a=>a[0]===1&&a[1]==='panic'));
c.disconnect();assert(!c.connected);c.receive(JSON.stringify(plan));assert.notEqual(output.at(-1)[1][0],'planbytes');
console.log('OK: identity, menus, validated values, plan routing, timeout and disconnect');

c.connect();
for(let i=0;i<1000;i++)c.clock(i*60,1);
const controls=output.filter(a=>a[0]===0);
assert(controls.every(entry=>entry[1][0]==='/desnivel/v1/voice/control'&&Array.from(entry[1]).slice(1).every(Number.isInteger)));
assert.equal(control(controls.at(-1)).transport.beat,999*60/480);
c.tempo(131);c.clock(1000*60,1);
assert.equal(control(output.at(-1)).transport.bpm,131);
c.tempo(0);c.tempo('invalid');c.clock(1001*60,1);
assert.equal(control(output.at(-1)).transport.bpm,131);
console.log('OK: 1000 clock con payload numerico, senza JSON come simboli Max');

// Le risposte grandi si applicano solo dopo la ricomposizione completa.
function fragments(message,stream,serial){
 const bytes=packet(message), frames=[];
 for(let offset=0;offset<bytes.length;offset+=1500)
  frames.push([-1,stream,serial,offset,bytes.length,...bytes.slice(offset,offset+1500)]);
 return frames;
}
const large={...state,instance:c.instance,serial:c.serial,session:'python-chunks',
 controls:{velocity:{...state.controls.velocity,automation:{base:80,target:75,effective:80,
 source:'adaptive',reason:'densità musicale 🚲 '.repeat(160)}}}};
const frames=fragments(large,7,1), previousState=c.state;
assert(frames.length>2);
receiveBytes.apply(c,frames.at(-1));
receiveBytes.apply(c,frames.at(-1)); // Il duplicato non completa il messaggio.
assert.strictEqual(c.state,previousState);
for(const frame of frames.slice(0,-1).reverse())receiveBytes.apply(c,frame);
assert.equal(c.state.controls.velocity.automation.reason,large.controls.velocity.automation.reason);
assert.equal(Object.keys(c.wireParts).length,0);
// Due invii distinti non condividono frammenti.
receiveBytes.apply(c,fragments(large,8,1)[0]);
receiveBytes.apply(c,fragments(large,9,1).at(-1));
assert.equal(Object.keys(c.wireParts).length,2);
for(let i=10;i<20;i++)receiveBytes.apply(c,fragments(large,i,1)[0]);
assert.equal(Object.keys(c.wireParts).length,8);
for(const key of c.wireOrder)c.wireParts[key].created-=2000;
c.expireWire();assert.equal(Object.keys(c.wireParts).length,0);
receiveBytes.apply(c,frames[0]);c.disconnect();
assert.equal(Object.keys(c.wireParts).length,0);
assert.throws(()=>c.wireBytes([-1,1,1,0,12001,1]));
console.log('OK: frammenti UTF-8 fuori ordine, duplicati, isolamento, scadenza e limiti');

// Large device state uses bounded numeric frames in the opposite direction too.
c.connected=true;output=[];
c.deviceAdapter={capabilities:['bank_control'],snapshot:()=>({telemetry:{text:'a'.repeat(7000)}})};
c.request('transport',{});
const requests=output.filter(e=>e[0]===0).map(e=>Array.from(e[1]).slice(1));
assert(requests.length>1);
assert(requests.every(p=>p[0]===-2&&p.length<=905));
const restored=Buffer.from(requests.flatMap(p=>p.slice(5))).toString('utf8');
assert.equal(JSON.parse(restored).device_state.telemetry.text.length,7000);

// Even messages below the old 1500-byte JSON threshold exceed Max's 5096-byte UDP buffer.
output=[];
c.deviceAdapter.snapshot=()=>({telemetry:{text:'a'.repeat(950)}});
c.request('transport',{});
const boundary=output.filter(e=>e[0]===0).map(e=>Array.from(e[1]));
const align=n=>Math.ceil(n/4)*4;
const oscBytes=frame=>align(Buffer.byteLength(frame[0])+1)+align(frame.length+1)+(frame.length-1)*4;
assert(boundary.length>1);
assert(boundary.every(frame=>frame[1]===-2&&oscBytes(frame)<=5096));
const boundaryBytes=boundary.flatMap(frame=>frame.slice(6));
assert(boundaryBytes.length>1013&&boundaryBytes.length<1500);
assert.equal(JSON.parse(Buffer.from(boundaryBytes).toString()).device_state.telemetry.text.length,950);
