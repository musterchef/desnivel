// Adattatore locale: il componente segue immediatamente la propria istanza Snake.
var DesnivelSnakeControl = (function () {
    var parameters={}, target=0, applied=-1, error='', ready=false, hasInstrument=false;
    var selfApi=null, parentApi=null, deviceApi=null, instrumentApi=null, parameterApi=null;
    var nextCheck=0;
    function point(api, id){if(Number(api.id)!==id)api.id=id;return api;}
    function scalar(api, key){var a=api.get(key);return Array.isArray(a)?a[0]:a;}
    function ids(api, key){var a=api.get(key), r=[];for(var i=0;i<a.length;i++)if(/^[1-9][0-9]*$/.test(String(a[i])))r.push(Number(a[i]));return r;}
    function resolve(){
        // I messaggi di trasporto interrogano spesso lo stato: riusare i riferimenti nativi.
        if(!selfApi){
            selfApi=new LiveAPI(null,'this_device');
            parentApi=new LiveAPI(null,'id 0');
            deviceApi=new LiveAPI(null,'id 0');
            instrumentApi=new LiveAPI(null,'id 0');
            parameterApi=new LiveAPI(null,'id 0');
        }
        // Durante il caricamento this_device può essere ancora id 0: risolverlo di nuovo,
        // senza conservare per tutta la sessione il riferimento iniziale non valido.
        if(!(Number(selfApi.id)>0))selfApi.goto('this_device');
        if(!(Number(selfApi.id)>0))throw new Error('Live API in attesa del caricamento del controllo');
        var self=selfApi, parents=ids(self,'canonical_parent');
        if(parents.length!==1)throw new Error('contenitore del controllo non disponibile nella Live API');
        var parent=point(parentApi,parents[0]);
        var devices=ids(parent,'devices'), index=devices.indexOf(Number(self.id));
        if(index<0)throw new Error('controllo non trovato nel contenitore Live (id '+self.id+', devices '+devices.join(', ')+')');
        if(index===0)throw new Error('nessun device precedente: colloca il controllo immediatamente dopo Snake con Length');
        var id=devices[index-1];
        if(id!==target || !ready){
            var device=point(deviceApi,id), p=ids(device,'parameters'), map={}, duplicate={};
            for(var i=0;i<p.length;i++){
                var item=point(parameterApi,p[i]), name=String(scalar(item,'name'));
                if(map[name] || duplicate[name]){delete map[name];duplicate[name]=true;}else map[name]=p[i];
            }
            for(var cell=1;cell<=16;cell++){
                var suffix=(cell<10?'0':'')+cell;
                for(var j=0;j<4;j++)if(!map[['Note_','Gate_','Velocity_','Length_'][j]+suffix])
                    throw new Error('Snake precedente senza banchi compatibili, compreso Length');
            }
            if(!map.Scales || !map.Length_Min_ms || !map.Length_Max_ms)throw new Error('mod Snake con Length richiesta');
            for(var lane=0;lane<3;lane++)for(var control=0;control<5;control++){
                var required=['Notes','Gates','Velocities'][lane]+'_Sequencer_'+['Snake_Shape','Speed','Length','Direction','Steps_Shift'][control];
                if(!map[required])throw new Error('controllo dei percorsi Snake assente: '+required);
            }
            for(var name in map)map[name]=new LiveAPI(null,'id '+map[name]);
            parameters=map;target=id;applied=-1;error='';
        }
        hasInstrument=false;
        for(var d=index+1;d<devices.length;d++)if(Number(scalar(point(instrumentApi,devices[d]),'type'))===1){hasInstrument=true;break;}
        ready=true;
    }
    function mute(){
        try{
            resolve();
            for(var i=1;i<=16;i++)parameters['Gate_'+(i<10?'0':'')+i].set('value',0);
            outlet(1,'panic');
        }catch(e){error=String(e);ready=false;}
        applied=-1;
    }
    function snapshot(){
        var now=Date.now();
        if(now>=nextCheck){
            nextCheck=now+1000;
            try{resolve();}catch(e){error=String(e);ready=false;}
        }
        return {ready:ready,has_instrument:hasInstrument,error:error || null,applied:applied};
    }
    function receive(message){
        if(message.kind==='plan' && message.plan && message.plan.reset && message.plan.session===backendSession){mute();return true;}
        if(message.kind!=='parameters')return false;
        if(!backendSession || message.session!==backendSession || typeof message.serial!=='number'
            || !isFinite(message.serial) || Math.floor(message.serial)!==message.serial || message.serial<=applied)return true;
        try{
            resolve();
            var values=message.parameters, updates=[];
            if(!values || typeof values!=='object' || Array.isArray(values))throw new Error('banchi non validi');
            for(var name in values){
                if(!/^(Scales|Length_(Min|Max)_ms|(Note|Gate|Velocity|Length)_\d\d|(Notes|Gates|Velocities)_Sequencer_(Snake_Shape|Speed|Length|Direction|Steps_Shift))$/.test(name) || !parameters[name])
                    throw new Error('parametro Snake non supportato: '+name);
                var api=parameters[name], value=values[name];
                if(typeof value!=='number' || !isFinite(value) || value<Number(scalar(api,'min')) || value>Number(scalar(api,'max'))
                    || Number(scalar(api,'is_quantized')) && Math.floor(value)!==value)
                    throw new Error('valore Snake fuori intervallo: '+name);
                if(Number(scalar(api,'value'))!==value)updates.push({api:api,value:value});
            }
            for(var i=0;i<updates.length;i++)updates[i].api.set('value',updates[i].value);
            applied=message.serial;error='';
        }catch(e){error=String(e);mute();status('Snake: '+error);}
        return true;
    }
    return {snapshot:snapshot,receive:receive,panic:mute,capabilities:['transport_control','bank_control']};
})();
