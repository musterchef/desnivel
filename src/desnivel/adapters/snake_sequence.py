"""Previsione a beat da uno stato Snake esplicito, senza accesso a Live.

Modello iniziale: Chromatic, swing zero, direzioni forwards/backwards.
Fasi e offset MIDI sono input, non valori dedotti dal numero di step.
"""
from dataclasses import dataclass
from fractions import Fraction
import math

from desnivel.music.phrases import Note, Phrase
from desnivel.music.rhythm import SUBDIVISIONS


# Celle per righe 0..15; ID Shape dell'interfaccia 1..14, Live 0..13.
SHAPES = (
    (0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15),
    (12,13,14,15,8,9,10,11,4,5,6,7,0,1,2,3),
    (0,4,8,12,1,5,9,13,2,6,10,14,3,7,11,15),
    (12,8,4,0,13,9,5,1,14,10,6,2,15,11,7,3),
    (0,4,8,12,13,9,5,1,2,6,10,14,15,11,7,3),
    (12,8,4,0,1,5,9,13,14,10,6,2,3,7,11,15),
    (0,1,2,3,7,6,5,4,8,9,10,11,15,14,13,12),
    (3,2,1,0,4,5,6,7,11,10,9,8,12,13,14,15),
    (0,1,4,8,5,2,3,6,9,12,13,10,7,11,14,15),
    (12,13,8,4,9,14,15,10,5,0,1,6,11,7,2,3),
    (0,1,2,3,7,11,15,14,13,12,8,4,5,6,10,9),
    (3,2,1,0,4,8,12,13,14,15,11,7,6,5,9,10),
    (12,13,14,15,11,7,3,2,1,0,4,8,9,10,6,5),
    (15,14,13,12,8,4,0,1,2,3,7,11,10,9,5,6),
)
SPEEDS = {name: Fraction(str(beats)) for name, beats in SUBDIVISIONS.items()}


@dataclass(frozen=True)
class Lane:
    shape: int
    speed: str
    steps: int
    direction: str
    phase_beats: float

    def __post_init__(self):
        if type(self.shape) is not int or not 1 <= self.shape <= 14:
            raise ValueError('shape deve essere un ID 1..14')
        if self.speed not in SPEEDS:
            raise ValueError('speed non supportata')
        if type(self.steps) is not int or not 1 <= self.steps <= 16:
            raise ValueError('steps deve essere un intero 1..16')
        if self.direction not in ('forwards', 'backwards'):
            raise ValueError('direzione non prevedibile nel modello corrente')
        if not math.isfinite(self.phase_beats) or self.phase_beats < 0:
            raise ValueError('phase_beats deve essere finita e non negativa')

    def cell_at(self, beat):
        position_beats = Fraction(str(beat)) + Fraction(str(self.phase_beats))
        step_position = position_beats / SPEEDS[self.speed]
        nearest_step = round(step_position)
        # Fasi esportate come float possono differire dopo il modulo del ciclo.
        # Riconcilia solo il rumore numerico sul confine, non il timing musicale.
        if abs(position_beats - nearest_step * SPEEDS[self.speed]) <= Fraction(1, 10**9):
            position = nearest_step
        else:
            position = step_position // 1
        index = int(position) % self.steps
        if self.direction == 'backwards':
            index = self.steps - 1 - index
        return SHAPES[self.shape-1][index]


@dataclass(frozen=True)
class SnakeState:
    notes: tuple[int, ...]
    gates: tuple[int, ...]
    velocities: tuple[int, ...]
    lengths_ms: tuple[float, ...]
    notes_lane: Lane
    gates_lane: Lane
    velocities_lane: Lane
    bpm: float
    midi_offset: int
    swing: float = 0

    def __post_init__(self):
        for values, low, high in ((self.notes,0,127), (self.gates,0,1), (self.velocities,0,127)):
            if len(values) != 16 or any(type(v) is not int or not low <= v <= high for v in values):
                raise ValueError('servono 16 valori interi nel range del banco')
        if len(self.lengths_ms) != 16 or any(not math.isfinite(v) or v <= 0 for v in self.lengths_ms):
            raise ValueError('servono 16 durate positive in ms')
        if not math.isfinite(self.bpm) or self.bpm <= 0:
            raise ValueError('bpm deve essere positivo e finito')
        if type(self.midi_offset) is not int or any(not 0 <= n+self.midi_offset <= 127 for n in self.notes):
            raise ValueError('offset MIDI non valido')
        if self.swing != 0:
            raise ValueError('previsione dello swing non ancora implementata')

    @classmethod
    def from_dict(cls, data):
        return cls(**{**data,
            **{key: tuple(data[key]) for key in ('notes','gates','velocities','lengths_ms')},
            **{key: Lane(**data[key]) for key in ('notes_lane','gates_lane','velocities_lane')}})


def predict(state: SnakeState, length_beats: float) -> Phrase:
    """Proietta una finestra a tempo costante; tronca le code al suo confine.

    Ogni attacco Gates legge Notes, Length e Velocity correnti. A parità
    di beat il modello applica prima gli avanzamenti delle celle.
    Il modello va confrontato con una registrazione MIDI del device.
    """
    if not math.isfinite(length_beats) or length_beats <= 0:
        raise ValueError('length_beats deve essere positivo e finito')
    interval = SPEEDS[state.gates_lane.speed]
    phase = Fraction(str(state.gates_lane.phase_beats))
    first = (-phase) % interval
    stop = Fraction(str(length_beats))
    result = []
    beat = first
    while beat < stop:
        gate = state.gates[state.gates_lane.cell_at(beat)]
        velocity = state.velocities[state.velocities_lane.cell_at(beat)]
        if gate and velocity:
            cell = state.notes_lane.cell_at(beat)
            duration = min(state.lengths_ms[cell] * state.bpm / 60000, float(stop-beat))
            result.append(Note(float(beat), state.notes[cell]+state.midi_offset, duration, velocity))
        beat += interval
    # Il device chiude una nota prima del successivo attacco della stessa altezza.
    next_beat = {}
    for i in range(len(result)-1, -1, -1):
        n = result[i]
        duration = min(n.duration, next_beat.get(n.pitch, length_beats)-n.beat)
        result[i] = Note(n.beat, n.pitch, duration, n.velocity)
        next_beat[n.pitch] = n.beat
    return Phrase(length_beats, tuple(result))
