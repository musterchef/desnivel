"""Regole musicali pure: metriche in ingresso, pattern in uscita."""
from __future__ import annotations

from dataclasses import dataclass

#: Intervalli in semitoni dalla tonica.
SCALES: dict[str, tuple[int, ...]] = {
    "chromatic": tuple(range(12)),
    "major": (0, 2, 4, 5, 7, 9, 11),
    "minor": (0, 2, 3, 5, 7, 8, 10),
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "phrygian": (0, 1, 3, 5, 7, 8, 10),
    "lydian": (0, 2, 4, 6, 7, 9, 11),
    "mixolydian": (0, 2, 4, 5, 7, 9, 10),
    "pentatonic_major": (0, 2, 4, 7, 9),
    "pentatonic_minor": (0, 3, 5, 7, 10),
    "blues": (0, 3, 5, 6, 7, 10),
}



def scale_notes(scale: str, root: int, count: int = 16) -> list[int]:
    if scale not in SCALES:
        raise ValueError(f"scala sconosciuta: {scale}")
    intervals = SCALES[scale]
    return [root + 12 * (i // len(intervals)) + intervals[i % len(intervals)]
            for i in range(count)]


@dataclass(frozen=True)
class Pattern:
    notes: tuple[int, ...]
    gates: tuple[int, ...]

    def __post_init__(self):
        if not self.notes or len(self.notes) != len(self.gates):
            raise ValueError("note e gate devono avere la stessa lunghezza non nulla")
        if any(type(n) is not int for n in self.notes):
            raise ValueError("le note devono essere semitoni interi")
        if any(g not in (0, 1) for g in self.gates):
            raise ValueError("gate ammessi: 0 e 1")
