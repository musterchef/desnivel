"""Build a separate Length bank into the supported frozen MDD Snake 3.2.3.

The original device and its embedded resources are never overwritten.
Generated devices belong outside the repository.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct


SUPPORTED_SOURCE_SHA256 = '715c6287aaa484a260bb5d2499b48cd0886963bace20cd638be1b8d21619c7da'


def u32(data, offset):
    return struct.unpack_from('>I', data, offset)[0]


def entries(container):
    directory = u32(container, 12)
    if container[directory:directory+4] != b'dlst':
        raise ValueError('Unsupported frozen device directory')
    pos = directory + 8
    while pos < len(container):
        if container[pos:pos+4] != b'dire':
            raise ValueError('Invalid frozen device entry')
        end = pos + u32(container, pos+4)
        fields = {}
        field = pos+8
        while field < end:
            size = u32(container, field+4)
            if size < 8 or field+size > end:
                raise ValueError('Invalid resource field')
            fields[container[field:field+4].decode()] = (field+8, container[field+8:field+size])
            field += size
        yield fields
        pos = end


def read_device(path):
    raw = Path(path).read_bytes()
    if raw[:4] != b'ampf' or raw[24:28] != b'ptch' or raw[32:36] != b'mx@c':
        raise ValueError('Expected the original frozen MDD Snake 3.2.3')
    container = raw[32:]
    main = next(entries(container))
    offset = int.from_bytes(main['of32'][1], 'big')
    size = int.from_bytes(main['sz32'][1], 'big')
    document = json.loads(container[offset:offset+size].rstrip(b'\x00\n\r '))
    return raw, document, offset, size


def replace_document(raw, document, offset, size):
    old = raw[32:]
    payload = json.dumps(document, ensure_ascii=True, separators=(',', ':')).encode()+b'\n\0'
    delta = len(payload)-size
    directory = u32(old, 12)
    result = bytearray(old[:offset]+payload+old[offset+size:])
    struct.pack_into('>I', result, 12, directory+delta)
    for i, fields in enumerate(entries(old)):
        op, ov = fields['of32']; sp, sv = fields['sz32']
        previous_offset = int.from_bytes(ov, 'big')
        struct.pack_into('>I', result, op+delta, previous_offset+(delta if previous_offset >= offset+size else 0))
        if i == 0:
            struct.pack_into('>I', result, sp+delta, len(payload))
    header = bytearray(raw[:32])
    struct.pack_into('<I', header, 28, len(result))
    return bytes(header)+bytes(result)


def boxes(patcher):
    return {x['box']['id']: x['box'] for x in patcher['boxes']}


def connect(p, source, destination, outlet=0, inlet=0):
    p['lines'].append({'patchline': {'source':[source,outlet], 'destination':[destination,inlet]}})


def add(p, id, text, x, y, cls='newobj', **attrs):
    box = dict(id=id, maxclass=cls, patching_rect=[x,y,180,22], **attrs)
    if text is not None:
        box['text'] = text
    p['boxes'].append({'box':box})
    return box


def parameter(box, name, minimum=None, maximum=None, initial=None):
    box['varname'] = name
    box['parameter_enable'] = 1
    values = box.setdefault('saved_attribute_attributes', {}).setdefault('valueof', {})
    values.update(parameter_longname=name, parameter_shortname=name, parameter_linknames=1)
    if minimum is not None: values['parameter_mmin'] = minimum
    if maximum is not None: values['parameter_mmax'] = maximum
    if initial is not None: values.update(parameter_initial=[initial], parameter_initial_enable=1)


def expose_lane_parameters(patcher):
    """La Live API legge i nomi brevi: distinguere esplicitamente le tre lane."""
    sequencer = boxes(patcher)['obj-115']['patcher']
    required = {f'{lane}_Sequencer_{control}'
                for lane in ('Notes', 'Gates', 'Velocities')
                for control in ('Snake_Shape', 'Speed', 'Length', 'Direction', 'Steps_Shift')}
    found = set()
    for item in sequencer['boxes']:
        box = item['box']
        name = box.get('varname')
        if name in required:
            parameter(box, name)
            patcher['parameters']['obj-115::'+box['id']][:2] = [name, name]
            found.add(name)
    if found != required:
        raise ValueError('parametri delle lane Snake mancanti: '+', '.join(sorted(required-found)))


def length_bank(source):
    """Store durations only; Notes supplies the actual selected cell."""
    bank = {'fileversion': 1, 'rect': [0, 0, 750, 900],
            'openinpresentation': 1, 'boxes': [], 'lines': []}
    add(bank, 'cell', None, 0, 0, 'inlet', index=1)
    add(bank, 'select', 'sel ' + ' '.join(str(i) for i in range(1, 17)), 0, 50)
    connect(bank, 'cell', 'select')
    source_boxes = boxes(source)
    for i in range(1, 17):
        template = next(b for b in source_boxes.values()
                        if b.get('varname') == f'Custom_{i:02d}[2]')
        dial = deepcopy(template)
        dial['id'] = f'dial-{i}'
        dial['patching_rect'] = [i * 35, 150, 27, 37]
        dial['presentation_rect'] = [120 + ((i-1) % 4)*40, 10 + ((i-1)//4)*39, 27, 37]
        parameter(dial, f'Length_{i:02d}', 0, 127, 64)
        dial['annotation'] = f'Durata della cella Notes {i}'
        bank['boxes'].append({'box': dial})
        add(bank, f'value-{i}', 'f 64.', i*35, 210)
        connect(bank, dial['id'], f'value-{i}', inlet=1)
        connect(bank, 'select', f'value-{i}', outlet=i-1)
        connect(bank, f'value-{i}', 'range')
    add(bank, 'title', 'Length', 0, 0, 'comment',
        presentation=1, presentation_rect=[0, 0, 110, 20])
    for key, initial, y in [('Min', 50, 32), ('Max', 500, 83)]:
        box = deepcopy(source_boxes['obj-506'])
        box.update(id='range-'+key, patching_rect=[440, y+400, 100, 22],
                   presentation_rect=[0, y+18, 94, 18], appearance=0)
        parameter(box, 'Length_'+key+'_ms', 10, 10000, initial)
        # INT ha soltanto 256 valori in Live: per 10–10000 ms occorre FLOAT.
        box['saved_attribute_attributes']['valueof'].update(parameter_type=0, parameter_unitstyle=0)
        box['annotation'] = 'Durata '+('minima' if key == 'Min' else 'massima')+' delle celle, in millisecondi'
        bank['boxes'].append({'box': box})
        add(bank, 'label-'+key, key+' ms', 440, y+370, 'comment',
            presentation=1, presentation_rect=[0, y, 94, 18])
    add(bank, 'range', 'pak 64. 50. 500.', 300, 820)
    add(bank, 'convert', r'expr min($f2\, $f3) + ($f1 / 127.) * abs($f3 - $f2)', 300, 850)
    add(bank, 'out', None, 300, 885, 'outlet', index=1)
    connect(bank, 'range-Min', 'range', inlet=1)
    connect(bank, 'range-Max', 'range', inlet=2)
    connect(bank, 'range', 'convert')
    connect(bank, 'convert', 'out')
    return bank


def connect_note_cells(patcher):
    """Publish the cell before its pitch, using the real Notes core events."""
    add(patcher, 'length-cell-out', None, 4500, 1200, 'outlet', index=6)
    for line in list(patcher['lines']):
        wire = line['patchline']
        source, outlet = wire['source']
        if source != 'obj-39' or outlet >= 16:
            continue
        target = wire['destination']
        trigger = f'length-trigger-{outlet}'
        add(patcher, trigger, 't b b', 4500, 30+outlet*55)
        add(patcher, f'length-cell-{outlet}', str(outlet+1), 4700, 30+outlet*55, 'message')
        wire['destination'] = [trigger, 0]
        wire.pop('midpoints', None)
        connect(patcher, trigger, target[0], inlet=target[1])
        connect(patcher, trigger, f'length-cell-{outlet}', outlet=1)
        connect(patcher, f'length-cell-{outlet}', 'length-cell-out')


def build(document):
    result=deepcopy(document);p=result['patcher'];b=boxes(p)
    if b['obj-67'].get('text')!='Custom' or b['obj-66'].get('text')!='del 64n':
        raise ValueError('Unsupported source: expected unmodified vanilla layout')
    original=b['obj-115']['patcher']
    expose_lane_parameters(p)
    bank=length_bank(original)
    add(p,'length-bank',None,1000,500,'bpatcher',patcher=bank,
        numinlets=1,numoutlets=1,outlettype=['float'],varname='Length_Bank',
        presentation=1,presentation_rect=[390,0,285,169],offset=[0,0],border=0)
    connect_note_cells(original)
    b['obj-115']['numoutlets'] = 6
    b['obj-115']['outlettype'].append('int')
    connect(p, 'obj-115', 'length-bank', outlet=5)
    # Separate note lifecycle from the vanilla swing retrigger window.
    # Only the old global note-off wire is removed; timing/swing logic is retained.
    replacements={('obj-10',0,'obj-5',0):('obj-10',0,'length-notes',0),
                  ('obj-75',0,'obj-5',1):('obj-75',0,'length-notes',1)}
    lines=[]
    for line in p['lines']:
        q=line['patchline'];key=(*q['source'],*q['destination'])
        if key==('obj-66',0,'obj-5',0):continue
        if key in replacements:
            a,ao,d,di=replacements[key];q['source']=[a,ao];q['destination']=[d,di];q.pop('midpoints',None)
        lines.append(line)
    p['lines']=lines
    lifecycle={'fileversion':1,'rect':[0,0,600,400],'boxes':[],'lines':[]}
    for i,name in enumerate(['pitch','velocity','duration']):
        add(lifecycle,name,None,20+i*180,20,'inlet',index=i+1)
    add(lifecycle,'notes','makenote 64 275 @repeatmode 1',20,140)
    for i,name in enumerate(['pitch','velocity','duration']):connect(lifecycle,name,'notes',inlet=i)
    for i,name in enumerate(['pitch-out','velocity-out']):
        add(lifecycle,name,None,20+i*180,250,'outlet',index=i+1);connect(lifecycle,'notes',name,outlet=i)
    add(lifecycle,'ready','live.thisdevice',20,290)
    add(lifecycle,'path','path live_set',200,290,'message')
    add(lifecycle,'resolve','live.path',380,290)
    add(lifecycle,'observe','live.observer is_playing',380,330)
    add(lifecycle,'off','sel 0',200,330)
    add(lifecycle,'stop','stop',20,330,'message')
    add(lifecycle,'close','closebang',20,370)
    for a,d,di in [('ready','path',0),('path','resolve',0),('resolve','observe',1),('observe','off',0),('off','stop',0),('close','stop',0),('stop','notes',0)]:connect(lifecycle,a,d,inlet=di)
    add(p,'length-notes','p note_length',1000,750,patcher=lifecycle,numinlets=3,numoutlets=2,outlettype=['int','int'])
    connect(p,'length-bank','length-notes',inlet=2)
    connect(p,'length-notes','obj-5');connect(p,'length-notes','obj-5',outlet=1,inlet=1)
    # Expand horizontally; User Scale keeps its conditional visibility.
    b['obj-135']['text']='680';b['obj-14']['text']='907'
    b['obj-1']['presentation_rect'][0]=680
    p['devicewidth']=680
    # Register only new parameters; preserve all existing parameter keys and banks.
    def register(q,prefix):
        for box in boxes(q).values():
            path=prefix+box['id'];v=box.get('saved_attribute_attributes',{}).get('valueof',{})
            if box.get('parameter_enable') and v.get('parameter_longname'):
                p.setdefault('parameters',{})[path]=[v['parameter_longname'],v['parameter_shortname'],0]
            if 'patcher' in box:register(box['patcher'],path+'::')
    register(bank,'length-bank::')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists() or args.source.resolve()==args.output.resolve():
        parser.error('Output must be a new file; no device is overwritten')
    try:
        raw,document,offset,size=read_device(args.source)
        if hashlib.sha256(raw).hexdigest() != SUPPORTED_SOURCE_SHA256:
            raise ValueError('Source differs from the inspected vanilla build; review its structure first')
        result=build(document)
        output=replace_document(raw,result,offset,size)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_bytes(output)
        _,reread,_,_=read_device(args.output)
        assert reread==result
    except (ValueError,KeyError,StopIteration) as exc:
        parser.error(str(exc))
    print(args.output)
    print('Source SHA256:',hashlib.sha256(raw).hexdigest())


if __name__=='__main__':main()
