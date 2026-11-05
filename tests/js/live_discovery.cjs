const vm=require('vm'),fs=require('fs'),assert=require('assert');
let output=[], messages={}, c;
const objects={};
const patch={getnamed:name=>(objects[name]??={message:(...args)=>{
 (messages[name]??=[]).push(args);
 if(name==='receive_port'&&typeof args[0]==='number')c.receiveport(args[0]);
 if(name==='server_port'&&typeof args[0]==='number')c.backendport(args[0]);
 if(name==='endpoint_identity')c.endpoint(...args);
},setvalueof:(value)=>{(messages[name]??=[]).push(['setvalueof',value]);c.endpoint(value);}})};
let trackName='synth', position=2;
function LiveAPI(callback,path){
 this.id=path==='this_device'?42:12;
 this.path=path==='this_device'?`"live_set tracks ${position} devices 1"`:path;
 this.get=key=>key==='name'?[trackName]:[];
}
c={patcher:patch,LiveAPI,outlet:(...args)=>output.push(args),arrayfromargs:a=>Array.from(a)};
vm.createContext(c);c.include=name=>vm.runInContext(fs.readFileSync('m4l/'+name,'utf8'),c);
vm.runInContext(fs.readFileSync('m4l/desnivel_voice.js','utf8'),c);
function decode(entry){return JSON.parse(Buffer.from(Array.from(entry[1]).slice(1)).toString('utf8'));}
function receive(message){c.receive(...Buffer.from(JSON.stringify(message),'utf8'));}
c.endpoint(0);
c.announce();
let discovery=decode(output.find(o=>o[0]===4));
assert.equal(discovery.action,'discover');assert.equal(discovery.reply_port,10042);
assert.equal(discovery.track.name,'synth');assert.equal(discovery.track.index,2);
assert.equal(c.connected,false);
const endpoint=discovery.device_id, instance=discovery.instance;
assert.match(endpoint,/^endpoint_\d+_\d+$/);
assert.deepEqual(messages.endpoint_identity.at(-1),['setvalueof',endpoint]);
c.endpoint(0);assert.equal(c.endpointId,endpoint);
c.endpoint('symbol',endpoint);assert.equal(c.endpointId,endpoint);
const binding={version:1,kind:'binding',instance,device_id:endpoint,voice:'melody',backend_port:9006};
receive({...binding,device_id:'other'});assert.equal(c.connected,false);
receive(binding);assert.equal(c.connected,true);assert.equal(c.voiceId,'melody');
let hello=decode(output.filter(o=>o[0]===0).at(-1));
assert.equal(hello.device_id,endpoint);assert.equal(hello.action,'hello');
const serial=hello.serial;
receive(binding);hello=decode(output.filter(o=>o[0]===0).at(-1));
assert(hello.serial>serial);assert.equal(c.instance,instance);
trackName='renamed';position=5;c.announce();
discovery=decode(output.filter(o=>o[0]===4).at(-1));
assert.equal(discovery.device_id,endpoint);assert.equal(discovery.track.name,'renamed');assert.equal(discovery.track.index,5);
receive({...binding,kind:'release'});assert.equal(c.connected,false);assert.equal(c.voiceId,'');
c.announce();assert.equal(decode(output.filter(o=>o[0]===4).at(-1)).device_id,endpoint);
c.liveDeviceId=0;c.receiveport(17000);c.announce();assert.equal(c.replyPort,17000);
console.log('live_discovery: identità persistente, associazione, rinnovo, rinomina, riordino e rilascio verificati');
