"""Riferimenti e influenze ritmiche indipendenti da voci e dispositivi."""
from __future__ import annotations
from dataclasses import dataclass
import math

from desnivel.music.phrases import Note, Phrase

SUBDIVISIONS = {'32n': .125, '16n': .25, '8n': .5, '4n': 1., '2n': 2.}


@dataclass(frozen=True)
class RhythmReference:
    length_beats: float
    cycle_beats: float
    phase_beats: float
    points: tuple[tuple[float, float], ...]

    def __post_init__(self):
        object.__setattr__(self, 'points', tuple(tuple(point) for point in self.points))
        if (not math.isfinite(self.length_beats) or self.length_beats <= 0
                or not math.isfinite(self.cycle_beats) or self.cycle_beats <= 0
                or not math.isfinite(self.phase_beats) or not 0 <= self.phase_beats < self.cycle_beats):
            raise ValueError('intervallo o fase del riferimento ritmico non validi')
        previous = -1.
        for beat, weight in self.points:
            if (not math.isfinite(beat) or not previous < beat < self.length_beats or beat < 0
                    or not math.isfinite(weight) or not 0 <= weight <= 1):
                raise ValueError('appoggi ritmici ordinati, distinti e pesati in [0, 1] richiesti')
            previous = beat


@dataclass(frozen=True)
class PreparedRhythm:
    reference: RhythmReference
    material: object = None


def shape_rhythm(phrase, influences):
    """Colloca gli attacchi monofonici bilanciando posizione propria e appoggi.

    Non cambia numero, ordine, altezze o velocity. Le durate si accorciano
    solo quando lo spazio prima dell'attacco successivo diminuisce.
    """
    influences = [(points, amount) for points, amount in influences if amount > 0 and points]
    if not influences or not phrase.notes:
        return phrase
    notes = sorted(phrase.notes, key=lambda note: note.beat)
    if any(a.beat >= b.beat for a, b in zip(notes, notes[1:])):
        raise ValueError('la modellazione ritmica richiede attacchi monofonici distinti')
    total = sum(amount for _, amount in influences)
    own = max(0., 1-total)
    divisor = max(1., total)
    candidates = sorted({n.beat for n in notes} | {b for points, _ in influences for b, _ in points})
    scores = [(0., 0.)]*len(candidates)
    paths = []
    for index, note in enumerate(notes):
        current, previous = [None]*len(candidates), [None]*len(candidates)
        best = None
        for i, beat in enumerate(candidates):
            if index and i and scores[i-1] is not None and (best is None or scores[i-1] > scores[best]):
                best = i-1
            distance = abs(beat-note.beat)
            if distance > .5 or index and best is None:
                continue
            value = own*(1-distance/.5)
            for points, amount in influences:
                proximity = max(weight*max(0., 1-abs(beat-anchor)/.5) for anchor, weight in points)
                value += amount/divisor*proximity
            base = scores[best] if index else (0., 0.)
            current[i] = (base[0]+value, base[1]-distance)
            previous[i] = best
        scores = current
        paths.append(previous)
    selected = max((i for i, score in enumerate(scores) if score is not None), key=lambda i: scores[i])
    positions = []
    for previous in reversed(paths):
        positions.append(candidates[selected])
        selected = previous[selected]
    positions.reverse()
    result = []
    for i, (note, beat) in enumerate(zip(notes, positions)):
        end = positions[i+1] if i+1 < len(positions) else phrase.length_beats
        result.append(Note(beat, note.pitch, min(note.duration, end-beat), note.velocity))
    return Phrase(phrase.length_beats, tuple(result))


def rhythm_influences(request, groove_follow):
    result = []
    if groove_follow:
        if request.rhythm is None:
            raise ValueError('groove_follow richiede un riferimento ritmico configurato')
        result.append((request.rhythm.points, groove_follow))
    for relation in request.relations:
        if relation.phrase is not None:
            peak = max((n.velocity for n in relation.phrase.notes), default=1)
            points = tuple((n.beat, n.velocity/peak) for n in relation.phrase.notes)
            result.append((points, relation.spec.strength))
    return result
