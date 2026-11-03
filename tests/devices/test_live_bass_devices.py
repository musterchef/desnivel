"""Verifica il confezionamento senza distribuire il device di terzi nei test."""
import importlib.util
import json
from pathlib import Path
import struct
import sys

TOOLS=Path(__file__).resolve().parents[2]/'tools'
spec=importlib.util.spec_from_file_location('build_snake_length',TOOLS/'build_snake_length.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
sys.modules['build_snake_length']=base
spec=importlib.util.spec_from_file_location('build_live_bass',TOOLS/'build_live_bass.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


def fixture_container():
    payloads=[('main.amxd',b'JSON',b'{"patcher":{}}\0'),('asset.bin',b'TEXT',b'preserve\x00bytes')]
    body=bytearray(b'mx@c'+struct.pack('>III',16,0,0));directory=b''
    for name,kind,payload in payloads:
        fields={'type':kind,'fnam':name.encode()+b'\0','of32':struct.pack('>I',len(body)),
                'sz32':struct.pack('>I',len(payload))}
        entry=b''.join(k.encode()+struct.pack('>I',len(v)+8)+v for k,v in fields.items())
        directory+=b'dire'+struct.pack('>I',len(entry)+8)+entry;body.extend(payload)
    struct.pack_into('>I',body,12,len(body));body.extend(b'dlst'+struct.pack('>I',len(directory)+8)+directory)
    header=b'ampf'+struct.pack('<I',4)+b'mmmmmeta'+struct.pack('<II',4,4)+b'ptch'+struct.pack('<I',len(body))
    return header+body


def test_freeze_preserves_assets_and_embeds_script(tmp_path):
    doc={'patcher':{'boxes':[],'lines':[]}}
    frozen=builder.freeze(fixture_container(),doc,'new.amxd',{'script.js':b'outlets=1;'},True)
    path=tmp_path/'new.amxd';path.write_bytes(frozen)
    _,loaded,_,_=base.read_device(path)
    assert loaded==doc
    resources={}
    for fields in base.entries(frozen[32:]):
        offset=int.from_bytes(fields['of32'][1],'big');size=int.from_bytes(fields['sz32'][1],'big')
        resources[fields['fnam'][1].rstrip(b'\0').decode()]=frozen[32+offset:32+offset+size]
    assert resources['asset.bin']==b'preserve\x00bytes'
    assert resources['script.js']==b'outlets=1;'


def test_player_uses_ticks_outlet_and_native_midi_path():
    patch=builder.player_document(9004)['patcher']
    wires=[w['patchline'] for w in patch['lines']]
    assert any(w['source']==['when',1] and w['destination']==['now',0] for w in wires)
    assert any(w['source']==['unpack',1] and w['destination']==['flush',1] for w in wires)
    assert any(w['source']==['resolve',0] and w['destination']==['observe',1] for w in wires)
    assert base.boxes(patch)['receive']['text']=='udpreceive 9004 @defer 1'


def test_message_values_are_mirrored_without_banging_pitch():
    p={'boxes':[{'box':{'id':'display','maxclass':'message','text':'1','varname':'read_shift'}},
                {'box':{'id':'upstream','maxclass':'newobj','text':'+ 1'}}],
       'lines':[{'patchline':{'source':['upstream',0],'destination':['display',1]}}]}
    builder.mirror_message(p,'display','read_shift')
    assert base.boxes(p)['read_shift']['maxclass']=='number'
    assert 'varname' not in base.boxes(p)['display']
    wires=[x['patchline'] for x in p['lines']]
    assert any(w['source']==['upstream',0] and w['destination']==['read_shift',0] for w in wires)
    assert not any(w['source']==['read_shift',0] for w in wires)


def test_lane_parameters_expose_unique_short_names_used_by_live_api():
    names=[f'{lane}_Sequencer_{control}' for lane in ('Notes','Gates','Velocities')
           for control in ('Snake_Shape','Speed','Length','Direction','Steps_Shift')]
    seq={'boxes':[{'box':{'id':str(i),'varname':name,'parameter_enable':1,
        'saved_attribute_attributes':{'valueof':{'parameter_longname':name,'parameter_shortname':'Shapes'}}}}
        for i,name in enumerate(names)]}
    patch={'boxes':[{'box':{'id':'obj-115','patcher':seq}}],
           'parameters':{f'obj-115::{i}':[name,'Shapes',0] for i,name in enumerate(names)}}
    base.expose_lane_parameters(patch)
    assert [x['box']['saved_attribute_attributes']['valueof']['parameter_shortname'] for x in seq['boxes']]==names
    assert [patch['parameters'][f'obj-115::{i}'][:2] for i in range(len(names))]==[[name,name] for name in names]
    # A known long name does not suffice if its short API name is still ambiguous.
    assert len(set(names))==15


def test_length_limits_are_float_parameters_so_live_does_not_truncate_at_265_ms():
    # Una sorgente con controlli INT riproduce il tipo ereditato dal vanilla.
    source={'boxes':[{'box':{'id':f'custom-{i}','varname':f'Custom_{i:02d}[2]',
        'maxclass':'live.dial','saved_attribute_attributes':{'valueof':{'parameter_type':1}}}}
        for i in range(1,17)]}
    source['boxes'].append({'box':{'id':'obj-506','maxclass':'live.numbox',
        'saved_attribute_attributes':{'valueof':{'parameter_type':1,'parameter_mmin':1,'parameter_mmax':16}}}})
    bank=base.length_bank(source)
    for key in ('Min','Max'):
        metadata=base.boxes(bank)['range-'+key]['saved_attribute_attributes']['valueof']
        assert metadata['parameter_type']==0
        assert (metadata['parameter_mmin'],metadata['parameter_mmax'])==(10,10000)
        assert metadata['parameter_unitstyle']==0
