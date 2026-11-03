"""Costruisce il controllo Snake riutilizzando l'interfaccia Voice."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil

from build_voice_device import DEFAULT_TEMPLATE, ROOT, build

SCRIPTS = ('desnivel_voice.js', 'desnivel_recording.js', 'desnivel_snake_voice.js', 'desnivel_snake_control.js')


def document(source):
    result = deepcopy(source)
    patch = result['patcher']
    boxes = {item['box']['id']: item['box'] for item in patch['boxes']}
    boxes['title']['text'] = 'DESNIVEL · SNAKE'
    boxes['voice_id']['text'] = 'snake_01'
    boxes['persist']['restore'] = ['snake_01']
    boxes['interface']['text'] = 'js desnivel_snake_voice.js'
    boxes['receive']['text'] = 'udpreceive 9201 @defer 1'
    boxes['send']['text'] = 'udpsend 127.0.0.1 9007'
    for name, value in (('receive_port', 9201), ('server_port', 9007)):
        boxes[name]['saved_attribute_attributes']['valueof']['parameter_initial'] = [value]
    boxes['player']['text'] = 'route panic'
    for name, box in boxes.items():
        if name.startswith(('presence_', 'preset_')) or name == 'weather_display':
            box['presentation'] = 0
    boxes['role_display']['presentation_rect'][2] = 588
    patch['lines'] = [line for line in patch['lines'] if line['patchline']['source'][0] != 'player']
    for ident, text, x in (('source_midi', 'midiin', 20), ('source_flush', 'midiflush', 180)):
        patch['boxes'].append({'box': dict(id=ident, maxclass='newobj', text=text, patching_rect=[x,1050,100,22])})
    for a, ao, b, bi in (('source_midi',0,'source_flush',0), ('source_flush',0,'midi_out',0), ('player',0,'source_flush',0)):
        patch['lines'].append({'patchline': dict(source=[a,ao],destination=[b,bi])})
    patch['dependency_cache'] = [dict(name=name,type='TEXT',implicit=1) for name in SCRIPTS]
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error('usare una cartella di output nuova')
    patch = document(json.loads((ROOT/'m4l/desnivel_voice.maxpat').read_text()))
    device = build(args.template.read_bytes(), patch)
    args.output.mkdir(parents=True)
    path = args.output/'Desnivel_Snake_Control.amxd'
    path.write_bytes(device)
    for name in SCRIPTS:
        shutil.copyfile(ROOT/'m4l'/name,args.output/name)
    print(path)


if __name__ == '__main__':
    main()
