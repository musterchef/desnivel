"""Allocazione delle macrosezioni in finestre musicali e posizione logica del piano."""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
import math
from typing import Sequence


def _positive(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f'{name} deve essere positivo e finito')


@dataclass(frozen=True)
class TimelineSpan:
    source_index: int
    start_window: int
    window_count: int

    def __post_init__(self):
        if any(type(v) is not int or v < 0 for v in (self.source_index, self.start_window)):
            raise ValueError('indici di sezione e finestra interi non negativi richiesti')
        if type(self.window_count) is not int or self.window_count < 1:
            raise ValueError('numero di finestre intero positivo richiesto')

    @property
    def end_window(self):
        return self.start_window + self.window_count


@dataclass(frozen=True)
class Timeline:
    requested_beats: float
    window_beats: float
    min_windows: int
    distance_exponent: float
    spans: tuple[TimelineSpan, ...]
    beats_per_km: float | None = None

    def __post_init__(self):
        _positive(self.requested_beats, 'target_beats')
        _positive(self.window_beats, 'window_beats')
        if self.beats_per_km is not None:
            _positive(self.beats_per_km, 'beats_per_km')
        if type(self.min_windows) is not int or self.min_windows < 1:
            raise ValueError('min_windows deve essere un intero positivo')
        if (type(self.distance_exponent) not in (int, float)
                or not math.isfinite(self.distance_exponent) or self.distance_exponent < 0):
            raise ValueError('distance_exponent deve essere non negativo e finito')
        if not isinstance(self.spans, tuple) or not self.spans:
            raise ValueError('una timeline richiede una tupla non vuota di intervalli')
        cursor = 0
        for index, span in enumerate(self.spans):
            if (not isinstance(span, TimelineSpan) or span.source_index != index
                    or span.start_window != cursor or span.window_count < self.min_windows):
                raise ValueError('intervalli ordinati e contigui con minimi rispettati richiesti')
            if span.end_window*self.window_beats <= span.start_window*self.window_beats:
                raise ValueError('confini musicali non rappresentabili alla scala della timeline')
            cursor = span.end_window
        if not math.isfinite(self.total_beats) or self.total_beats < self.requested_beats:
            raise ValueError('durata effettiva finita e non inferiore alla richiesta necessaria')

    @property
    def total_windows(self):
        return self.spans[-1].end_window

    @property
    def total_beats(self):
        return self.total_windows * self.window_beats

    def position(self, window_index, fraction=0.):
        """Sezione e frazione interna di una finestra, inclusa la sua fine."""
        if type(window_index) is not int or not 0 <= window_index < self.total_windows:
            raise ValueError('finestra fuori dalla timeline')
        if type(fraction) not in (int, float) or not math.isfinite(fraction) or not 0 <= fraction <= 1:
            raise ValueError('frazione della finestra richiesta tra 0 e 1')
        span = self.spans[bisect_right([s.end_window for s in self.spans], window_index)]
        return span.source_index, (window_index-span.start_window+fraction)/span.window_count

    @property
    def quantized_beats(self):
        return math.ceil(self.requested_beats / self.window_beats) * self.window_beats

    @property
    def extended_for_minimum(self):
        return len(self.spans)*self.min_windows > math.ceil(self.requested_beats/self.window_beats)

    def to_dict(self):
        adjustments = []
        if self.quantized_beats > self.requested_beats:
            adjustments.append({'code': 'window_quantization', 'from_beats': self.requested_beats,
                                'to_beats': self.quantized_beats})
        if self.extended_for_minimum:
            adjustments.append({'code': 'minimum_extension', 'from_beats': self.quantized_beats,
                                'to_beats': self.total_beats})
        return {'requested_beats': self.requested_beats, 'total_beats': self.total_beats,
                'beats_per_km': self.beats_per_km,
                'total_windows': self.total_windows, 'window_beats': self.window_beats,
                'min_windows': self.min_windows, 'distance_exponent': self.distance_exponent,
                'adjustments': adjustments,
                'spans': [{'source_index': s.source_index, 'start_window': s.start_window,
                           'window_count': s.window_count, 'start_beat': s.start_window*self.window_beats,
                           'end_beat': s.end_window*self.window_beats,
                           'duration_beats': s.window_count*self.window_beats} for s in self.spans]}


def allocate_timeline(distances_m: Sequence[float], *, target_beats: float | None = None,
                      beats_per_km: float | None = None,
                      window_beats: float, min_windows: int = 2,
                      distance_exponent: float = .5) -> Timeline:
    """Riserva i minimi e assegna il residuo con pesi metrici e maggiori resti."""
    distances = tuple(distances_m)
    if not distances:
        raise ValueError('almeno una distanza richiesta')
    for value in distances:
        _positive(value, 'distanza')
    if (target_beats is None) == (beats_per_km is None):
        raise ValueError('specificare uno solo tra target_beats e beats_per_km')
    if beats_per_km is not None:
        _positive(beats_per_km, 'beats_per_km')
        distance_km = math.fsum(distances)/1000
        target_beats = distance_km*beats_per_km
    _positive(target_beats, 'target_beats')
    _positive(window_beats, 'window_beats')
    if type(min_windows) is not int or min_windows < 1:
        raise ValueError('min_windows deve essere un intero positivo')
    if (type(distance_exponent) not in (int, float)
            or not math.isfinite(distance_exponent) or distance_exponent < 0):
        raise ValueError('distance_exponent deve essere non negativo e finito')
    ratio = target_beats/window_beats
    if not math.isfinite(ratio):
        raise ValueError('numero di finestre non rappresentabile')
    if beats_per_km is not None and math.ceil(ratio) < len(distances)*min_windows:
        required = len(distances)*min_windows*window_beats/distance_km
        raise ValueError(f'scala {beats_per_km:g} beat/km insufficiente per i minimi: '
                         f'scegliere almeno {required:.6g} beat/km per questa tappa '
                         'oppure rivedere i minimi o il raggruppamento')
    total = max(math.ceil(ratio), len(distances)*min_windows)
    if not math.isfinite(total*window_beats):
        raise ValueError('durata effettiva non rappresentabile')
    residual = total-len(distances)*min_windows
    # Sottrarre il logaritmo massimo mantiene i pesi fra zero e uno,
    # senza elevare direttamente grandi distanze a grandi esponenti.
    logs = [math.log(d) for d in distances]
    maximum = max(logs)
    weights = [math.exp((value-maximum)*distance_exponent) for value in logs]
    weight_sum = math.fsum(weights)
    quotas = [residual*(weight/weight_sum) for weight in weights]
    floors = [math.floor(q) for q in quotas]
    remainder = residual-sum(floors)
    if not 0 <= remainder <= len(distances):
        raise ValueError('budget troppo grande per una ripartizione numericamente affidabile')
    order = sorted(range(len(distances)), key=lambda i: (-(quotas[i]-floors[i]), i))
    for index in order[:remainder]:
        floors[index] += 1
    spans, cursor = [], 0
    for index, extra in enumerate(floors):
        count = min_windows+extra
        spans.append(TimelineSpan(index, cursor, count))
        cursor += count
    return Timeline(target_beats, window_beats, min_windows, distance_exponent, tuple(spans), beats_per_km)


class TimelineManager:
    """Gestisce una posizione discreta; non legge clock, Live o tempi GPX."""

    def __init__(self, timeline: Timeline):
        if not isinstance(timeline, Timeline):
            raise ValueError('Timeline richiesta dal manager')
        self._timeline = timeline
        self._ends = tuple(span.end_window for span in timeline.spans)
        self._window_index = 0

    @property
    def timeline(self):
        return self._timeline

    @property
    def window_index(self):
        return self._window_index

    @property
    def finished(self):
        return self._window_index == self.timeline.total_windows

    @property
    def current_span(self):
        return None if self.finished else self.timeline.spans[bisect_right(self._ends, self._window_index)]

    def seek_window(self, index: int):
        """Posizionamento esplicito per ispezione o gestione della sessione."""
        if type(index) is not int or not 0 <= index <= self.timeline.total_windows:
            raise ValueError('posizione fuori dalla timeline')
        self._window_index = index

    def advance(self):
        """Consuma una finestra; a fine piano richiede un riposizionamento esplicito."""
        if self.finished:
            raise ValueError('timeline già terminata')
        self._window_index += 1

    def reset(self):
        self._window_index = 0

    def snapshot(self):
        span = self.current_span
        return {'window_index': self._window_index,
                'beat': self._window_index*self.timeline.window_beats,
                'source_index': span.source_index if span else None,
                'remaining_windows': span.end_window-self._window_index if span else 0,
                'finished': self.finished}
