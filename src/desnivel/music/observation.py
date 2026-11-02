"""Osservazione dei piani accettati, indipendente dai confini dei gesti."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from types import MappingProxyType
from typing import Mapping

from desnivel.music.phrases import Phrase


def _union_length(intervals):
    total, end = 0., -math.inf
    for low, high in sorted(intervals):
        total += max(0., high-max(low, end))
        end = max(end, high)
    return total


@dataclass(frozen=True)
class VoiceObservation:
    attacks: int
    attacks_per_beat: float | None
    occupied_ratio: float | None
    register: tuple[int, int] | None
    assigned_beats: float


@dataclass(frozen=True)
class EnsembleObservation:
    start_beat: float
    end_beat: float
    lookback_beats: float
    available_beats: float
    voices: Mapping[str, VoiceObservation]

    def to_dict(self):
        return dict(start_beat=self.start_beat, end_beat=self.end_beat,
                    lookback_beats=self.lookback_beats, available_beats=self.available_beats,
                    coverage_ratio=self.available_beats/self.lookback_beats,
                    voices={name: asdict(value) for name, value in self.voices.items()})


@dataclass(frozen=True)
class AcceptedWindow:
    start: float
    end: float
    phrases: Mapping[str, Phrase]


@dataclass(frozen=True)
class MusicalMemory:
    lookback_beats: float = 16.
    windows: tuple[AcceptedWindow, ...] = ()

    def __post_init__(self):
        if (type(self.lookback_beats) not in (int, float)
                or not math.isfinite(self.lookback_beats) or self.lookback_beats <= 0):
            raise ValueError('intervallo di osservazione positivo e finito richiesto')

    def before(self, start, voices):
        """Legge soltanto musica accettata che termina prima della nuova finestra."""
        if not math.isfinite(start) or start < 0:
            raise ValueError('inizio di osservazione non valido')
        low = max(0., start-self.lookback_beats)
        windows = [w for w in self.windows if w.end <= start and w.end > low]
        available = _union_length((max(low, w.start), w.end) for w in windows)
        observed = {}
        for voice in voices:
            attacks, intervals, pitches, assigned = 0, [], [], []
            for window in windows:
                phrase = window.phrases.get(voice)
                if phrase is None:
                    continue
                assigned.append((max(low, window.start), window.end))
                for note in phrase.notes:
                    onset = window.start+note.beat
                    end = onset+note.duration
                    if low <= onset < start:
                        attacks += 1
                    if end > low and onset < start:
                        intervals.append((max(low, onset), min(start, end)))
                        pitches.append(note.pitch)
            observed[voice] = VoiceObservation(
                attacks, attacks/available if available else None,
                _union_length(intervals)/available if available else None,
                (min(pitches), max(pitches)) if pitches else None, _union_length(assigned))
        return EnsembleObservation(low, start, self.lookback_beats, available,
                                   MappingProxyType(observed))

    def accepted(self, start, length, phrases):
        """Prepara una memoria successiva riutilizzando le Phrase immutabili."""
        if not math.isfinite(start) or start < 0 or not math.isfinite(length) or length <= 0:
            raise ValueError('intervallo accettato non valido')
        if any(p.length_beats != length for p in phrases.values()):
            raise ValueError('le frasi osservate devono coprire la finestra')
        low = start+length-self.lookback_beats
        previous = tuple(w for w in self.windows if low < w.end <= start)
        window = AcceptedWindow(start, start+length, MappingProxyType(dict(phrases)))
        return MusicalMemory(self.lookback_beats, (*previous, window))
