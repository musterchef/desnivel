const vm=require('vm'),fs=require('fs'),assert=require('assert');
let out=[],local=[],clockMs=1000,controls={},lengths={};
for(let i=1;i<=16;i++){
 const s=String(i).padStart(2,'0');controls['desnivel_pitch_'+s]=60+i-1;
 controls['Gate_'+s]=1;controls['Velocity_'+s]=90;lengths['Length_'+s]=64;
}
lengths.Length_Min_ms=50;lengths.Length_Max_ms=500;controls.swing=0;
for(const bank of ['Notes','Gates','Velocities']){
 const pre=bank+'_Sequencer_';controls[pre+'Speed']=1;controls[pre+'Direction']=0;
 controls[pre+'Length']=16;controls[pre+'Steps_Shift']=0;controls[pre+'Snake_Shape']=0;
}
for(const lane of ['notes','gates','velocities'])controls['desnivel_shift_'+lane]=1;
const wrap=data=>({getnamed:n=>n in data?{getvalueof:()=>[data[n]]}:null});
const c={patcher:{getnamed:n=>({message:()=>{},subpatcher:()=>wrap(n==='Length_Bank'?lengths:controls)})},
 outlet:(...a)=>out.push(a),post:()=>{},
 Date:{now:()=>clockMs},LiveAPI:function(){this.id=77;this.unquotedpath='live_set tracks 5 devices 0';},messnamed:(...a)=>local.push(a)};
vm.createContext(c);vm.runInContext(fs.readFileSync('m4l/desnivel_snake_state.js','utf8'),c);
c.observe(1);c.legacy(1);
for(const name of ['notes','gates','velocities'])c.phase(name,4,480);
c.duration(2500);c.note(67,88,480);
c.snapshot(540,120,1);
let p=JSON.parse(out.pop()[2]);assert(!p.error,p.error);
assert.equal(p.device,77);assert.equal(p.observation_version,1);
assert.equal(p.active_notes[0].pitch,67);assert.equal(p.active_notes[0].remaining_ms,2500);
assert.equal(local.at(-1)[0],'desnivel.snake.live_set_tracks_5_devices_0');
assert.equal(local.at(-1)[1],'list');assert(local.at(-1)[2].every(n=>Number.isInteger(n)&&n>=0&&n<=255));
c.note(67,0,540);assert.equal(Object.keys(c.active).length,0);
assert.equal(p.state.notes[0],60);assert.equal(p.state.notes_lane.phase_beats,1.125);
assert.equal(p.state.lengths_ms[0],50+64/127*450);
controls.Notes_Sequencer_Direction=1;c.phase('notes',11,480);c.snapshot(540,120,1);
p=JSON.parse(out.pop()[2]);assert.equal(p.state.notes_lane.phase_beats,1.125);
controls.desnivel_shift_notes=2;c.snapshot(540,120,1);
p=JSON.parse(out.pop()[2]);assert(p.error.includes('Shift'));
c.snapshot(540,120,0);p=JSON.parse(out.pop()[2]);assert.equal(p.playing,0);assert.equal(Object.keys(c.phases).length,0);
console.log('OK: pitch reale, fase osservata, durata, stato non supportato, stop');

const legacyCount=out.length;c.legacy(0);c.snapshot(600,120,0);assert.equal(out.length,legacyCount);assert(local.length>0);

clockMs+=3000;const beforeExpiry=local.length;c.snapshot(600,120,0);assert.equal(c.observing,false);assert.equal(local.length,beforeExpiry);

c.subscribe('live_set tracks 99 devices 0',1);assert.equal(c.observing,false);
c.subscribe('live_set tracks 5 devices 0',1);assert.equal(c.observing,true);
const numericStart=local.length, legacyStart=out.length;
for(let i=0;i<1000;i++)c.snapshot(600,120,0);
assert.equal(local.length,numericStart+1000);assert.equal(out.length,legacyStart);
assert(local.slice(numericStart).every(frame=>frame[2].every(value=>Number.isInteger(value))));
