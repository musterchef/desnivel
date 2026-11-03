import importlib.util
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('build_voice_device', ROOT / 'tools/build_voice_device.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_device_has_valid_connections_and_native_midi_output():
    patch = json.loads((ROOT / 'm4l/desnivel_voice.maxpat').read_text())['patcher']
    boxes = {entry['box']['id']: entry['box'] for entry in patch['boxes']}
    for line in patch['lines']:
        assert line['patchline']['source'][0] in boxes
        assert line['patchline']['destination'][0] in boxes
    assert boxes['midi_format']['text'] == 'midiformat'
    assert boxes['midi_out']['text'] == 'midiout'
    assert boxes['notes_unpack']['varname'] == 'notes_unpack'
    assert boxes['notes_flush']['varname'] == 'notes_flush'
    assert boxes['receive']['text'] == 'udpreceive 9101 @defer 1'
    assert boxes['route']['text'] == 'route /desnivel/v1/voice/message /desnivel/v1/voice/connect-all'
    assert all('bass' not in box.get('text', '').lower() for box in boxes.values())
    ui = [b['presentation_rect'] for b in boxes.values() if b.get('presentation')]
    assert all(x >= 0 and y >= 0 and x+w <= patch['devicewidth'] and y+h <= 169 for x,y,w,h in ui)
    weather = boxes['weather_display']
    assert weather['varname'] == 'weather_display' and weather['presentation'] == 1
    assert boxes['role_display']['presentation_rect'][0]+boxes['role_display']['presentation_rect'][2] <= weather['presentation_rect'][0]


def test_build_preserves_midi_type_and_packages_source():
    document = json.loads((ROOT / 'm4l/desnivel_voice.maxpat').read_text())
    empty = b'{"patcher":{}}\0'
    template = b'ampf' + struct.pack('<I', 4) + b'mmmmmeta' + struct.pack('<II',4,0) + b'ptch' + struct.pack('<I',len(empty)) + empty
    raw = builder.build(template, document)
    assert raw[:28] == template[:28]
    assert struct.unpack_from('<I', raw, 28)[0] == len(raw)-32
    assert json.loads(raw[32:].rstrip(b'\0\n')) == document


def test_voice_identity_uses_a_stored_live_parameter_bound_to_the_editor():
    patch = json.loads((ROOT / 'm4l/desnivel_voice.maxpat').read_text())['patcher']
    boxes = {entry['box']['id']: entry['box'] for entry in patch['boxes']}
    identity = boxes['persist']
    assert identity['text'] == 'pattr voice_identity'
    assert identity['saved_object_attributes']['parameter_enable'] == 1
    assert '@parameter_enable' not in identity['text']
    assert identity['saved_attribute_attributes']['valueof']['parameter_type'] == 3
    assert identity['saved_attribute_attributes']['valueof']['parameter_invisible'] == 1
    assert patch['parameters']['persist'][0] == 'Voice_ID'
    assert any(line['patchline']['source'] == ['persist', 1]
               and line['patchline']['destination'] == ['voice_id', 0] for line in patch['lines'])


def test_live_transport_commands_reach_the_resolved_song_object():
    patch = json.loads((ROOT / 'm4l/desnivel_voice.maxpat').read_text())['patcher']
    boxes = {entry['box']['id']: entry['box'] for entry in patch['boxes']}
    assert boxes['live_transport_control']['text'] == 'live.object'
    paths = [(line['patchline']['source'], line['patchline']['destination']) for line in patch['lines']]
    assert (['resolve', 0], ['live_transport_control', 1]) in paths
    assert (['interface', 3], ['live_transport_control', 0]) in paths


def test_connect_all_reuses_the_button_trigger_through_a_shared_max_bus():
    patch = json.loads((ROOT / 'm4l/desnivel_voice.maxpat').read_text())['patcher']
    boxes = {entry['box']['id']: entry['box'] for entry in patch['boxes']}
    assert boxes['connect_all_send']['text'] == 's desnivel_voice_connect_all'
    assert boxes['connect_all_receive']['text'] == 'r desnivel_voice_connect_all'
    paths = [(line['patchline']['source'], line['patchline']['destination']) for line in patch['lines']]
    assert (['route', 1], ['connect_all_send', 0]) in paths
    assert (['connect_all_receive', 0], ['connect_trigger', 0]) in paths
    assert (['connect_button', 0], ['connect_trigger', 0]) in paths


def test_presence_has_a_dedicated_visible_control_and_readout():
    patch = json.loads((ROOT / 'm4l/desnivel_voice.maxpat').read_text())['patcher']
    boxes = {entry['box']['id']: entry['box'] for entry in patch['boxes']}
    for name in ('presence_multiplier', 'presence_slider', 'presence_display'):
        assert boxes[name]['varname'] == name
        assert boxes[name]['presentation'] == 1
    assert boxes['presence_multiplier']['minimum'] == 0
    assert boxes['presence_multiplier']['maximum'] == 10
    paths = [(line['patchline']['source'], line['patchline']['destination']) for line in patch['lines']]
    assert (['presence_prefix', 0], ['interface', 0]) in paths
    assert (['presence_slider_prefix', 0], ['interface', 0]) in paths


def test_boolean_parameter_uses_the_common_value_input():
    patch = json.loads((ROOT / 'm4l/desnivel_voice.maxpat').read_text())['patcher']
    boxes = {entry['box']['id']: entry['box'] for entry in patch['boxes']}
    assert boxes['parameter_toggle']['maxclass'] == 'toggle'
    assert boxes['parameter_toggle']['hidden'] == 1
    paths = [(line['patchline']['source'], line['patchline']['destination']) for line in patch['lines']]
    assert (['parameter_toggle', 0], ['toggle_prefix', 0]) in paths
    assert boxes['toggle_prefix']['text'] == 'prepend value'
    assert (['toggle_prefix', 0], ['interface', 0]) in paths


def test_manual_mode_has_a_visible_switch_and_confirmed_status():
    patch = json.loads((ROOT / 'm4l/desnivel_voice.maxpat').read_text())['patcher']
    boxes = {entry['box']['id']: entry['box'] for entry in patch['boxes']}
    for name in ('manual_toggle', 'manual_display'):
        assert boxes[name]['varname'] == name
        assert boxes[name]['presentation'] == 1
    assert boxes['manual_toggle']['maxclass'] == 'toggle'
    assert boxes['manual_prefix']['text'] == 'prepend manual'
    paths = [(line['patchline']['source'], line['patchline']['destination']) for line in patch['lines']]
    assert (['manual_toggle', 0], ['manual_prefix', 0]) in paths
    assert (['manual_prefix', 0], ['interface', 0]) in paths


def test_live_tempo_is_observed_and_forwarded_to_python():
    patch = json.loads((ROOT / 'm4l/desnivel_voice.maxpat').read_text())['patcher']
    boxes = {entry['box']['id']: entry['box'] for entry in patch['boxes']}
    assert boxes['tempo_observer']['text'] == 'live.observer tempo'
    assert boxes['tempo_prefix']['text'] == 'prepend tempo'
    paths = [(line['patchline']['source'], line['patchline']['destination']) for line in patch['lines']]
    assert (['resolve', 0], ['tempo_observer', 1]) in paths
    assert (['tempo_observer', 0], ['tempo_prefix', 0]) in paths
    assert (['tempo_prefix', 0], ['interface', 0]) in paths
