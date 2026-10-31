"""Catalogo musicale unico: ruoli, figure di riferimento e profili percussivi."""
from dataclasses import dataclass, replace
from types import MappingProxyType


HIT_ROLES = ('kick', 'rim', 'snare', 'clap', 'kick_alt', 'snare_alt', 'hat', 'snare_alt_2',
             'tom_low', 'tom_mid', 'hat_open', 'tom_high', 'crash', 'crash_alt', 'ride', 'ride_alt')
STYLE_ROLES = ('kick', 'snare', 'hat')


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


@dataclass(frozen=True)
class ReferenceMaterial:
    name: str
    length_beats: float
    hits: tuple[StyleHit, ...]
    anchor_beats: tuple = ()
    development: tuple[str, ...] = ()
    support_roles: tuple[str, ...] = ()

    def pattern(self):
        """Nuova rappresentazione modificabile per il parser dei pattern espliciti."""
        return {'name': self.name, 'length_beats': self.length_beats,
                'hits': [{'beat': h.beat, 'lane': h.role, 'velocity': h.velocity} for h in self.hits]}


MATERIALS = (
    ReferenceMaterial('spaced_impacts', 32, (
        StyleHit(0, 'kick', 105),
        StyleHit(0.75, 'hat', 36),
        StyleHit(1.5, 'snare', 78),
        StyleHit(2.5, 'hat', 48),
        StyleHit(2.75, 'hat', 30),
        StyleHit(4, 'kick', 90),
        StyleHit(4.75, 'rim', 39),
        StyleHit(5.5, 'hat', 60),
        StyleHit(6.5, 'clap', 54),
        StyleHit(6.75, 'hat', 32),
        StyleHit(8, 'kick', 98),
        StyleHit(8.75, 'ride', 42),
        StyleHit(9.5, 'snare_alt', 65),
        StyleHit(10.5, 'hat_open', 38),
        StyleHit(11.25, 'tom_high', 46),
        StyleHit(12, 'kick_alt', 85),
        StyleHit(12.75, 'ride_alt', 36),
        StyleHit(13.5, 'snare', 62),
        StyleHit(14.5, 'tom_mid', 52),
        StyleHit(15.25, 'tom_low', 60),
        StyleHit(16, 'kick', 100),
        StyleHit(16.75, 'crash', 43),
        StyleHit(17.5, 'snare_alt_2', 66),
        StyleHit(18.5, 'hat', 37),
        StyleHit(19.25, 'rim', 43),
        StyleHit(20, 'kick_alt', 88),
        StyleHit(20.75, 'ride', 40),
        StyleHit(21.5, 'clap', 58),
        StyleHit(22.5, 'hat_open', 36),
        StyleHit(23.25, 'tom_mid', 44),
        StyleHit(24, 'kick', 94),
        StyleHit(24.75, 'crash_alt', 40),
        StyleHit(25.5, 'snare_alt', 59),
        StyleHit(26.5, 'ride_alt', 34),
        StyleHit(27.25, 'hat', 40),
        StyleHit(28, 'kick_alt', 82),
        StyleHit(28.75, 'tom_high', 42),
        StyleHit(29.5, 'snare_alt_2', 53),
        StyleHit(30.5, 'tom_mid', 46),
        StyleHit(31.25, 'tom_low', 55),
    ), (0, 1.5, 4, 8, 12, 16, 20, 24, 28), ('statement', 'statement', 'subtract', 'displace', 'statement', 'accent', 'silence', 'displace'), ('kick', 'kick_alt')),
    ReferenceMaterial('regular_pulse_eighths', 4, (
        StyleHit(0, 'kick', 96),
        StyleHit(2, 'kick', 96),
        StyleHit(1, 'snare', 82),
        StyleHit(3, 'snare', 82),
        StyleHit(0, 'hat', 48),
        StyleHit(0.5, 'hat', 48),
        StyleHit(1, 'hat', 48),
        StyleHit(1.5, 'hat', 48),
        StyleHit(2, 'hat', 48),
        StyleHit(2.5, 'hat', 48),
        StyleHit(3, 'hat', 48),
        StyleHit(3.5, 'hat', 48),
    )),
    ReferenceMaterial('spaced_dialogue', 8, (
        StyleHit(0, 'kick', 105),
        StyleHit(0.75, 'hat', 48),
        StyleHit(1.5, 'snare', 78),
        StyleHit(2.5, 'hat', 55),
        StyleHit(4, 'kick', 95),
        StyleHit(4.75, 'snare', 70),
        StyleHit(5.5, 'hat', 58),
        StyleHit(6.5, 'snare', 65),
        StyleHit(7.25, 'hat', 42),
    ), (0, 1.5, 4), ('statement', 'subtract', 'displace', 'silence'), ('kick',)),
    ReferenceMaterial('regular_pulse_offbeats', 4, (
        StyleHit(0, 'kick', 100),
        StyleHit(1, 'snare', 82),
        StyleHit(2, 'kick', 95),
        StyleHit(3, 'snare', 78),
        StyleHit(0.5, 'hat', 48),
        StyleHit(1.5, 'hat', 48),
        StyleHit(2.5, 'hat', 48),
        StyleHit(3.5, 'hat', 48),
    )),
)
MATERIAL_BY_ID = MappingProxyType({material.name: material for material in MATERIALS})


def reference_material(name):
    if not isinstance(name, str) or name not in MATERIAL_BY_ID:
        raise ValueError(f'materiale percussivo sconosciuto: {name!r}')
    return MATERIAL_BY_ID[name]
