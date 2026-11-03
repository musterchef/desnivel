const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
let clockMs=0, reads=0, liveReady=false, own=20, stringIds=false, allocations=0, writes=[], packets=[], all=[10,20,50,30,40,60], next=100;
const objects=new Map();
function snake(id){
 const parameters=[];
 for(const [name,min,max] of [['Export_State',0,1],['Scales',0,36],['Length_Min_ms',10,10000],['Length_Max_ms',10,10000],
  ...['Notes','Gates','Velocities'].flatMap(lane=>[['Snake_Shape',0,13],['Speed',0,4],['Length',1,16],['Direction',0,4],['Steps_Shift',1,100]].map(([key,min,max])=>[lane+'_Sequencer_'+key,min,max])),
  ...Array.from({length:16},(_,i)=>String(i+1).padStart(2,'0')).flatMap(s=>[
   ['Note_'+s,0,83],['Gate_'+s,0,1],['Velocity_'+s,0,127],['Length_'+s,0,127]])]){
  const ident=next++;parameters.push(ident);objects.set(ident,{name,min,max,value:min,is_quantized:0});
 }
 objects.set(id,{parameters});
}
snake(10);snake(30);
for(const id of [20,40])objects.set(id,{type:4});
for(const id of [50,60])objects.set(id,{type:1});
function ids(list){return list.flatMap(id=>['id',id]);}
class LiveAPI{
 constructor(_,path){allocations++;this.self=path==='this_device';this.ident=this.self?(liveReady?own:0):Number(path.split(' ')[1]);}
 get unquotedpath(){return 'live_set tracks 0 devices '+all.indexOf(Number(this.id));}
 get id(){const value=this.self&&this.ident?own:this.ident;return stringIds?String(value):value;}
 set id(value){this.ident=Number(value);this.self=false;}
 goto(path){assert.equal(path,'this_device');this.self=true;this.ident=liveReady?own:0;}
 get(key){
  reads++;
  if(!Number(this.id))return ['id',0];
  if(key==='canonical_parent')return ['id',1];
  if(key==='devices')return ids(all);
  if(key==='parameters')return ids(objects.get(Number(this.id)).parameters);
  return [objects.get(Number(this.id))[key]];
 }
 set(key,value){objects.get(Number(this.id))[key]=value;writes.push([Number(this.id),key,value]);}
}
const bindings=[];
const c={messnamed:()=>{},patch:{getnamed:()=>({message:(...args)=>bindings.push(args)})},utf8text:bytes=>Buffer.from(bytes).toString('utf8'),Date:{now:()=>clockMs},LiveAPI,backendSession:'session',outlet:(...args)=>packets.push(args),status:()=>{}};
vm.createContext(c);vm.runInContext(fs.readFileSync('m4l/desnivel_snake_control.js','utf8'),c);
const adapter=c.DesnivelSnakeControl;
function snapshot(){clockMs+=1000;return adapter.snapshot();}
assert.equal(snapshot().ready,false);
assert.equal(writes.length,0);
liveReady=true;
assert(snapshot().ready,'a reference created before Live is ready must recover');
assert(snapshot().has_instrument);
// LiveAPI identifiers must compare by value, including string representations.
stringIds=true;assert(snapshot().ready);
const steadyAllocations=allocations;
const steadyReads=reads;
for(let i=0;i<1000;i++)assert(adapter.snapshot().ready);
assert.equal(reads,steadyReads,'transport polling must use cached status within one second');
assert.equal(allocations,steadyAllocations,'status polling must reuse LiveAPI handles');
function command(serial,parameters,session='session'){adapter.receive({kind:'parameters',session,serial,parameters});}
command(1,{Note_01:36,Gate_01:1,Length_Min_ms:2500,Length_Max_ms:2500,Length_01:0});
assert.equal(snapshot().applied,1);
assert.equal(allocations,steadyAllocations,'bank writes must reuse parameter handles');
clockMs++;
function telemetry(data){adapter.telemetry([...Buffer.from(JSON.stringify(data))]);}
telemetry({version:1,device_path:'live_set tracks 99 devices 0',source:'other',serial:1,captured_ms:clockMs});
assert.equal(adapter.snapshot().telemetry,null);
telemetry({version:1,device_path:'live_set tracks 0 devices 0',source:'own',serial:1,captured_ms:clockMs});
assert.equal(adapter.snapshot().telemetry.source,'own');
clockMs+=751;assert.equal(adapter.snapshot().telemetry,null,'old snapshots must not remain readable');
const initialWrites=writes.length;
command(2,{Notes_Sequencer_Snake_Shape:6,Notes_Sequencer_Speed:2});
assert.equal(writes.length,initialWrites+2);
command(3,{Notes_Sequencer_Snake_Shape:6,Notes_Sequencer_Speed:2});
assert.equal(writes.length,initialWrites+2,'unchanged values must not be written again');
assert(writes.every(([id])=>objects.get(10).parameters.includes(id)));
const count=writes.length;command(1,{Note_01:37});command(2,{Note_01:37},'other');
assert.equal(writes.length,count);
// Moving the component changes only the immediate sibling; there is no global search.
own=40;assert(snapshot().ready);writes=[];command(4,{Note_01:48});
assert(writes.every(([id])=>objects.get(30).parameters.includes(id)));
writes=[];command(5,{Note_01:50,Length_Min_ms:20000});
assert(writes.every(([id])=>objects.get(id).name.startsWith('Gate_'))); // Batch validation precedes note writes.
assert(snapshot().error);
command(6,{Gate_01:1});assert.equal(snapshot().error,null);
adapter.panic();assert.equal(snapshot().applied,-1);assert.deepEqual(packets.at(-1),[1,'panic']);
all=[10,20,30,40];assert(snapshot().ready);assert.equal(snapshot().has_instrument,false);
all=[10,20,40];assert.equal(snapshot().ready,false);
assert(bindings.some(args=>args[1]==='desnivel.snake.live_set_tracks_0_devices_0'));
const invalidAllocations=allocations;
for(let i=0;i<100;i++)assert.equal(snapshot().ready,false);
assert.equal(allocations,invalidAllocations,'an incompatible predecessor must not allocate on retries'); // Non-Snake predecessor is rejected.
console.log('snake_control: istanze isolate, validazione dei banchi, seriali, errori e panic verificati');
