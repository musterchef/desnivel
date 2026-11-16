"""Sviluppo di cellule del motivo con continuità melodica."""
from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import product
import random

from desnivel.music.phrases import Note, Phrase

LABELS = {'statement': 'presentazione', 'repeat': 'ripresa',
          'rhythm': 'variazione ritmica',
          'transpose': 'trasposizione', 'fragment': 'frammentazione',
          'continuation': 'prosecuzione'}

@dataclass(frozen=True)
class DevelopmentState:
    gesture_start: float
    gesture_beats: float
    gesture_index: int = 0
    last_end: float | None = None
    last_pitch: int | None = None
    cell: int = 0
    repetitions: int = 0
    open_end: bool = False


def motif_cells(degrees):
    """Cellule di 2–4 note: tratti monotoni, oppure frammenti contigui."""
    runs, first, direction = [], 0, 0
    for i in range(1, len(degrees)):
        move = (degrees[i] > degrees[i-1])-(degrees[i] < degrees[i-1])
        if move and direction and move != direction:
            runs.append(tuple(degrees[first:i]))
            first = i-1
        if move:
            direction = move
    runs.append(tuple(degrees[first:]))
    runs = [run for run in runs if len(run) >= 3]
    if not runs:
        runs = [tuple(degrees[i:i+3]) for i in range(0, max(1, len(degrees)-1), 2)]
    cells = []
    for run in runs:
        for i in range(0, max(1, len(run)-1), 3):
            cell = run[i:i+4]
            if cell and cell not in cells:
                cells.append(cell)
    return tuple(cells)


def _pitch(degree, intervals, root):
    return root+intervals[degree % len(intervals)]+12*(degree//len(intervals))


def _placements(cell, intervals, root, last_pitch, shifts, register):
    candidates = []
    center = last_pitch if last_pitch is not None else _pitch(cell[0], intervals, root)
    for shift in shifts:
        for octave in (-12, 0, 12):
            pitches = tuple(_pitch(d+shift, intervals, root)+octave for d in cell)
            if all(register[0] <= p <= register[1] for p in pitches):
                candidates.append((abs(pitches[0]-center), abs(octave), shift, octave, pitches))
    return candidates


def _fit_cell_rhythm(rhythm, step, available):
    unit = step/2
    while unit*len(rhythm) > available or int(available/unit) < len(rhythm):
        unit /= 2
    capacity = int(available/unit)
    desired = tuple(round(factor*2) for factor in rhythm)
    if sum(desired) <= capacity:
        slots = desired
    else:
        choices = (candidate for candidate in product((1, 2, 3), repeat=len(rhythm))
                   if sum(candidate) <= capacity)
        slots = min(choices, key=lambda candidate: (
            sum((a-b)**2 for a, b in zip(candidate, desired)),
            tuple(abs(a-b) for a, b in zip(candidate, desired)),
        ))
    return [slot*unit for slot in slots]


def develop(degrees, intervals, root, request, values, previous):
    """Prepara una finestra e lo stato successivo senza mutare il generatore."""
    length, step, amount = request.length_beats, values['step_beats'], values['development']
    gesture_beats = values['phrase_windows']*length
    fresh = previous is None or previous.last_end != request.start
    state = DevelopmentState(request.start, gesture_beats) if fresh else previous
    if request.start < state.gesture_start:
        raise ValueError('lo sviluppo richiede reset prima di una ripartenza precedente')
    if state.gesture_beats != gesture_beats or request.start >= state.gesture_start+state.gesture_beats:
        state = replace(state, gesture_start=request.start, gesture_beats=gesture_beats,
                        gesture_index=state.gesture_index+1)
    window = round((request.start-state.gesture_start)/length)
    rng = random.Random(values['seed']+state.gesture_index*104729+window*65537+request.context.section_index*1009)
    cells = motif_cells(degrees)
    register = (max(0, _pitch(min(degrees), intervals, root)-12),
                min(127, _pitch(max(degrees), intervals, root)+12))
    radius = max(1, round(amount*3))
    shifts = tuple(i for i in range(-radius, radius+1) if i)
    cell_index = state.cell
    if fresh or state.last_pitch is None and request.participating:
        cell_index, operation = 0, 'statement'
    elif state.repetitions >= 2 and len(cells) > 1:
        cell_index = (state.cell+1) % len(cells)
        operation = 'continuation'
    else:
        operations = ['repeat', 'rhythm', 'fragment', 'continuation']
        weights = [1-amount+.1, amount, amount*.7, amount*(1.5 if state.open_end else .2)]
        if _placements(cells[cell_index], intervals, root, state.last_pitch, shifts, register):
            operations.append('transpose')
            weights.append(amount)
        operation = rng.choices(operations, weights)[0]
    cell = cells[cell_index]
    # Una cellula mantiene gli intervalli. Le connessioni scelgono l'ottava
    # più vicina all'ultima altezza, entro un'ottava dal registro configurato.
    candidates = _placements(cell, intervals, root, state.last_pitch, shifts if operation == 'transpose' else (0,), register)
    if not candidates:
        raise ValueError('nessuna trasformazione della cellula compatibile con il registro MIDI')
    if operation == 'transpose':
        # Sceglie tra trasposizioni realizzabili, senza estrazioni nota per nota.
        shift = rng.choice(sorted({c[2] for c in candidates}))
        candidates = [c for c in candidates if c[2] == shift]
    _, _, shift, octave, pitches = min(candidates)
    can_sound = request.participating
    rhythm_rng = random.Random(values['seed']+cell_index*59)
    rhythm = [rhythm_rng.choices((.5, 1., 1.5),
                                (values['activity']*.6, 1., (1-values['activity'])*.6))[0] for _ in pitches]
    if operation == 'rhythm':
        rhythm = [rng.choice((.5, 1., 1.5)) for _ in pitches]
    slots = _fit_cell_rhythm(rhythm, step, length)
    notes, beat, anchor_beats = [], 0., []
    for i, (pitch, slot) in enumerate(zip(pitches, slots)):
        duration = slot*min(1., values['articulation']*rng.uniform(.9, 1.05))
        velocity = max(1, min(127, round(values['velocity']+(5 if i == 0 else 0)+rng.uniform(-3, 3))))
        notes.append(Note(beat, pitch, min(duration, length-beat), velocity))
        anchor_beats.append(beat)
        beat += slot
    # Il seguito riprende il frammento oppure ne estende la direzione.
    tail = pitches[:max(1, len(pitches)//2)] if operation == 'fragment' else pitches
    cursor, last_degree = 0, cell[-1]+shift
    while beat < length-1e-9:
        if len(notes) >= 127:
            raise ValueError('lo sviluppo supera 128 eventi per finestra')
        slot = step*rng.choices((.5, 1., 1.5, 2.),
                               (values['activity']*.6, 1., .35, (1-values['activity'])*1.2+.1))[0]
        slot = min(slot, length-beat)
        rest = rng.random() < (1-values['activity'])*.45
        if operation == 'continuation':
            direction = 1 if cell[-1] >= cell[0] else -1
            lower, upper = -len(intervals), max(degrees)+len(intervals)
            candidate = last_degree+direction
            if not lower <= candidate <= upper or not register[0] <= _pitch(candidate, intervals, root)+octave <= register[1]:
                candidate = last_degree-direction
            pitch = _pitch(candidate, intervals, root)+octave
            if not 0 <= pitch <= 127:
                raise ValueError('prosecuzione fuori dal registro MIDI')
            if not rest:
                last_degree = candidate
        else:
            pitch = tail[cursor % len(tail)]
        if not rest:
            velocity = max(1, min(127, round(values['velocity']+(-7 if beat % 1 else 0)+rng.uniform(-3, 3))))
            notes.append(Note(beat, pitch, slot*values['articulation'], velocity))
            cursor += 1
        beat += slot
    phrase = Phrase(length, tuple(notes))
    moved = notes[-1].pitch-notes[-2].pitch if len(notes) > 1 else 0
    next_state = replace(state, last_end=request.start+length,
                         last_pitch=notes[-1].pitch if can_sound else state.last_pitch,
                         cell=cell_index, repetitions=state.repetitions+1 if cell_index == state.cell and operation != 'statement' else 1,
                         open_end=bool(moved) and notes[-1].duration < step*1.25)
    if not can_sound:
        next_state = replace(next_state, cell=state.cell, repetitions=state.repetitions,
                             open_end=state.open_end)
    decision = {'method': 'motif_development', 'phase': operation,
                'cell': cell_index, 'cell_degrees': list(cell), 'degree_shift': shift, 'octave_shift': octave,
                'anchor_beats': anchor_beats, 'anchor_pitches': list(pitches),
                'window': window+1, 'windows': values['phrase_windows'], 'seed': values['seed'],
                'summary': f'{LABELS[operation]} · cellula {cell_index+1} · gesto {window+1}/{values["phrase_windows"]}'}
    return phrase, decision, next_state
