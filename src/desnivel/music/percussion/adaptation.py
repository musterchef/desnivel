"""Dinamica e sviluppo percussivo secondo contesto e spazio dell'insieme."""
from desnivel.music.automation import ParameterTarget, attack_rate, bounded


def targets(request, cycle):
    base, intent = request.parameters, request.intent
    terrain = 0. if intent.intensity is None else intent.intensity-.5
    melody = attack_rate(request.peers('melody'))
    bass = attack_rate(request.peers('bass_line'))
    crowd = bounded(.65*(melody or 0.)/1.5+.35*(bass or 0.), 0, 1)
    space = .12*(.5-crowd) if request.observation.available_beats else 0.
    change = (intent.change*intent.persistence
              if intent.change is not None and intent.persistence is not None else 0.)
    result = {
        'velocity_ratio': ParameterTarget(bounded(base['velocity_ratio']*(1+.2*terrain+.15*(intent.dynamic_pressure or 0.)), .05, 1),
            'dinamica percussiva dal contesto e dalla pressione ambientale' if intent.dynamic_pressure is not None else
            'dinamica percussiva dal contesto locale' if intent.intensity is not None else
            'dinamica di sezione: contesto locale indisponibile', 8.),
        'variation': ParameterTarget(bounded(base['variation']+.22*change+space+.2*(intent.material_change or 0.), 0, 1),
            'sviluppo dai cambiamenti persistenti e dallo spazio di melodia e basso'+
            (' e dai cambiamenti ambientali' if intent.material_change is not None else ''), 16., cycle),
    }
    if intent.dynamic_pressure is not None:
        result['velocity_ratio'] = result['velocity_ratio'].with_contribution('dynamic_pressure',
            bounded(base['velocity_ratio']*(1+.2*terrain), .05, 1))
    if intent.material_change is not None:
        result['variation'] = result['variation'].with_contribution('material_change',
            bounded(base['variation']+.22*change+space, 0, 1))
    return result
