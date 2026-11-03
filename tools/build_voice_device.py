"""Confeziona il dispositivo comune usando il template MIDI ufficiale di Live."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import struct

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = Path('/Applications/Ableton Live 12 Suite.app/Contents/App-Resources/Misc/Max Devices/Max MIDI Effect.amxd')
SCRIPTS = ('desnivel_voice.js', 'desnivel_transport_player.js', 'desnivel_recording.js')


def build(template: bytes, document: dict) -> bytes:
    if (template[:4] != b'ampf' or template[24:28] != b'ptch'
            or template[32:33] != b'{' or template[20:24] != bytes(4)):
        raise ValueError('richiesto un template Max MIDI Effect non congelato')
    original = json.loads(template[32:].rstrip(b'\0\r\n '))
    result = json.loads(json.dumps(document))
    if 'project' in original['patcher']:
        result['patcher']['project'] = original['patcher']['project']
    payload = json.dumps(result, separators=(',', ':')).encode() + b'\n\0'
    header = bytearray(template[:32])
    struct.pack_into('<I', header, 28, len(payload))
    return bytes(header) + payload


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument('--output', type=Path, required=True, help='Cartella per device e dipendenze JS.')
    parser.add_argument('--update', action='store_true', help='Aggiorna il dispositivo e gli script in una cartella esistente.')
    args = parser.parse_args(argv)
    if args.output.exists() and not args.update:
        parser.error('la cartella di output deve essere nuova oppure usare --update')
    document = json.loads((ROOT / 'm4l/desnivel_voice.maxpat').read_text())
    device = build(args.template.read_bytes(), document)
    args.output.mkdir(parents=True, exist_ok=args.update)
    (args.output / 'Desnivel_Voice.amxd').write_bytes(device)
    for script in SCRIPTS:
        shutil.copyfile(ROOT / 'm4l' / script, args.output / script)
    print(args.output / 'Desnivel_Voice.amxd')


if __name__ == '__main__':
    main()
