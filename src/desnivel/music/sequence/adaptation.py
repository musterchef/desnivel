"""Indicazioni del viaggio per una voce ciclica; nessuna conoscenza dell'esecutore."""
from desnivel.music.automation import ParameterTarget, bounded
from desnivel.music.rhythm import SUBDIVISIONS

PULSES = tuple(SUBDIVISIONS)


def targets(role, intent, length_beats, settings):
    """Obiettivi interpolati dalla stessa intenzione usata dalle altre voci."""
    spec = settings['roles'][role]
    base, response = spec['parameters'], spec['response']
    adaptation = settings['adaptation']
    transition = adaptation['transition_beats']
    terrain = 0. if intent.intensity is None else intent.intensity-.5
    change = intent.change or 0.
    persistence = 0. if intent.persistence is None else intent.persistence-.5
    movement = bounded(base['movement']+adaptation['movement_change']*change
                       +adaptation['movement_persistence']*persistence
                       +adaptation['movement_material_change']*(intent.material_change or 0.), 0, 1)
    activity = bounded(base['activity']+response['activity']*terrain, 0, 1)
    velocity = bounded(base['velocity']+response['velocity']*terrain
                       +adaptation['velocity_pressure']*(intent.dynamic_pressure or 0.), 1, 127)
    length = bounded(base['length_ms']*(1+response['articulation']*terrain
                     +adaptation['length_persistence']*persistence+adaptation['length_change']*change), 10, 10000)
    return {
        'activity': ParameterTarget(activity,
            'densità dal rilievo locale', transition, length_beats),
        'velocity': ParameterTarget(velocity,
            'dinamica dal rilievo e dalla pressione ambientale', transition, length_beats, integer=True, deadband=1.),
        'length_ms': ParameterTarget(length,
            'articolazione dalla continuità e dai cambi del terreno', transition, length_beats),
        'movement': ParameterTarget(movement, 'movimento dai cambi e dalla persistenza del viaggio', transition, length_beats),
    }


def pulse(intent, settings):
    """Sceglie la suddivisione dal viaggio entro l'intervallo del ruolo.

    Senza intensità disponibile usa l'estremo lento; il chiamante segnala
    questa condizione nello stato del componente.
    """
    fastest, slowest = (PULSES.index(settings[name]) for name in ('fastest', 'slowest'))
    intensity = 0. if intent.intensity is None else intent.intensity
    step = int(intensity*(slowest-fastest)+.5)
    return PULSES[slowest-step]
