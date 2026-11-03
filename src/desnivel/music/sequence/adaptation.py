"""Indicazioni del viaggio per una voce ciclica; nessuna conoscenza dell'esecutore."""
from desnivel.music.automation import ParameterTarget, bounded
from desnivel.music.rhythm import SUBDIVISIONS

# Attività, dinamica e articolazione rispondono con pesi diversi per ruolo.
RESPONSE = {
    'melody': (.36, 24., -.45),
    'bass_line': (.24, 18., -.3),
    'sustained_texture': (.16, 12., .3),
}
PULSES = tuple(SUBDIVISIONS)


def targets(role, base, intent, length_beats):
    """Obiettivi interpolati dalla stessa intenzione usata dalle altre voci."""
    activity, velocity, articulation = RESPONSE[role]
    terrain = 0. if intent.intensity is None else intent.intensity-.5
    change = intent.change or 0.
    persistence = 0. if intent.persistence is None else intent.persistence-.5
    movement = bounded(base['movement']+.45*change-.2*persistence+.25*(intent.material_change or 0.), 0, 1)
    return {
        'activity': ParameterTarget(bounded(base['activity']+activity*terrain, 0, 1),
            'densità dal rilievo locale', 8., length_beats),
        'velocity': ParameterTarget(bounded(base['velocity']+velocity*terrain+12*(intent.dynamic_pressure or 0.), 1, 127),
            'dinamica dal rilievo e dalla pressione ambientale', 8., length_beats, integer=True, deadband=1.),
        'length_ms': ParameterTarget(bounded(base['length_ms']*(1+articulation*terrain+.25*persistence-.2*change), 10, 10000),
            'articolazione dalla continuità e dai cambi del terreno', 8., length_beats),
        'movement': ParameterTarget(movement, 'movimento dai cambi e dalla persistenza del viaggio', 8., length_beats),
    }


def pulse(base, intent):
    """Cambia suddivisione solo con un'indicazione locale nettamente calma o intensa."""
    shift = (-1 if intent.intensity >= .75 else 1 if intent.intensity <= .25 else 0) if intent.intensity is not None else 0
    return PULSES[max(0, min(len(PULSES)-1, PULSES.index(base)+shift))]
