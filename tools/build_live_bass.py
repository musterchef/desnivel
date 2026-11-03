"""Costruisce due device autonomi per Snake e basso, senza modificare gli originali."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct

from build_snake_length import (
    SUPPORTED_SOURCE_SHA256, add, boxes, build, connect, entries, parameter, read_device,
)

ROOT = Path(__file__).resolve().parents[1]


def freeze(template, document, filename, scripts, keep_resources=False):
    """Conserva gli asset originali e incorpora i JS nel container Max."""
    container = template[32:]
    resources = []
    for i, fields in enumerate(entries(container)):
        if i and (not keep_resources or fields['fnam'][1].rstrip(b'\0').decode() in scripts):
            continue
        metadata = {k:v[1] for k,v in fields.items()}
        start = int.from_bytes(metadata['of32'],'big')
        size = int.from_bytes(metadata['sz32'],'big')
        payload = container[start:start+size]
        if i == 0:
            metadata['fnam'] = filename.encode()+b'\0'
            payload = json.dumps(document,separators=(',',':')).encode()+b'\n\0'
        resources.append((metadata,payload))
    for name, payload in scripts.items():
        resources.append(({'type':b'TEXT','fnam':name.encode()+b'\0','vers':bytes(4),
                           'flag':bytes(4),'mdat':bytes(4)},payload))
    body = bytearray(container[:16])
    directory = bytearray()
    for metadata,payload in resources:
        metadata['of32'] = struct.pack('>I',len(body))
        metadata['sz32'] = struct.pack('>I',len(payload))
        body.extend(payload)
        fields = bytearray()
        for key,value in metadata.items():
            if key=='fnam' and len(value)%2:value+=b'\0'
            fields.extend(key.encode()+struct.pack('>I',len(value)+8)+value)
        directory.extend(b'dire'+struct.pack('>I',len(fields)+8)+fields)
    struct.pack_into('>I',body,12,len(body))
    body.extend(b'dlst'+struct.pack('>I',len(directory)+8)+directory)
    header=bytearray(template[:32]);struct.pack_into('<I',header,28,len(body))
    return bytes(header)+body


def clock_chain(p, destination, method, include_tempo=True):
    add(p,'clock-metro','qmetro 125',900,100)
    add(p,'clock-trigger','t b b',900,140)
    add(p,'clock-transport','transport',1100,180)
    add(p,'clock-time','f',900,220)
    add(p,'clock-pack','pack 0. 120. 0' if include_tempo else 'pack 0. 0',900,260)
    add(p,'clock-method','prepend '+method,900,300)
    connect(p,'clock-metro','clock-trigger')
    connect(p,'clock-trigger','clock-transport',outlet=1)
    connect(p,'clock-transport','clock-time',outlet=7,inlet=1)
    if include_tempo:connect(p,'clock-transport','clock-pack',outlet=4,inlet=1)
    connect(p,'clock-transport','clock-pack',outlet=6,inlet=2 if include_tempo else 1)
    connect(p,'clock-trigger','clock-time')
    connect(p,'clock-time','clock-pack')
    connect(p,'clock-pack','clock-method');connect(p,'clock-method',destination)


def mirror_message(p, message_id, name):
    """Legge i valori numerici inviati al display, senza interrogare message."""
    message=boxes(p)[message_id]
    if message.get('varname')==name:message.pop('varname')
    incoming=[deepcopy(x['patchline']) for x in p['lines']
              if x['patchline']['destination']==[message_id,1]]
    if not incoming:raise ValueError('Nessun aggiornamento numerico per '+message_id)
    add(p,name,None,5100,500,'number',varname=name,parameter_enable=0)
    add(p,name+'-init','loadmess '+message['text'],5100,460)
    connect(p,name+'-init',name)
    for wire in incoming:
        wire['destination']=[name,0]
        wire.pop('midpoints',None)
        # Mantiene l'ordine delle connessioni originali e aggiunge la lettura in coda.
        siblings=[x['patchline'] for x in p['lines'] if x['patchline']['source']==wire['source']]
        if len(siblings)>1 or any('order' in x for x in siblings):
            for i,x in enumerate(sorted(siblings,key=lambda x:x.get('order',0))):x['order']=i
            wire['order']=len(siblings)
        else:
            siblings[0]['order']=0;wire['order']=1
        p['lines'].append({'patchline':wire})


def snake_document(document, state_port):
    result=build(document);p=result['patcher'];root=boxes(p)
    root['obj-115']['varname']='desnivel_sequencer'
    seq=root['obj-115']['patcher']
    # Legge le altezze quantizzate effettive, senza assumere offset o scala.
    sb=boxes(seq)
    for lane, display in [('notes','obj-37'),('gates','obj-130'),('velocities','obj-133')]:
        mirror_message(seq,display,'desnivel_shift_'+lane)
    for i in range(16):
        target=next(x['patchline']['destination'][0] for x in seq['lines']
                    if x['patchline']['source']==[f'length-trigger-{i}',0])
        mirror_message(seq,target,f'desnivel_pitch_{i+1:02d}')
    add(seq,'state-out',None,4750,1200,'outlet',index=7)
    for name,source in [('notes','obj-123'),('gates','obj-183'),('velocities','obj-221')]:
        add(seq,name+'-phase-trigger','t i b',4800,100)
        add(seq,name+'-phase-clock','when',5000,100)
        add(seq,name+'-phase-pack','pack 0 0.',4800,140)
        add(seq,name+'-phase-prefix','prepend phase '+name,4800,180)
        connect(seq,source,name+'-phase-trigger')
        connect(seq,name+'-phase-trigger',name+'-phase-clock',outlet=1)
        connect(seq,name+'-phase-clock',name+'-phase-pack',outlet=1,inlet=1)
        connect(seq,name+'-phase-trigger',name+'-phase-pack')
        connect(seq,name+'-phase-pack',name+'-phase-prefix')
        connect(seq,name+'-phase-prefix','state-out')
    root['obj-115']['numoutlets']=7;root['obj-115']['outlettype'].append('list')
    add(p,'state-js','js desnivel_snake_state.js',900,500)
    add(p,'state-defer','deferlow',900,450)
    add(p,'state-send',f'udpsend 127.0.0.1 {state_port}',900,550)
    connect(p,'obj-115','state-defer',outlet=6);connect(p,'state-defer','state-js')
    connect(p,'state-js','state-send')
    clock_chain(p,'state-js','snapshot')
    bank=root['length-bank']['patcher']
    toggle=add(bank,'export',None,0,500,'live.toggle',presentation=1,
               presentation_rect=[0,142,18,18])
    parameter(toggle,'Export_State',0,1,0)
    add(bank,'export-label','Export',25,500,'comment',presentation=1,presentation_rect=[22,142,80,20])
    add(bank,'export-out',None,600,885,'outlet',index=2)
    connect(bank,'export','export-out')
    root['length-bank']['numoutlets']=2;root['length-bank']['outlettype'].append('int')
    connect(p,'length-bank','clock-metro',outlet=1)
    p['parameters']['length-bank::export']=['Export_State','Export_State',0]
    p.setdefault('dependency_cache',[]).append({'name':'desnivel_snake_state.js','type':'TEXT','implicit':1})
    return result


def player_document(port):
    p={'fileversion':1,'classnamespace':'box','rect':[0,0,1150,800],
       'openinpresentation':1,'devicewidth':350,'boxes':[],'lines':[],
       'dependency_cache':[{'name':'desnivel_transport_player.js','type':'TEXT','implicit':1}]}
    add(p,'receive',f'udpreceive {port} @defer 1',20,20)
    add(p,'route','route /desnivel/v1/player/bass/plan',20,60)
    add(p,'incoming','t l b',20,100)
    add(p,'when','when',220,140)
    add(p,'now','prepend now',220,180)
    add(p,'plan','prepend plan',20,180)
    add(p,'player','js desnivel_transport_player.js',20,230)
    add(p,'print','print bass_player',20,280)
    add(p,'unpack','unpack 0 0',400,400,varname='notes_unpack')
    add(p,'flush','flush',400,450,varname='notes_flush')
    add(p,'midi','noteout',400,500)
    for a,b in [('receive','route'),('route','incoming'),('incoming','plan'),('plan','player'),('now','player'),('player','print')]:connect(p,a,b)
    connect(p,'incoming','when',outlet=1)
    connect(p,'when','now',outlet=1)
    connect(p,'unpack','flush');connect(p,'unpack','flush',outlet=1,inlet=1)
    connect(p,'flush','midi');connect(p,'flush','midi',outlet=1,inlet=1)
    clock_chain(p,'player','clock',False)
    add(p,'load','loadmess 1',900,60);connect(p,'load','clock-metro')
    # Stop immediato tramite Live API; il clock periodico rileva anche i seek.
    for id,text,x,y,cls in [('ready','live.thisdevice',20,350,'newobj'),
                         ('path','path live_set',20,390,'message'),
                         ('resolve','live.path',20,430,'newobj'),
                         ('observe','live.observer is_playing',20,470,'newobj'),
                         ('running','prepend running',20,510,'newobj')]:add(p,id,text,x,y,cls)
    connect(p,'ready','path');connect(p,'path','resolve');connect(p,'resolve','observe',inlet=1)
    connect(p,'observe','running');connect(p,'running','player')
    add(p,'title','DESNIVEL — Basso',10,10,'comment',presentation=1,presentation_rect=[10,10,320,25])
    add(p,'info',f'Python → porta {port} → trasporto Live',10,45,'comment',presentation=1,presentation_rect=[10,45,325,20])
    add(p,'status','In attesa del piano Python',10,80,'message',presentation=1,presentation_rect=[10,80,325,25])
    add(p,'status-set','prepend set',220,280);connect(p,'player','status-set');connect(p,'status-set','status')
    add(p,'panic','panic',10,120,'message',presentation=1,presentation_rect=[10,120,60,22]);connect(p,'panic','player')
    return {'patcher':p}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--state-port',type=int,default=9003)
    parser.add_argument('--player-port',type=int,default=9004)
    args=parser.parse_args()
    if args.output.exists():parser.error('La cartella output deve essere nuova')
    if any(not 1<=p<=65535 for p in (args.state_port,args.player_port)):parser.error('Porta non valida')
    raw,doc,_,_=read_device(args.source)
    if hashlib.sha256(raw).hexdigest()!=SUPPORTED_SOURCE_SHA256:parser.error('Vanilla diverso dalla versione ispezionata')
    results={
        'MDD_SNAKE_LengthBank.amxd':freeze(raw,snake_document(doc,args.state_port),'MDD_SNAKE_LengthBank.amxd',
            {'desnivel_snake_state.js':(ROOT/'m4l/desnivel_snake_state.js').read_bytes()},True),
        'Desnivel_Bass.amxd':freeze(raw,player_document(args.player_port),'Desnivel_Bass.amxd',
            {'desnivel_transport_player.js':(ROOT/'m4l/desnivel_transport_player.js').read_bytes()}),
    }
    args.output.mkdir(parents=True)
    for name,content in results.items():
        path=args.output/name;path.write_bytes(content)
        read_device(path)
        print(path)


if __name__=='__main__':main()
