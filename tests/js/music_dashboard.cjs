const assert = require('node:assert/strict');
class Element {
  constructor(tag) {this.tag=tag;this.children=[];this.dataset={};this.open=false;this.textContent='';}
  append(...items) {this.children.push(...items);}
  replaceChildren(...items) {this.children=items;}
  get childElementCount() {return this.children.length;}
  querySelectorAll() {
    return this.children.flatMap(child=>[...(child.tag==='details'&&child.open?[child]:[]),...child.querySelectorAll()]);
  }
  get text() {return this.textContent+this.children.map(child=>child.text).join(' ');}
}
const elements=Object.fromEntries(['music-clock','music-plans','music-notice','music-voices','weather-summary'].map(id=>[id,new Element('div')]));
global.document={createElement:tag=>new Element(tag),getElementById:id=>elements[id]};
const music=require('../../src/desnivel/viewer/music.js');
const plan={start:4,length_beats:4,section:'ascent',root:60,scale:'major',voices:{a:{role:'melody',notes:[{}]}}};
const state={transport:{beat:4,playing:true},adaptation_enabled:true,
 planning:{current:plan,upcoming:[{...plan,start:8,section:'descent'}]},
 voices:{a:{name:'<synth>',connected:true,active:true,role:'melody',controls:{
 activity:{value:.4,manual:false,automation:{base:.5,target:.8,reason:'spazio'}},
 velocity:{value:80,manual:true,automation:{base:90,target:100,reason:'terreno'}}}}}};
music.render(state,false);
assert.match(elements['music-plans'].text,/salita.*beat 4–8.*discesa.*beat 8–12/);
assert.match(elements['music-voices'].text,/<synth>.*1 nota nella finestra/);
assert.match(elements['music-voices'].text,/0,4.*→ 0,8.*auto/);
assert.doesNotMatch(elements['music-voices'].text,/→ 100/);
state.voices.a.weather={configured:true,enabled:true,status:'active',label:'in uso · velocity',parameters:['velocity'],blocked_parameters:[]};
music.render(state,false);
assert.match(elements['weather-summary'].text,/in uso su <synth>/);
assert.match(elements['music-voices'].text,/meteo: in uso · velocity/);
state.voices.a.weather={configured:true,enabled:false,status:'disabled',label:'disattivato',parameters:[],blocked_parameters:[]};
music.render(state,false);
assert.match(elements['weather-summary'].text,/meteo: disattivato/);
assert.doesNotMatch(elements['music-voices'].text,/meteo: in uso/);
state.voices.a.weather={configured:true,enabled:false,pending:true,status:'active',label:'in uso · velocity · disattivazione in coda',parameters:['velocity'],blocked_parameters:[]};
music.render(state,false);
assert.match(elements['weather-summary'].text,/disattivazione in coda.*in uso su <synth>/);
state.voices.a.weather={configured:true,enabled:true,pending:true,status:'disabled',label:'attivazione in coda',parameters:[],blocked_parameters:[]};
music.render(state,false);
assert.match(elements['weather-summary'].text,/attivazione in coda/);
const details=elements['music-voices'].children[0].children.at(-1);
details.open=true;
state.voices.a.controls.activity.value=.6;
music.render(state,false);
assert.equal(elements['music-voices'].querySelectorAll()[0].open,true);
state.planning={current:null,upcoming:[]};
music.render(state,true);
assert.match(elements['music-plans'].text,/Nessun piano in esecuzione/);
assert.match(elements['music-notice'].text,/non aggiornati/);
music.markStale();assert.match(elements['music-notice'].text,/Collegamento interrotto/);
assert.match(elements['weather-summary'].text,/ultimo stato/);
console.log('music_dashboard: presente/futuro, valori auto/manual, dettagli e stato scaduto verificati');
