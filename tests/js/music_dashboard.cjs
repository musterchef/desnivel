const assert = require('node:assert/strict');
class Element {
  constructor(tag) {this.tag=tag;this.children=[];this.textContent='';}
  append(...items) {this.children.push(...items);}
  replaceChildren(...items) {this.children=items;}
  get text() {return this.textContent+this.children.map(child=>child.text).join(' ');}
}
const elements=Object.fromEntries(['music-clock','music-plans','music-notice','weather-summary'].map(id=>[id,new Element('div')]));
global.document={createElement:tag=>new Element(tag),getElementById:id=>elements[id]};
const music=require('../../src/desnivel/viewer/music.js');
const plan={start:4,length_beats:4,section:'ascent',root:60,scale:'major',voices:{a:{role:'melody',notes:[{}]}}};
const state={transport:{beat:4,playing:true},
 planning:{current:plan,upcoming:[{...plan,start:8,section:'descent'}]},
 voices:{a:{name:'<synth>'}}};
music.render(state,false);
assert.match(elements['music-plans'].text,/salita.*beat 4–8.*discesa.*beat 8–12/);
state.voices.a.weather={configured:true,enabled:true,status:'active',label:'in uso · velocity',parameters:['velocity'],blocked_parameters:[]};
music.render(state,false);
assert.match(elements['weather-summary'].text,/in uso su <synth>/);
state.voices.a.weather={configured:true,enabled:false,status:'disabled',label:'disattivato',parameters:[],blocked_parameters:[]};
music.render(state,false);
assert.match(elements['weather-summary'].text,/meteo: disattivato/);
state.voices.a.weather={configured:true,enabled:false,pending:true,status:'active',label:'in uso · velocity · disattivazione in coda',parameters:['velocity'],blocked_parameters:[]};
music.render(state,false);
assert.match(elements['weather-summary'].text,/disattivazione in coda.*in uso su <synth>/);
state.voices.a.weather={configured:true,enabled:true,pending:true,status:'disabled',label:'attivazione in coda',parameters:[],blocked_parameters:[]};
music.render(state,false);
assert.match(elements['weather-summary'].text,/attivazione in coda/);
state.planning={current:null,upcoming:[]};
music.render(state,true);
assert.match(elements['music-plans'].text,/Nessun piano in esecuzione/);
assert.match(elements['music-notice'].text,/non aggiornati/);
music.markStale();assert.match(elements['music-notice'].text,/Collegamento interrotto/);
assert.match(elements['weather-summary'].text,/ultimo stato/);
console.log('music_dashboard: presente/futuro, meteo e stato scaduto verificati');
