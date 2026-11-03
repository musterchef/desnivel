// Operazioni Live: nessuna logica compositiva o modifica delle tracce sorgenti.
var DesnivelRecording = (function () {
    var prepared=[], job=null, recording=null, notify=null;
    function api(id){return new LiveAPI(null, typeof id==='number' ? 'id '+id : id);}
    function value(object, property){var data=object.get(property);return Array.isArray(data) ? data[0] : data;}
    function ids(object, property){
        var data=object.get(property), result=[];
        for(var i=0;i<data.length;i++)if(typeof data[i]==='number' && data[i]>0)result.push(data[i]);
        return result;
    }
    function tracks(){return ids(api('live_set'),'tracks');}
    function dictionary(object, property){
        var data=object.get(property);
        if(Array.isArray(data) && data[0]==='dictionary')return JSON.parse(new Dict(data[1]).stringify());
        if(Array.isArray(data) && data.length===1)data=data[0];
        if(typeof data==='string')return JSON.parse(data);
        if(data && typeof data==='object' && !Array.isArray(data))return data;
        throw new Error('risposta Live non valida: '+property);
    }
    function route(object, property, name){
        var choices=dictionary(object,'available_'+property+'s')['available_'+property+'s'], found=[];
        for(var i=0;i<choices.length;i++)if(choices[i].display_name===name)found.push(choices[i]);
        if(found.length!==1)throw new Error('routing non univoco: '+name);
        object.set(property,JSON.stringify(found[0]));
        return {property:property,name:name,identifier:found[0].identifier,deadline:new Date().getTime()+1500};
    }
    function currentRoute(object, property){
        var data=dictionary(object,property);
        var selected=data[property] || data;
        if(selected.identifier===undefined || typeof selected.display_name!=='string')
            throw new Error('risposta routing non valida per '+property+': '+JSON.stringify(data));
        return selected;
    }
    function confirmRoute(object, expected){
        var selected=currentRoute(object,expected.property);
        if(String(selected.identifier)===String(expected.identifier))return true;
        if(new Date().getTime()<expected.deadline)return false;
        throw new Error('routing non applicato: '+expected.name+' ('+expected.property+
            ', atteso '+expected.identifier+', ricevuto '+JSON.stringify(selected)+')');
    }
    function voiceDevices(track){
        var devices=ids(track,'devices'), result=[];
        for(var i=0;i<devices.length;i++){
            var name=String(value(api(devices[i]),'name')).toLowerCase().replace(/[ _-]/g,'');
            if(name==='desnivelvoice')result.push(i);
        }
        return result;
    }
    function names(){
        var all=tracks(), result={};
        for(var i=0;i<all.length;i++){
            var name=String(value(api(all[i]),'name'));
            if(!result[name])result[name]=[];
            result[name].push(all[i]);
        }
        return result;
    }
    function report(request,status,error){
        if(notify)notify({request:request,status:status,error:error || null,tracks:prepared.map(function(item){
            return {name:item.name,source:item.sourceName,type:item.type};
        })});
    }
    function removeCreated(created){
        for(var i=created.length-1;i>=0;i--){
            var all=tracks(), index=all.indexOf(created[i]);
            if(index>=0)api('live_set').call('delete_track',index);
        }
    }
    function fail(error){
        var old=job;job=null;prepared=[];
        if(old.task)old.task.cancel();
        var reason=String(error);
        try{removeCreated(old.created);}catch(cleanup){reason+='; pulizia incompleta: '+cleanup;}
        report(old.request,'error',reason);
    }
    function next(){
        if(!job)return;
        try{
            if(job.index===job.steps.length){
                var request=job.request;prepared=job.results;job=null;
                report(request,'ready');return;
            }
            if(job.steps[job.index++]()===false)job.index--;
            job.task.schedule(75);
        }catch(error){fail(error);}
    }
    function clearCopy(track){
        var devices=voiceDevices(track);
        for(var i=devices.length-1;i>=0;i--)track.call('delete_device',devices[i]);
        if(voiceDevices(track).length)throw new Error('Desnivel_Voice ancora presente nella copia');
        var clips=ids(track,'arrangement_clips'), slots=ids(track,'clip_slots');
        for(i=0;i<slots.length;i++)if(value(api(slots[i]),'has_clip')){
            var clip=ids(api(slots[i]),'clip');if(clip.length)clips.push(clip[0]);
        }
        for(i=0;i<clips.length;i++)track.call('delete_clip','id',clips[i]);
    }
    function prepare(message){
        if(job || recording)throw new Error('registrazione o preparazione già in corso');
        if(['audio','midi','both'].indexOf(message.mode)<0)throw new Error('modalità di registrazione non valida');
        var song=api('live_set');
        if(value(song,'record_mode'))throw new Error('fermare prima la registrazione di Live');
        song.call('stop_playing');song.set('current_song_time',0);
        var all=tracks(), byName=names(), sources=[];
        for(var i=0;i<all.length;i++){
            var track=api(all[i]), devices=voiceDevices(track);
            if(!devices.length)continue;
            var name=String(value(track,'name'));
            if(devices.length!==1 || byName[name].length!==1)throw new Error('sorgente non univoca: '+name);
            if(value(track,'is_frozen'))throw new Error('scongelare prima la traccia '+name);
            if(!value(track,'has_midi_input'))throw new Error('sorgente MIDI richiesta: '+name);
            sources.push({id:all[i],name:name});
        }
        if(!sources.length)throw new Error('nessuna traccia con Desnivel_Voice trovata');
        var operations=[];
        for(i=0;i<sources.length;i++)for(var t=0;t<2;t++){
            var type=t===0?'audio':'midi';
            if(message.mode!=='both' && message.mode!==type)continue;
            var targetName=sources[i].name+'_'+type.toUpperCase()+'_REC';
            if(byName[targetName] && byName[targetName].length!==1)throw new Error('nome REC non univoco: '+targetName);
            var existing=byName[targetName] ? byName[targetName][0] : null;
            if(existing){
                var existingTrack=api(existing);
                if(Boolean(value(existingTrack,'has_midi_input'))!==(type==='midi') || voiceDevices(existingTrack).length
                    || currentRoute(existingTrack,'input_routing_type').display_name!==sources[i].name)
                    throw new Error('traccia esistente incompatibile: '+targetName);
            }
            operations.push({source:sources[i].id,sourceName:sources[i].name,type:type,name:targetName,id:existing});
        }
        prepared=[];
        job={request:message.request,created:[],results:[],steps:[],index:0,task:null};
        for(i=0;i<operations.length;i++)(function(item){
            var before=[], inputType=null, inputChannel=null;
            job.steps.push(function(){
                if(item.id)return;
                before=tracks();
                if(item.type==='midi')api('live_set').call('duplicate_track',before.indexOf(item.source));
                else api('live_set').call('create_audio_track',-1);
            });
            job.steps.push(function(){
                var fresh=!item.id;
                if(fresh){
                    var after=tracks(), added=after.filter(function(id){return before.indexOf(id)<0;});
                    if(added.length!==1)throw new Error('creazione traccia non confermata da Live');
                    item.id=added[0];job.created.push(item.id);
                }
                var track=api(item.id);
                track.set('arm',0);
                if(fresh){
                    if(item.type==='midi')clearCopy(track);
                    else for(var d=ids(track,'devices').length-1;d>=0;d--)track.call('delete_device',d);
                    track.set('name',item.name);track.set('color',value(api(item.source),'color'));
                    track.set('solo',0);
                }
                track.set('current_monitoring_state',2);
                inputType=route(track,'input_routing_type',item.sourceName);
            });
            job.steps.push(function(){
                var track=api(item.id);
                if(!confirmRoute(track,inputType))return false;
                inputChannel=route(track,'input_routing_channel',item.type==='audio'?'Post Mixer':'Post FX');
            });
            job.steps.push(function(){
                if(!confirmRoute(api(item.id),inputChannel))return false;
                job.results.push(item);
            });
        })(operations[i]);
        job.task=new Task(next);
        job.task.schedule(0);
    }
    function restore(){
        var saved=recording;recording=null;
        if(!saved)return;
        if(saved.task)saved.task.cancel();
        var all=tracks(), song=api('live_set');
        for(var i=0;i<saved.arms.length;i++)if(all.indexOf(saved.arms[i].id)>=0)
            api(saved.arms[i].id).set('arm',saved.arms[i].value);
        for(var property in saved.settings)song.set(property,saved.settings[property]);
    }
    function stop(request){
        if(job){job.task.cancel();var created=job.created;job=null;removeCreated(created);prepared=[];}
        var song=api('live_set');
        if(recording){song.set('record_mode',0);song.call('stop_playing');restore();}
        report(request,'ready');
    }
    function start(message){
        if(job || recording || !prepared.length)throw new Error('preparare prima le tracce REC');
        var song=api('live_set');
        if(value(song,'is_playing') || Math.abs(value(song,'current_song_time'))>.0001 || value(song,'record_mode'))
            throw new Error('Live deve essere fermo a zero prima della registrazione');
        if(value(song,'count_in_duration'))throw new Error('disattivare il count-in di Live prima di registrare da zero');
        var all=tracks(), arms=[], settings={};
        for(var p=0;p<prepared.length;p++)if(all.indexOf(prepared[p].id)<0)throw new Error('traccia REC rimossa: '+prepared[p].name);
        var properties=['loop','punch_in','punch_out','midi_recording_quantization','arrangement_overdub'];
        for(var k=0;k<properties.length;k++)settings[properties[k]]=value(song,properties[k]);
        for(var i=0;i<all.length;i++)if(value(api(all[i]),'can_be_armed'))arms.push({id:all[i],value:value(api(all[i]),'arm')});
        recording={arms:arms,settings:settings,request:message.request,phase:'arming',
                   deadline:new Date().getTime()+1500,task:null};
        try{
            for(i=0;i<arms.length;i++)api(arms[i].id).set('arm',0);
            for(i=0;i<prepared.length;i++){
                var target=api(prepared[i].id);
                if(voiceDevices(target).length)throw new Error('Desnivel_Voice presente in una traccia REC');
                target.set('current_monitoring_state',2);target.set('arm',1);
            }
            recording.task=new Task(advanceStart);
            recording.task.schedule(75);
        }catch(error){song.set('record_mode',0);song.call('stop_playing');restore();throw error;}
    }
    function advanceStart(){
        if(!recording || recording.phase==='active')return;
        var song=api('live_set'), request=recording.request;
        try{
            if(recording.phase==='arming'){
                var armed=true;
                for(var i=0;i<prepared.length;i++)if(!value(api(prepared[i].id),'arm'))armed=false;
                if(armed){
                    for(var property in recording.settings)song.set(property,0);
                    song.set('record_mode',1);
                    recording.phase='enabling';recording.deadline=new Date().getTime()+1500;
                }
            }else if(recording.phase==='enabling' && value(song,'record_mode')){
                if(!value(song,'is_playing'))song.call('continue_playing');
                recording.phase='playing';recording.deadline=new Date().getTime()+1500;
            }else if(recording.phase==='playing' && value(song,'record_mode') && value(song,'is_playing')){
                recording.phase='active';report(request,'recording');return;
            }
            if(new Date().getTime()>=recording.deadline)
                throw new Error('Live non conferma la fase REC: '+recording.phase+
                    ' (record_mode='+value(song,'record_mode')+', is_playing='+value(song,'is_playing')+')');
            recording.task.schedule(75);
        }catch(error){
            song.set('record_mode',0);song.call('stop_playing');restore();
            report(request,'error',String(error));
        }
    }
    function handle(message, callback){
        notify=callback;
        try{
            if(message.action==='prepare')prepare(message);
            else if(message.action==='start')start(message);
            else if(message.action==='stop')stop(message.request);
            else throw new Error('comando REC sconosciuto');
        }catch(error){report(message.request,'error',String(error));}
    }
    function heartbeat(){
        if(recording && recording.phase==='active'){
            var song=api('live_set');
            if(!value(song,'is_playing') || !value(song,'record_mode'))stop(recording.request);
        }
    }
    function disconnect(){if(job || recording)stop(recording ? recording.request : job.request);}
    return {handle:handle,heartbeat:heartbeat,disconnect:disconnect};
})();
