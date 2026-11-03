"""Materiale di una voce ciclica autonoma o in relazione a una frase sorgente."""
from __future__ import annotations

from dataclasses import dataclass
import math

from desnivel.music.patterns import Pattern, SCALES
from desnivel.music.phrases import Phrase
from desnivel.music.automation import bounded
from desnivel.music.rhythm import SUBDIVISIONS

DEFAULTS = {
    'melody': dict(octave=0, activity=.65, velocity=85, length_ms=220, movement=.25, pulse='16n'),
    'bass_line': dict(octave=-1, activity=.4, velocity=75, length_ms=160, movement=.15, pulse='8n'),
    'sustained_texture': dict(octave=1, activity=.15, velocity=48, length_ms=2500, movement=.1, pulse='4n'),
}
ROLES = tuple(DEFAULTS)


@dataclass(frozen=True)
class SequenceMaterial:
    notes: tuple[int, ...]
    gates: tuple[int, ...]
    velocities: tuple[int, ...]
    lengths_ms: tuple[float, ...]
    movement: float = 0.
    step_beats: float = .25

    def __post_init__(self):
        Pattern(self.notes, self.gates)
        if (len(self.velocities) != len(self.notes) or len(self.lengths_ms) != len(self.notes)
                or any(type(v) is not int or not 1 <= v <= 127 for v in self.velocities)
                or any(type(v) not in (int, float) or not math.isfinite(v) or not 10 <= v <= 10000
                       for v in self.lengths_ms)):
            raise ValueError('velocity e durate finite richieste per ogni cella')
        if (not math.isfinite(self.movement) or not 0 <= self.movement <= 1
                or self.step_beats not in SUBDIVISIONS.values()):
            raise ValueError('movimento o suddivisione della sequenza non validi')


def compose(context, role, values, *, motif=(0, 2, 4, 1), source: Phrase | None = None,
            coordinated=False, steps=16):
    """Restituisce celle musicali; non assume percorsi o parametri di un device.

    Coordinato: riprende le altezze della sorgente; la linea principale usa
    le classi di altezza, l'accompagnamento dirada i gate, la tessitura sostiene
    la classe di altezza più pesante. Una sorgente silenziosa produce silenzio.
    """
    if role not in ROLES or context.scale not in SCALES:
        raise ValueError('ruolo o scala della voce ciclica non valido')
    if type(steps) is not int or not 1 <= steps <= 128:
        raise ValueError('numero di celle richiesto fra 1 e 128')
    if set(values) != set(DEFAULTS[role]):
        raise ValueError('controlli della voce ciclica non validi')
    octave, activity, velocity, length = (values[k] for k in ('octave', 'activity', 'velocity', 'length_ms'))
    movement = values['movement']
    if (type(octave) is not int or not -3 <= octave <= 3 or type(velocity) is not int or not 1 <= velocity <= 127
            or type(activity) not in (int, float) or not math.isfinite(activity) or not 0 <= activity <= 1
            or type(length) not in (int, float) or not math.isfinite(length) or not 10 <= length <= 10000
            or type(movement) not in (int, float) or not math.isfinite(movement) or not 0 <= movement <= 1
            or values['pulse'] not in SUBDIVISIONS):
        raise ValueError('controlli della voce ciclica fuori intervallo')
    if not motif or any(type(d) is not int or d < 0 for d in motif):
        raise ValueError('motivo richiesto come gradi interi non negativi')
    intervals = SCALES[context.scale]
    base = context.root+12*octave
    degrees = motif if role == 'melody' else (0, 4, 0, 2) if role == 'bass_line' else (0,)
    if role == 'melody':
        degrees = tuple(round(d*(.6+.8*movement)) for d in degrees)
    notes = [base+intervals[d % len(intervals)]+12*(d//len(intervals))
             for d in (degrees[i % len(degrees)] for i in range(steps))]
    candidates = list(range(steps))
    ordered = []
    if coordinated:
        if source is None:
            raise ValueError('la modalità coordinata richiede una frase sorgente')
        if not source.notes:
            candidates = []
        else:
            attacks = {min(steps-1, int(n.beat/source.length_beats*steps)) for n in source.notes}
            if role == 'sustained_texture':
                weights = {}
                for n in source.notes:
                    weights[n.pitch % 12] = weights.get(n.pitch % 12, 0)+n.duration*n.velocity
                pitch_class = max(sorted(weights), key=weights.get)
                notes = [base+(pitch_class-base) % 12]*steps
            else:
                ordered = sorted(source.notes, key=lambda n: (n.beat, n.pitch))
                notes = [base+(ordered[i % len(ordered)].pitch-base) % 12 for i in range(steps)]
                if role == 'bass_line':
                    activity *= 1-.5*len(attacks)/steps
    count = min(len(candidates), round(steps*activity))
    # Distribuzione stabile: gli accenti forti restano leggibili; il movimento
    # sposta gli attacchi deboli, senza cambiare casualmente a ogni polling.
    chosen = {candidates[int(i*len(candidates)/count)] for i in range(count)} if count else set()
    if movement >= .5:
        chosen = {i+1 if i % 4 == 1 and i+1 < steps else i-1 if i % 4 == 2 else i for i in chosen}
    accents = [1. if i % 4 == 0 else .35 if i % 2 == 0 else -.5 for i in range(steps)]
    velocities = [round(bounded(velocity+(4+12*movement)*a, 1, 127)) for a in accents]
    lengths = [bounded(length*(1+.25*a-movement*.2*(1-a)), 10, 10000) for a in accents]
    if ordered:
        average_velocity = sum(n.velocity for n in ordered)/len(ordered)
        average_duration = sum(n.duration for n in ordered)/len(ordered)
        for i in range(steps):
            note = ordered[i % len(ordered)]
            velocities[i] = round(bounded(velocities[i]+.5*(note.velocity-average_velocity), 1, 127))
            lengths[i] = bounded(lengths[i]*bounded(note.duration/average_duration, .5, 2.), 10, 10000)
    if any(not 0 <= n <= 127 for n in notes):
        raise ValueError('materiale della voce ciclica fuori dal registro MIDI')
    return SequenceMaterial(tuple(notes), tuple(int(i in chosen) for i in range(steps)),
                            tuple(velocities), tuple(float(n) for n in lengths), movement, SUBDIVISIONS[values['pulse']])
