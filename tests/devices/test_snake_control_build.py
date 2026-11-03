import json
from pathlib import Path
import sys

TOOLS=Path(__file__).resolve().parents[2]/'tools'
sys.path.insert(0,str(TOOLS))
from build_snake_control import document, SCRIPTS


def test_companion_reuses_voice_ui_passes_midi_and_isolates_its_ports():
    original=json.loads(Path('m4l/desnivel_voice.maxpat').read_text())
    result=document(original)['patcher']
    boxes={item['box']['id']:item['box'] for item in result['boxes']}
    assert boxes['persist']['restore']==['snake_01']
    assert boxes['interface']['text']=='js desnivel_snake_voice.js'
    assert boxes['player']['text']=='route panic'
    assert boxes['receive']['text']=='udpreceive 9201 @defer 1'
    assert boxes['receive_port']['saved_attribute_attributes']['valueof']['parameter_initial']==[9201]
    assert boxes['server_port']['saved_attribute_attributes']['valueof']['parameter_initial']==[9007]
    assert boxes['send']['text']=='udpsend 127.0.0.1 9007'
    assert not boxes['presence_label']['presentation']
    wires=[line['patchline'] for line in result['lines']]
    assert dict(source=['source_midi',0],destination=['source_flush',0]) in wires
    assert dict(source=['source_flush',0],destination=['midi_out',0]) in wires
    assert dict(source=['player',0],destination=['source_flush',0]) in wires
    assert all(w['source'][0] in boxes and w['destination'][0] in boxes for w in wires)
    assert all(Path('m4l',script).is_file() for script in SCRIPTS)
    assert original['patcher']['boxes'][0]['box']['text']=='DESNIVEL · VOICE'
