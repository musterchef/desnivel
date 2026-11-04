const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
let nextId=10, queue=[], reports=[], failRoute=false, pendingRouting=[];
let now=0, rejectRouting=false, lastRejected=false;
const objects=new Map(), order=[];
const song={is_playing:0,current_song_time:0,record_mode:0,loop:1,punch_in:1,punch_out:0,count_in_duration:0,
 midi_recording_quantization:5,arrangement_overdub:1};
function object(data){const id=nextId++;objects.set(id,data);return id;}
function track(name,midi=true,voice=true){
 const devices=[...(voice?[object({name:'Desnivel_Voice'})]:[]),object({name:'instrument',parameter:37}),object({name:'reverb',parameter:.7})];
 const id=object({name,has_midi_input:Number(midi),is_frozen:0,can_be_armed:1,arm:0,color:123,solo:0,
  current_monitoring_state:1,devices,arrangement_clips:[object({name:'original clip'})],clip_slots:[],
  input_routing_type:{display_name:'All Ins',identifier:'all'},input_routing_channel:{display_name:'All Channels',identifier:'all'}});
 order.push(id);return id;
}
const source1=track('synth'),source2=track('bass');objects.get(source1).arm=1;
function ids(items){return items.flatMap(id=>['id',id]);}
class LiveAPI {
 constructor(_,path){this.song=path==='live_set';this.id=this.song?0:Number(path.split(' ')[1]);}
 get(prop){
  const obj=this.song?song:objects.get(this.id);if(!obj)throw Error('id rimosso');
  if(prop==='tracks')return ids(order);
  if(['devices','arrangement_clips','clip_slots'].includes(prop))return ids(obj[prop]);
  if(prop==='available_input_routing_types')return [JSON.stringify({[prop]:order.map(id=>({display_name:objects.get(id).name,identifier:String(id)}))})];
  if(prop==='available_input_routing_channels')return [JSON.stringify({[prop]:failRoute&&obj.input_routing_type.display_name==='texture'?[]:[{display_name:'Post FX',identifier:'fx'},{display_name:'Post Mixer',identifier:'mixer'}]})];
  if(prop.startsWith('input_routing_'))return [JSON.stringify({[prop]:obj[prop]})];
  return [obj[prop]];
 }
 set(prop,val){
  const obj=this.song?song:objects.get(this.id);
  if(prop==='count_in_duration')throw Error('sola lettura');
  if(this.song && prop==='record_mode') {pendingRouting.push(()=>{obj[prop]=val;});return;}
  if(prop.startsWith('input_routing_')){
   if(rejectRouting){lastRejected=true;return;}
   pendingRouting.push(()=>{obj[prop]=JSON.parse(val);});
  } else obj[prop]=val;
 }
 call(method,...args){
  if(this.song){
   if(method==='stop_playing')song.is_playing=0;
   else if(method==='start_playing'||method==='continue_playing')pendingRouting.push(()=>{song.is_playing=1;});
   else if(method==='delete_track'){objects.delete(order[args[0]]);order.splice(args[0],1);}
   else if(method==='create_audio_track')track('Audio',false,false);
   else if(method==='duplicate_track'){
    const old=objects.get(order[args[0]]), clone=JSON.parse(JSON.stringify(old));
    clone.devices=old.devices.map(id=>object({...objects.get(id)}));
    clone.arrangement_clips=old.arrangement_clips.map(id=>object({...objects.get(id)}));
    order.splice(args[0]+1,0,object(clone));
   } else throw Error(method);
  } else {
   const obj=objects.get(this.id);
   if(method==='delete_device')obj.devices.splice(args[0],1);
   else if(method==='delete_clip')obj.arrangement_clips=obj.arrangement_clips.filter(id=>id!==args[1]);
   else throw Error(method);
  }
 }
}
class Task {
 constructor(fn){this.fn=fn;this.cancelled=false;}
 schedule(){this.cancelled=false;queue.push(this);}
 cancel(){this.cancelled=true;}
}
function flush(){let count=0;while(queue.length||pendingRouting.length){assert(count++<200);now+=75;const apply=pendingRouting;pendingRouting=[];apply.forEach(fn=>fn());const task=queue.shift();if(task&&!task.cancelled)task.fn();}}
class Clock extends Date {getTime(){return now;}}
const context={LiveAPI,Task,Date:Clock};vm.createContext(context);
vm.runInContext(fs.readFileSync('m4l/desnivel_recording.js','utf8'),context);
const recorder=context.DesnivelRecording;
const send=(action,request,mode='both')=>recorder.handle({action,request,mode},report=>reports.push(report));
send('prepare',1);flush();
assert.equal(reports.at(-1).status,'ready');assert.equal(reports.at(-1).tracks.length,4);
assert.equal(order.length,6);
for(const id of order.filter(id=>![source1,source2].includes(id))){
 const t=objects.get(id);
 assert.equal(t.arm,0);assert.equal(t.current_monitoring_state,2);
 if(t.name.endsWith('_MIDI_REC')){
  assert.deepEqual(t.devices.map(id=>objects.get(id).name),['instrument','reverb']);
  assert.equal(objects.get(t.devices[0]).parameter,37);
  assert.equal(t.arrangement_clips.length,0);
  assert.equal(t.input_routing_channel.identifier,'fx');
 } else {assert.equal(t.devices.length,0);assert.equal(t.input_routing_channel.identifier,'mixer');}
}
assert.equal(objects.get(source1).devices.length,3);
assert.equal(objects.get(source1).arrangement_clips.length,1);
send('prepare',2);flush();assert.equal(order.length,6); // Riuso, nessuna copia ulteriore.
song.current_song_time=4;send('start',3);assert.equal(reports.at(-1).status,'error');assert.equal(song.record_mode,0);
song.current_song_time=0;send('start',4);
assert.notEqual(reports.at(-1).status,'recording');
recorder.heartbeat(); // L’attesa delle conferme non equivale a uno Stop dell’utente.
flush();
assert.equal(reports.at(-1).status,'recording');assert.equal(song.is_playing,1);assert.equal(song.record_mode,1);
assert.equal(song.loop,0);assert.equal(song.punch_in,0);assert.equal(objects.get(source1).arm,0);
assert.equal(song.midi_recording_quantization,0);assert.equal(song.arrangement_overdub,0);
assert(order.filter(id=>![source1,source2].includes(id)).every(id=>objects.get(id).arm===1));
song.is_playing=0;recorder.heartbeat();
flush();
assert.equal(reports.at(-1).status,'ready');assert.equal(song.record_mode,0);
assert.equal(song.loop,1);assert.equal(song.punch_in,1);assert.equal(objects.get(source1).arm,1);
assert.equal(song.midi_recording_quantization,5);assert.equal(song.arrangement_overdub,1);
// In caso di errore le nuove copie vengono rimosse; sorgenti e REC preesistenti restano.
const source3=track('texture'), originals=order.slice();
failRoute=true;send('prepare',5,'audio');flush();
assert.equal(reports.at(-1).status,'error');assert.deepEqual(order,originals);
assert.equal(objects.get(source3).devices.length,3);
failRoute=false;rejectRouting=true;
send('prepare',6,'audio');flush();
assert(lastRejected);
assert.equal(reports.at(-1).status,'error');
assert.match(reports.at(-1).error,/atteso.*ricevuto/);
assert.deepEqual(order,originals);
// Le sorgenti Snake producono audio e MIDI; le copie non devono generare note.
rejectRouting=false;
const snake=track('snake',true,false), snakeTrack=objects.get(snake);
snakeTrack.devices.unshift(object({name:'MDD_SNAKE_LengthBank'}),object({name:'Desnivel_Snake_Control'}));
const snakeDevices=snakeTrack.devices.slice();
send('prepare',7);flush();
assert.equal(reports.at(-1).status,'ready');
const snakeReports=reports.at(-1).tracks.filter(t=>t.source==='snake');
assert.deepEqual(Array.from(snakeReports,t=>t.type),['audio','midi']);
const snakeMidi=objects.get(order.find(id=>objects.get(id).name==='snake_MIDI_REC'));
const snakeAudio=objects.get(order.find(id=>objects.get(id).name==='snake_AUDIO_REC'));
assert.deepEqual(snakeMidi.devices.map(id=>objects.get(id).name),['instrument','reverb']);
assert.equal(snakeMidi.arrangement_clips.length,0);
assert.equal(snakeMidi.input_routing_type.identifier,String(snake));
assert.equal(snakeMidi.input_routing_channel.identifier,'fx');
assert.equal(snakeAudio.devices.length,0);
assert.equal(snakeAudio.input_routing_channel.identifier,'mixer');
assert.deepEqual(snakeTrack.devices,snakeDevices);
const preparedCount=order.length;
for(const mode of ['audio','midi']){
 send('prepare',8,mode);flush();
 assert.equal(reports.at(-1).status,'ready');
 assert.equal(order.length,preparedCount);
 assert(reports.at(-1).tracks.some(t=>t.source==='snake'&&t.type===mode));
}
console.log('live_recording: copie, FX, routing differito e annidato, riuso, armamenti, timeout e rollback verificati');
