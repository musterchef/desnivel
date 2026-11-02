"""Accompagnamento parametrico da una frase, indipendente da sorgente e player."""
from __future__ import annotations

from collections import defaultdict
from bisect import bisect_left
from dataclasses import dataclass, replace
import math
import random

from desnivel.music.phrases import Note, Phrase

# I preset forniscono solo valori: il percorso musicale è unico.
PRESETS = {
    'responsive': dict(density=.8, syncopation=.25, rhythm_follow=.35,
                       melody_follow=.25, mobility=.15, variation=.35,
                       min_spacing=1.0, articulation=.9),
    'follow': dict(density=4.0, syncopation=0.0, rhythm_follow=1.0,
                   melody_follow=1.0, mobility=0.0, variation=0.0,
                   min_spacing=1.0, articulation=.9),
    'slap': dict(density=1.8, syncopation=.7, rhythm_follow=.15,
                 melody_follow=.5, mobility=.85, variation=.5,
                 min_spacing=.5, articulation=.5),
}


@dataclass(frozen=True)
class BassSettings:
    lowest: int = 28
    highest: int = 47
    min_spacing: float | None = None
    articulation: float | None = None
    velocity_ratio: float = .9
    strategy: str = 'responsive'  # Alias storico del nome del preset.
    seed: int = 0
    variation_period: int = 4
    max_hold: float = 2.0
    grid: float = .5
    density: float | None = None
    syncopation: float | None = None
    rhythm_follow: float | None = None
    melody_follow: float | None = None
    mobility: float | None = None
    variation: float | None = None

    def __post_init__(self):
        if self.strategy not in PRESETS:
            raise ValueError('preset basso sconosciuto')
        for name, default in PRESETS[self.strategy].items():
            if getattr(self, name) is None:
                object.__setattr__(self, name, default)
        if type(self.seed) is not int or type(self.variation_period) is not int or self.variation_period < 1:
            raise ValueError('seed intero e variation_period positivo richiesti')
        if (type(self.lowest) is not int or type(self.highest) is not int
                or not 0 <= self.lowest <= self.highest <= 127
                or self.highest - self.lowest < 11):
            raise ValueError('registro del basso: almeno 12 note MIDI consecutive')
        for name in ('min_spacing', 'max_hold', 'grid'):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(name + ' deve essere positivo e finito')
        if not math.isfinite(self.density) or self.density < 0:
            raise ValueError('density deve essere non negativa e finita')
        for name in ('syncopation', 'rhythm_follow', 'melody_follow', 'mobility', 'variation'):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(name + ' deve essere in [0, 1]')
        for name in ('articulation', 'velocity_ratio'):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0 < value <= 1:
                raise ValueError(name + ' deve essere in (0, 1]')


def interpolate_settings(start: BassSettings, target: BassSettings, amount: float) -> BassSettings:
    """Interpola i controlli musicali; seed, griglia e periodo restano discreti."""
    if not math.isfinite(amount) or not 0 <= amount <= 1:
        raise ValueError('amount deve essere in [0, 1]')
    if amount == 0:
        return start
    if amount == 1:
        return target
    values = {}
    for name in ('lowest', 'highest', 'density', 'syncopation', 'rhythm_follow',
                 'melody_follow', 'mobility', 'variation', 'min_spacing',
                 'articulation', 'velocity_ratio', 'max_hold'):
        value = getattr(start, name) * (1 - amount) + getattr(target, name) * amount
        values[name] = math.floor(value + .5) if name in ('lowest', 'highest') else value
    return replace(target, **values)


def _salience(melody):
    weights = defaultdict(float)
    for note in melody.notes:
        accent = 1.5 if abs(note.beat - round(note.beat)) < 1e-8 else 1.0
        weights[note.pitch % 12] += note.duration * note.velocity * accent
    return weights


def _rhythm(melody, settings, rng):
    """La densità decide quanti attacchi; i pesi decidono dove collocarli."""
    start = min(n.beat for n in melody.notes)
    attacks = {round(n.beat, 9) for n in melody.notes}
    slots = set(attacks)
    if settings.rhythm_follow < 1:
        for i in range(math.ceil(start / settings.grid), math.ceil(melody.length_beats / settings.grid)):
            slots.add(round(i * settings.grid, 9))
    ranked = []
    for beat in sorted(slots):
        if beat >= melody.length_beats:
            continue
        strong = abs(beat - round(beat)) < 1e-8
        coincides = beat in attacks
        metric = (1 - settings.syncopation) if strong else settings.syncopation
        relation = settings.rhythm_follow if coincides else 1 - settings.rhythm_follow
        score = metric + 2 * relation + rng.random() * settings.variation
        # Un primo appoggio rende riconoscibile l'ingresso, anche con molte sincopi.
        if beat == start:
            score += 4
        ranked.append((score, beat))
    target = round(min(len(ranked), settings.density * (melody.length_beats - start)))
    selected, chronological = [], []
    for _, beat in sorted(ranked, key=lambda item: (-item[0], item[1])):
        index = bisect_left(chronological, beat)
        spacing = settings.min_spacing-1e-9
        if ((index == 0 or beat-chronological[index-1] >= spacing)
                and (index == len(chronological) or chronological[index]-beat >= spacing)):
            selected.append(beat)
            chronological.insert(index, beat)
    onsets = sorted(selected[:target])
    return onsets, {'requested': settings.density, 'target_attacks': target,
                    'capacity_attacks': len(selected), 'selected_attacks': len(onsets),
                    'active_beats': melody.length_beats-start,
                    'saturated': bool(selected) and target >= len(selected)}


def _pitches(melody, onsets, settings, previous_pitch, rng, resolve):
    """Bilancia nota locale, appoggi osservati e continuità del registro."""
    weights = _salience(melody)
    peak = max(weights.values())
    anchor = max(weights, key=lambda pc: (weights[pc], -pc))
    candidates = [p for p in range(settings.lowest, settings.highest + 1) if p % 12 in weights]
    previous = previous_pitch if previous_pitch is not None else (settings.lowest + settings.highest) / 2
    result = []
    for index, beat in enumerate(onsets):
        nearby = min(melody.notes, key=lambda n: (abs(n.beat - beat), -n.velocity, n.pitch))
        sounding = [n for n in melody.notes if n.beat <= beat < n.beat + n.duration]
        offbeat = abs(beat - round(beat)) >= 1e-8
        # Mobilità alta apre risposte acute; bassa privilegia il movimento vicino.
        center = (settings.lowest + settings.highest) / 2
        target = center + (6 if offbeat else -6) * settings.mobility
        jitter = {p: rng.random() * settings.variation for p in candidates}

        def score(pitch):
            harmony = sum(1 if (n.pitch - pitch) % 12 in (0, 3, 4, 5, 7, 8, 9) else -2
                          for n in sounding) / max(1, len(sounding))
            home = 0
            if pitch % 12 == anchor:
                if index == 0:
                    home = 2.5
                elif resolve and index == len(onsets) - 1:
                    home = 2.5 * settings.variation
            independent = home + harmony + weights[pitch % 12] / peak
            local = 4 if pitch % 12 == nearby.pitch % 12 else -4
            continuity = abs(pitch - previous) * .1 * (1 - settings.mobility)
            register = abs(pitch - target) * .15 * settings.mobility
            repeat = .5 if result and pitch == result[-1] else 0
            return ((1 - settings.melody_follow) * independent + settings.melody_follow * local
                    - continuity - register - repeat * (1 - settings.melody_follow) + jitter[pitch])

        pitch = max(candidates, key=lambda p: (score(p), -p))
        result.append((pitch, nearby))
        previous = pitch
    return result


def _articulate(melody, onsets, pitches, settings):
    notes = []
    for index, (beat, (pitch, source)) in enumerate(zip(onsets, pitches)):
        end = onsets[index + 1] if index + 1 < len(onsets) else melody.length_beats
        available = min(end - beat, settings.max_hold)
        # Il legame ritmico influenza anche il respiro della nota sorgente.
        source_hold = min(available, source.duration)
        hold = available * (1 - settings.rhythm_follow) + source_hold * settings.rhythm_follow
        strong = abs(beat - round(beat)) < 1e-8
        metric_accent = 1 if index == 0 else (.92 if strong else .75)
        accent = metric_accent * (1 - settings.rhythm_follow) + settings.rhythm_follow
        duration = hold * settings.articulation
        velocity = max(1, min(127, round(source.velocity * settings.velocity_ratio * accent)))
        notes.append(Note(beat, pitch, duration, velocity))
    return Phrase(melody.length_beats, tuple(notes))


def generate_bass(melody: Phrase, settings: BassSettings = BassSettings(),
                  previous_pitch: int | None = None, *, phrase_index: int = 0) -> Phrase:
    """Stessi input musicali e seed producono lo stesso piano, senza stato RNG globale."""
    return plan_bass(melody, settings, previous_pitch, phrase_index=phrase_index)[0]


def plan_bass(melody: Phrase, settings: BassSettings = BassSettings(),
              previous_pitch: int | None = None, *, phrase_index: int = 0) -> tuple[Phrase, dict]:
    """Compone la frase e descrive la capacità ritmica dello stesso piano."""
    if type(phrase_index) is not int or phrase_index < 0:
        raise ValueError('phrase_index deve essere un intero non negativo')
    if previous_pitch is not None and (type(previous_pitch) is not int or not 0 <= previous_pitch <= 127):
        raise ValueError('previous_pitch deve essere una nota MIDI')
    if not melody.notes or settings.density == 0:
        return Phrase(melody.length_beats, ()), {
            'requested': settings.density, 'target_attacks': 0, 'capacity_attacks': None,
            'selected_attacks': 0, 'active_beats': None, 'saturated': False,
            'unavailable_reason': 'source_silent' if not melody.notes else 'density_zero'}
    # Nessuna ripetizione forzata di un catalogo di groove ogni quattro frasi.
    rng = random.Random(settings.seed + phrase_index * 104729)
    onsets, density = _rhythm(melody, settings, rng)
    resolve = (phrase_index + 1) % settings.variation_period == 0
    pitches = _pitches(melody, onsets, settings, previous_pitch, rng, resolve)
    return _articulate(melody, onsets, pitches, settings), density
