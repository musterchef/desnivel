// Interfaccia della voce. Le scelte compositive restano nel motore Python.
include('desnivel_recording.js');
inlets=1;outlets=4; // UDP, player, diagnostica, API del trasporto Live
var voiceId='', replyPort=9101, instance='', serial=0, acknowledged=-1;
var backendPort=9006, beat=0, playing=0, epoch=0, lastTick=-1;
var bpm=null;
var connected=false, lastReply=0, state=null, snapshot='', parameterNames=[], presetNames=[];
var selectedParameter=0, patch=this.patcher;
var lastTransportSerial=-1, backendSession='';
var lastRecordingSerial=-1;
var rewindPending=false;
var deviceAdapter=null;
var presetDraft='';
var wireParts={}, wireOrder=[];
var wireStream=Math.floor(Math.random()*0x7fffffff), wireSerial=0;
// I payload variabili restano byte numerici, senza simboli Max per ogni JSON.
function utf8bytes(text){var binary=unescape(encodeURIComponent(text)), out=[];for(var i=0;i<binary.length;i++)out.push(binary.charCodeAt(i));return out;}
function utf8text(bytes){var binary='';for(var i=0;i<bytes.length;i++){if(bytes[i]<0||bytes[i]>255||Math.floor(bytes[i])!==bytes[i])throw new Error('byte non valido');binary+=String.fromCharCode(bytes[i]);}return decodeURIComponent(escape(binary));}
function status(text){outlet(2,String(text));}
function ui(name){return patch.getnamed(name);}
function loadbang(){reflectPresence();reflectManual();}
function playerReset(){if(deviceAdapter)deviceAdapter.panic();outlet(1,'panic');}
function disconnect(){DesnivelRecording.disconnect();connected=false;state=null;snapshot='';wireParts={};wireOrder=[];playerReset();ui('role_display').message('set','Unassigned');ui('role_menu').message('clear');reflectPresence();reflectManual();reflectWeather();status('Disconnected');}
function voice(){var name=arrayfromargs(arguments).join(' ');if(name!==voiceId){disconnect();voiceId=name;}}
function receiveport(value){var n=Number(value);if(n!==replyPort){disconnect();replyPort=n;}}
function backendport(value){var n=Number(value);if(n!==backendPort){disconnect();backendPort=n;}}
function connect(){
    if(connected){request('hello',{});return;}
    disconnect();
    if(!/^[A-Za-z0-9_-]+$/.test(voiceId)){status('Enter a voice ID');return;}
    instance='device_'+new Date().getTime()+'_'+Math.floor(Math.random()*1000000000);
    serial=0;acknowledged=-1;lastTransportSerial=-1;lastRecordingSerial=-1;backendSession='';lastReply=new Date().getTime();connected=true;request('hello',{});
}
function request(action, extra){
    if(!connected)return;
    var m={version:1,voice:voiceId,instance:instance,reply_port:replyPort,serial:++serial,action:action,capabilities:['transport_control','recording_control'],transport:{beat:beat,playing:playing,epoch:epoch,bpm:bpm}};
    if(deviceAdapter){m.capabilities=deviceAdapter.capabilities;m.device_state=deviceAdapter.snapshot();}
    for(var key in extra)m[key]=extra[key];
    var bytes=utf8bytes(JSON.stringify(m));
    if(bytes.length>12000){status('messaggio di controllo oltre il limite JSON');return;}
    wireSerial=wireSerial%0x7fffffff+1;
    // udpsend usa per default 5096 byte: 900 interi OSC lasciano spazio all'intestazione.
    for(var offset=0;offset<bytes.length;offset+=900){
        var part=bytes.slice(offset,offset+900);
        if(bytes.length>900)part=[-2,wireStream,wireSerial,offset,bytes.length].concat(part);
        outlet(0,['/desnivel/v1/voice/control'].concat(part));
    }
}
function tempo(value){
    value=Number(value);
    if(isFinite(value) && value>0)bpm=value;
}
function clock(ticks,running){
    ticks=Number(ticks);running=Number(running);
    if(rewindPending && ticks===0 && running===0){epoch++;rewindPending=false;}
    else if(!rewindPending && (ticks<lastTick || running!==playing))epoch++;
    lastTick=ticks;beat=ticks/480;playing=running;
    if(connected)request('transport',{});
}
function heartbeat(){
    if(!connected)return;
    DesnivelRecording.heartbeat();
    expireWire();
    if(new Date().getTime()-lastReply>3000){DesnivelRecording.disconnect();playerReset();ui('weather_display').message('set','meteo: dati non aggiornati');status('Python not responding');}
    request('hello',{});
}
function expireWire(){
    var now=new Date().getTime(), keep=[];
    for(var i=0;i<wireOrder.length;i++){
        var key=wireOrder[i], part=wireParts[key];
        if(part && now-part.created<=1500)keep.push(key);
        else delete wireParts[key];
    }
    wireOrder=keep;
}
function wireBytes(data){
    if(data[0]!==-1)return data;
    expireWire();
    if(data.length<6)throw new Error('frammento OSC incompleto');
    var stream=data[1], serial=data[2], offset=data[3], total=data[4], size=data.length-5;
    for(var n=1;n<5;n++)if(!isFinite(data[n]) || Math.floor(data[n])!==data[n])throw new Error('intestazione OSC non valida');
    if(stream<0 || serial<0 || offset<0 || offset%1500!==0 || total<=1500 || total>12000 || size!==Math.min(1500,total-offset))throw new Error('limiti del frammento OSC non validi');
    for(var j=5;j<data.length;j++)if(data[j]<0 || data[j]>255 || Math.floor(data[j])!==data[j])throw new Error('byte del frammento non valido');
    var key=stream+':'+serial, part=wireParts[key];
    if(!part){
        if(wireOrder.length>=8)delete wireParts[wireOrder.shift()];
        part={created:new Date().getTime(),total:total,received:0,chunks:{}};
        wireParts[key]=part;wireOrder.push(key);
    }
    if(part.total!==total)throw new Error('lunghezza dei frammenti incoerente');
    if(part.chunks[offset]===undefined){part.chunks[offset]=data.slice(5);part.received+=size;}
    if(part.received!==total)return null;
    var result=[];
    for(var start=0;start<total;start+=1500){
        if(part.chunks[start]===undefined)return null;
        result=result.concat(part.chunks[start]);
    }
    delete wireParts[key];
    expireWire();
    return result;
}
function receive(){
    try{
        if(!connected)return;
        var bytes=wireBytes(arrayfromargs(arguments));
        if(bytes===null)return;
        var m=JSON.parse(utf8text(bytes));
        if(!connected || m.version!==1 || m.voice!==voiceId || m.instance!==instance)return;
        if(deviceAdapter && deviceAdapter.receive(m))return;
        if(m.kind==='recording'){
            if(!backendSession || m.session!==backendSession || typeof m.serial!=='number'
                || !isFinite(m.serial) || Math.floor(m.serial)!==m.serial || m.serial<=lastRecordingSerial)return;
            lastRecordingSerial=m.serial;
            DesnivelRecording.handle(m,function(report){request('recording_status',{report:report});});
            return;
        }
        if(m.kind==='transport'){
            if(!backendSession||m.session!==backendSession)return;
            if(typeof m.serial!=='number'||!isFinite(m.serial)||Math.floor(m.serial)!==m.serial||m.serial<0||m.serial<=lastTransportSerial)return;
            if(m.action==='pause'){playerReset();outlet(3,'call','stop_playing');}
            else if(m.action==='resume')outlet(3,'call','continue_playing');
            else if(m.action==='restart'){
                rewindPending=true;
                playerReset();outlet(3,'call','stop_playing');
                outlet(3,'set','start_time',0);
                outlet(3,'set','current_song_time',0);
            }else return;
            lastTransportSerial=m.serial;return;
        }
        if(m.kind==='error'){reflectRole();reflectPresence();reflectManual();parameter(selectedParameter);status(m.error);return;}
        if(m.kind==='plan'){if(new Date().getTime()-lastReply>3000)return;outlet(1,['planbytes'].concat(utf8bytes(JSON.stringify(m.plan))));return;}
        if(m.kind!=='state' || m.serial<acknowledged)return;
        if(typeof m.session==='string' && m.session!==backendSession){
            if(backendSession)DesnivelRecording.disconnect();
            backendSession=m.session;lastTransportSerial=-1;lastRecordingSerial=-1;
        }
        acknowledged=m.serial;lastReply=new Date().getTime();
        var signature=JSON.stringify([m.role,m.role_mode,m.supported_roles,m.active,m.next_entry_progress,m.section_role,m.preset,m.presets,m.controls,m.can_save_presets,m.editable_presets,m.presence,m.weather]);
        if(signature!==snapshot){
            state=m;snapshot=signature;
            reflectRole();
            reflectPresence();
            reflectManual();
            var previous=parameterNames[selectedParameter];
            presetNames=m.presets;parameterNames=[];
            ui('preset_menu').message('clear');
            for(var i=0;i<presetNames.length;i++)ui('preset_menu').message('append',presetNames[i]);
            if(m.preset!==null)ui('preset_menu').message('set',presetNames.indexOf(m.preset));
            else ui('preset_menu').message('set',-1);
            for(var key in m.controls)parameterNames.push(key);
            ui('parameter_menu').message('clear');
            for(var j=0;j<parameterNames.length;j++){
                var name=parameterNames[j], control=m.controls[name];
                ui('parameter_menu').message('append',(control.inactive_reason?'[inattivo] ':'')+String(control.label||name).toLowerCase());
            }
            selectedParameter=Math.max(0,parameterNames.indexOf(previous));
            ui('parameter_menu').message('set',selectedParameter);parameter(selectedParameter);
        }
        reflectWeather();status(m.notice||'Python connected');
    }catch(e){status('Invalid Python message: '+e);}
}
function reflectWeather(){
    var weather=state && state.weather;
    var text='meteo: '+(weather?weather.label:'stato non disponibile');
    ui('weather_display').message('set',text);
    ui('weather_display').message('annotation',text+(weather && weather.blocked_parameters.length
        ?' · manual: '+weather.blocked_parameters.join(', '):''));
}
function reflectManual(){
    var control=state && state.controls[parameterNames[selectedParameter]];
    var available=control && typeof control.manual==='boolean';
    ui('manual_toggle').message('set',available && control.manual?1:0);
    ui('manual_display').message('set',available?(control.manual?'manual':'auto'):'—');
}
function manual(value){
    var name=parameterNames[selectedParameter], control=state && state.controls[name];
    if(!control || typeof control.manual!=='boolean'){reflectManual();return;}
    value=Number(value);
    if(value!==0 && value!==1){reflectManual();return;}
    request('manual',{parameter:name,value:value===1});
}
function reflectPresence(){
    var p=state && state.presence;
    ui('presence_display').message('set',p?'Auto '+Math.round(p.automatic*100)+'%  |  Effettiva '+Math.round(p.effective*100)+'%':'Presenza: collega alla sessione');
    ui('presence_multiplier').message('set',p?p.multiplier:1);
    ui('presence_slider').message('set',p?Math.round(p.multiplier*100):100);
}
function presence(value){
    value=Number(value);
    if(!state || !state.presence || !isFinite(value) || value<0 || value>10){reflectPresence();return;}
    request('presence',{value:value});
}
function presence_slider(value){presence(Number(value)/100);}
function reflectRole(){
    if(!state)return;
    var roles=state.supported_roles||[], menu=ui('role_menu');
    menu.message('clear');menu.message('append',roles.length?(state.role_follow_label||'Follow section'):'No roles available');
    for(var i=0;i<roles.length;i++)menu.message('append',roles[i]);
    menu.message('set',state.role_mode==='manual'?roles.indexOf(state.role)+1:0);
    var activity='';
    if(state.active===false)activity=state.next_entry_progress!==null && state.next_entry_progress!==undefined
        ?' (enters at '+Math.round(state.next_entry_progress*100)+'%)':' (not in this section)';
    ui('role_display').message('set',(state.role||'Unassigned')+activity);
}
function choose_role(index){
    if(!state)return;
    var roles=state.supported_roles||[];
    if(!roles.length)return;
    if(index===0)request('role',{role:null});
    else if(roles[index-1]!==undefined)request('role',{role:roles[index-1]});
}
function preset(index){
    if(state && presetNames[index]!==undefined){
        presetDraft=presetNames[index];ui('preset_name').message('set',presetDraft);
        request('preset',{preset:presetDraft});
    }
}
function preset_name(){presetDraft=arrayfromargs(arguments).join(' ').replace(/^\s+|\s+$/g,'');}
function save_preset(overwrite){
    if(!state || !state.can_save_presets){status('Preset library unavailable');return;}
    if(!presetDraft){status('Enter a preset name');return;}
    request('save_preset',{preset:presetDraft,overwrite:!!overwrite});
}
function parameter(index){
    selectedParameter=Number(index);
    reflectManual();
    var name=parameterNames[selectedParameter];
    if(state && name!==undefined){
        var c=state.controls[name], choices=c.choices;
        var objective=c.automation && !c.manual?' → '+Math.round(c.automation.target*1000)/1000:'';
        ui('parameter_choice').hidden=!choices;
        ui('parameter_value').hidden=!!choices;
        ui('parameter_slider').hidden=!!choices||!!c.toggle;
        ui('parameter_toggle').hidden=!!choices||!c.toggle;
        if(choices){
            ui('parameter_choice').message('clear');
            var chosen=-1;
            for(var i=0;i<choices.length;i++){
                ui('parameter_choice').message('append',choices[i][1].toLowerCase());
                if(choices[i][0]===c.value)chosen=i;
            }
            ui('parameter_choice').message('set',chosen);
            ui('range_display').message('set',(chosen>=0?choices[chosen][1].toLowerCase():'scegli')+(c.inactive_reason?' · inattivo':''));
        }else{
            ui('parameter_value').message('set',c.value);
            ui('parameter_slider').message('set',c.maximum===c.minimum?0:Math.round((c.value-c.minimum)/(c.maximum-c.minimum)*1000));
            ui('parameter_toggle').message('set',c.value);
            ui('range_display').message('set',c.minimum+' .. '+c.maximum+objective+(c.integer?' (integer)':'')+(c.inactive_reason?' · inattivo':'')+(c.value_hint?'\n'+c.value_hint:''));
        }
        var help=name+(c.label?' — '+c.label.toLowerCase():'')+(c.inactive_reason?': '+c.inactive_reason:'');
        if(c.description)help+=' · '+c.description;
        if(c.automation)help+=' · base '+c.automation.base+', obiettivo '+c.automation.target+', effettivo '+c.automation.effective+' · '+c.automation.reason;
        ui('parameter_menu').setboxattr('annotation',help);
        ui('parameter_value').setboxattr('annotation',help);
        ui('parameter_slider').setboxattr('annotation',help);
        ui('parameter_toggle').setboxattr('annotation',help);
        ui('parameter_choice').setboxattr('annotation',help);
    }else ui('range_display').message('set','nessun parametro');
}
function slidervalue(v){
    var name=parameterNames[selectedParameter];
    if(!state || name===undefined)return;
    var c=state.controls[name], fraction=Math.max(0,Math.min(1000,Number(v)))/1000;
    if(c.choices)return;
    var n=c.minimum+fraction*(c.maximum-c.minimum);
    if(c.integer)n=Math.round(n);
    else n=Math.round(n*1000000)/1000000;
    ui('parameter_value').message('set',n);
    value(n);
}
function value(v){
    var name=parameterNames[selectedParameter];
    if(!state || name===undefined)return;
    var c=state.controls[name], n=Number(v);
    if(c.choices)return;
    if(!isFinite(n)||n<c.minimum||n>c.maximum||(c.integer&&Math.floor(n)!==n)){
        ui('parameter_value').message('set',c.value);status('Value outside allowed range');return;
    }
    request('parameter',{parameter:name,value:n});
}
function choice(index){
    var name=parameterNames[selectedParameter];
    if(!state || name===undefined)return;
    var choices=state.controls[name].choices;
    index=Number(index);
    if(!choices || !isFinite(index) || Math.floor(index)!==index || !choices[index])return;
    request('parameter',{parameter:name,value:choices[index][0]});
}
function panic(){playerReset();request('panic',{});}
function notifydeleted(){if(deviceAdapter && deviceAdapter.dispose)deviceAdapter.dispose();else playerReset();}
