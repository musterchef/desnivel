"""Profili ritmici in 4/4: ruoli percussivi, accenti e timing espliciti."""
from __future__ import annotations

from dataclasses import dataclass, replace
import math
import random


@dataclass(frozen=True)
class StyleHit:
    beat: float
    role: str
    velocity: int
    structural: bool = False
    response: bool = False


@dataclass(frozen=True)
class DrumStyle:
    id: str
    label: str
    variants: tuple[tuple[StyleHit, ...], ...]
    swing_delay: float = 0.
    cycle_beats: float = 4.
    meter: tuple[int, int] = (4, 4)

    def variant(self, cycle, seed, variation=.7):
        # Frasi di quattro battute: esposizione, richiamo, variazione, chiusura.
        # Il sorteggio riguarda figure intere, non singoli colpi.
        if variation == 0:
            return 0
        phrase, bar = divmod(cycle, 4)
        rng = random.Random(f'{self.id}:{seed}:{phrase}')
        main = phrase % 2
        if bar == 0 or rng.random() > variation:
            return main
        choices = (2, 3) if bar == 3 else (1-main, 2)
        return rng.choice(choices)


def _hits(kicks, hats, extra=()):
    core = [StyleHit(b, 'kick', v, True) for b, v in kicks]
    core += [StyleHit(1, 'snare', 102, True), StyleHit(3, 'snare', 98, True)]
    return tuple(sorted(core+[StyleHit(b, 'hat', v) for b, v in hats]+list(extra), key=lambda h: (h.beat, h.role)))


STYLES = (
    DrumStyle('house_classic', 'House classica', (
        _hits(((0, 110), (1, 104), (2, 108), (3, 104)),
              ((.5, 76), (1.5, 68), (2.5, 74), (3.5, 68))),
        _hits(((0, 110), (1, 104), (2, 108), (3, 104)),
              ((.5, 76), (1.5, 68), (2.5, 74), (3.5, 68)), (StyleHit(3.75, 'hat', 38, response=True),)),
    )),
    DrumStyle('boom_bap_90s', 'Boom bap', (
        _hits(((0, 112), (1.75, 88), (2, 105)),
              tuple((i*.5, 64 if i % 2 == 0 else 43) for i in range(8))),
        _hits(((0, 112), (2, 105), (2.75, 82)),
              tuple((i*.5, 64 if i % 2 == 0 else 43) for i in range(8)),
              (StyleHit(2.75, 'snare', 34, response=True),)),
    ), swing_delay=.08),
    DrumStyle('breakbeat_house', 'Breakbeat house', (
        _hits(((0, 110), (1.5, 97), (2.75, 104)),
              tuple((i*.5, 40 if i % 2 == 0 else 67) for i in range(8)),
              (StyleHit(3.75, 'hat', 35, response=True),)),
        _hits(((0, 110), (1.75, 97), (2.5, 104)),
              tuple((i*.5, 40 if i % 2 == 0 else 67) for i in range(8)),
              (StyleHit(2.75, 'snare', 36, response=True),)),
    ), swing_delay=.04),
)


def _vocabulary(style):
    base = style.variants[0]
    # Una figura più rada di piatti e una chiusura con levare di cassa.
    sparse = tuple(replace(h, velocity=max(1, h.velocity-8)) if h.role == 'hat' else h
                   for h in base if h.role != 'hat' or h.beat % 1 == .5)
    closing = tuple(h for h in style.variants[1] if h.beat != 3.75)
    closing += (StyleHit(3.75, 'kick', 68, True), StyleHit(3.5, 'snare', 32, response=True))
    return replace(style, variants=style.variants+(sparse, tuple(sorted(closing, key=lambda h: (h.beat, h.role)))))


STYLES = tuple(_vocabulary(style) for style in STYLES)
STYLE_BY_ID = {style.id: style for style in STYLES}
STYLE_OPTIONS = (('none', 'Nessuno'),)+tuple((style.id, style.label) for style in STYLES)


def style_events(style, lanes, start, end, seed, variation=.7):
    """Attacchi assoluti (beat, MIDI, velocity, struttura), prima dello sviluppo."""
    result = []
    for cycle in range(math.floor(start/style.cycle_beats), math.ceil(end/style.cycle_beats)):
        variant = style.variants[style.variant(cycle, seed, variation)]
        for hit in variant:
            delay = style.swing_delay if hit.role == 'hat' and hit.beat % 1 == .5 else 0.
            beat = cycle*style.cycle_beats+hit.beat+delay
            if start <= beat < end:
                result.append((beat, lanes[hit.role], hit.velocity, hit.structural))
    return sorted(result)


@dataclass(frozen=True)
class StyleTransition:
    target: str
    sources: tuple[tuple[str, float], ...]
    start: float
    duration: float
    variant_offsets: tuple[tuple[str, int], ...] = ()

    def variant(self, name, cycle, seed, variation):
        style = STYLE_BY_ID[name]
        offset = dict(self.variant_offsets).get(name, 0) if variation else 0
        return (style.variant(cycle, seed, variation)+offset) % len(style.variants)

    def weights(self, beat):
        amount = min(1., max(0., (beat-self.start)/self.duration)) if self.duration else 1.
        weights = {name: weight*(1-amount) for name, weight in self.sources}
        weights[self.target] = weights.get(self.target, 0.)+amount
        return {name: weight for name, weight in weights.items() if weight > 1e-9}


@dataclass(frozen=True)
class StyleMaterial:
    events: tuple
    transition: StyleTransition


def transition_for(previous, target, start, duration, seed=7, variation=.7):
    if previous is None or previous.target == 'none' or target == 'none':
        return StyleTransition(target, ((target, 1.),), start, 0.)
    if previous.target == target:
        return previous
    sources = tuple(previous.weights(start).items())
    offsets = {name: dict(previous.variant_offsets).get(name, 0) for name, _ in sources}
    if target not in offsets and variation and duration:
        cycle = math.floor(start/4)
        source = {}
        for name, weight in sources:
            style = STYLE_BY_ID[name]
            for hit in style.variants[previous.variant(name, cycle, seed, variation)]:
                if hit.structural:
                    key = (hit.beat, hit.role)
                    source[key] = source.get(key, 0.)+weight*hit.velocity/127
        def distance(index):
            hits = {(hit.beat, hit.role): hit.velocity/127
                    for hit in STYLE_BY_ID[target].variants[index] if hit.structural}
            return sum(abs(source.get(key, 0.)-hits.get(key, 0.)) for key in source.keys() | hits.keys())
        style = STYLE_BY_ID[target]
        preferred = style.variant(cycle, seed, variation)
        closest = min(range(len(style.variants)), key=lambda i: (distance(i), i != preferred, i))
        offsets[target] = (closest-preferred) % len(style.variants)
    return StyleTransition(target, sources, start, duration, tuple(sorted(offsets.items())))


def transition_events(transition, lanes, start, end, seed, variation):
    """Figure allineate sulla griglia: accenti e swing interpolati, senza doppi hat."""
    names = set(dict(transition.sources)) | {transition.target}
    result = []
    for cycle in range(math.floor(start/4), math.ceil(end/4)):
        figures = {}
        for name in sorted(names):
            style = STYLE_BY_ID[name]
            for hit in style.variants[transition.variant(name, cycle, seed, variation)]:
                figures.setdefault((hit.beat, hit.role), []).append((name, hit, style.swing_delay))
        for (offset, role), hits in sorted(figures.items()):
            absolute = cycle*4+offset
            weights = transition.weights(absolute)
            velocity = sum(weights.get(name, 0)*hit.velocity for name, hit, _ in hits)
            # Normalizza solo il timing: le figure esclusive entrano/escono in dinamica.
            mass = sum(weights.get(name, 0) for name, _, _ in hits)
            delay = (sum(weights.get(name, 0)*swing for name, _, swing in hits)/mass
                     if mass and role == 'hat' and offset % 1 == .5 else 0.)
            beat = absolute+delay
            if start <= beat < end and round(velocity) > 0:
                result.append((beat, lanes[role], round(velocity), any(h.structural for _, h, _ in hits),
                               all(h.response for _, h, _ in hits)))
    return tuple(sorted(result))
