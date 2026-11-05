"""Risoluzione, validazione e salvataggio della configurazione di sessione."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile


def resolve_journey(config, path, *, track=None, timing_reference=None, infer_fit_pauses=None):
    """Risolve il viaggio salvato; una traccia esplicita può sostituirlo."""
    saved = config.get('journey', {})
    if (not isinstance(saved, dict) or set(saved)-{'track', 'timing_reference', 'infer_fit_pauses'}
            or 'journey' in config and 'track' not in saved):
        raise ValueError('journey richiede track e ammette timing_reference e infer_fit_pauses')
    for key in ('track', 'timing_reference'):
        if key in saved and (not isinstance(saved[key], str) or not saved[key].strip()):
            raise ValueError(f'journey.{key} deve indicare un file')
    if 'infer_fit_pauses' in saved and type(saved['infer_fit_pauses']) is not bool:
        raise ValueError('journey.infer_fit_pauses deve essere booleano')
    base = Path(path).resolve().parent
    previous = (base/saved['track']).resolve() if saved else None
    selected = Path(track).resolve() if track is not None else previous
    if selected is None:
        raise ValueError('scegli una traccia con --track oppure salva il viaggio nella sessione')
    reuse = selected == previous
    if timing_reference is not None:
        reference = Path(timing_reference).resolve()
    elif reuse and 'timing_reference' in saved:
        reference = (base/saved['timing_reference']).resolve()
    else:
        reference = None
    if infer_fit_pauses is not None:
        infer = infer_fit_pauses
    else:
        infer = saved.get('infer_fit_pauses', False) if reuse else False
    return selected, reference, infer


def journey_configuration(path, track, timing_reference, infer_fit_pauses):
    """Conserva i percorsi rispetto al file di sessione, senza scriverlo."""
    base = Path(path).resolve().parent
    result = dict(track=os.path.relpath(Path(track).resolve(), base), infer_fit_pauses=infer_fit_pauses)
    if timing_reference is not None:
        result['timing_reference'] = os.path.relpath(Path(timing_reference).resolve(), base)
    return result


def resolve_configuration(track, config, direction):
    if direction is not None:
        from desnivel.cli.trip_direction import prepare_trip_config
        return prepare_trip_config(track, config, direction)
    resolved = deepcopy(config)
    if 'arrangement' in resolved:
        for section in resolved['sections']:
            section['assignments'] = deepcopy(resolved['arrangement'])
    return resolved


def reconfigure_runtime(runtime, config, library, *, external_voices=None):
    """Valida la nuova composizione prima di sostituire una sessione ferma."""
    from desnivel.adapters.voice_device import VoiceDeviceBridge
    from desnivel.cli.ensemble_runtime import EnsembleRuntime
    from desnivel.cli.voice_presets import connect_preset_library
    if runtime.playing:
        raise ValueError('ferma Live prima di modificare le tracce')
    bridge = VoiceDeviceBridge({}, runtime.bridge.send, clock=runtime.bridge.clock)
    candidate = EnsembleRuntime(runtime.track, config, bridge, runtime.speed, runtime.clock,
                                timing=runtime.timing, adaptive=runtime.adaptation_enabled,
                                context_sources=runtime.context_sources, external_voices=external_voices)
    connect_preset_library(library, bridge.voices, allow_missing=True)
    for name in candidate.registry.keys() & runtime.registry.keys():
        candidate.session.set_parameters(name, runtime.session.manual_parameters(name))
        candidate.session.set_role(name, runtime.session.director.manual_role(name))
        candidate.session.set_presence_multiplier(name, runtime.session.presence_state(name, runtime.progress)['multiplier'])
        bridge.voices[name].preset = runtime.bridge.voices[name].preset
    for index, section in enumerate(config['sections']):
        candidate.session.plan(section['from_progress'], index*candidate.window, candidate.window)
    candidate.reset()
    for key in ('elapsed', 'beat', 'bpm', 'epoch', 'instance', 'transport_serial', 'paused',
                'restart_count', '_restart_epoch'):
        setattr(candidate, key, getattr(runtime, key))
    if candidate.transport_voice != runtime.transport_voice:
        candidate.instance, candidate.transport_serial = None, -1
    candidate.timeline = runtime.timeline
    candidate.next_window = runtime.timeline.window_index if runtime.timeline else 0
    candidate.external_source_provider = runtime.external_source_provider
    bridge.set_bindings(config.get('live_bindings', {}))
    bridge.connections = {name: deepcopy(connection) for name, connection in runtime.bridge.connections.items()
                          if name in bridge.voices and runtime.bridge.bindings.get(name) == bridge.bindings.get(name)}
    runtime.reset()
    bridge.session, bridge.serial = runtime.bridge.session, runtime.bridge.serial
    return candidate


def save_configuration(path, config):
    path = Path(path)
    payload = json.dumps(config, ensure_ascii=False, allow_nan=False, indent=2)+'\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     prefix=path.name+'.', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(payload)
            stream.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


