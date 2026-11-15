"""Gesti effettivi e riferimenti storici per il dialogo ritmico."""
from __future__ import annotations
from dataclasses import dataclass, field
import math

from desnivel.music.phrases import Note, Phrase


@dataclass(frozen=True)
class GestureSpan:
    start: float
    end: float

    def __post_init__(self):
        if not math.isfinite(self.start) or not math.isfinite(self.end) or not 0 <= self.start < self.end:
            raise ValueError('intervallo del gesto non valido')


@dataclass(frozen=True)
class VoicePlan:
    phrase: Phrase
    state: object = None
    decision: dict = field(default_factory=dict)
    gestures: tuple[GestureSpan, ...] = ()


@dataclass(frozen=True)
class Gesture:
    voice: str
    span: GestureSpan
    phrase: Phrase


@dataclass(frozen=True)
class RhythmRelation:
    id: str
    source: str
    target: str
    lookback_beats: float
    fragment_beats: float
    strength: float
    on_unavailable: str = 'independent'
    roles: tuple[str, ...] = ()

    def __post_init__(self):
        if any(not isinstance(v, str) or not v for v in (self.id, self.source, self.target)):
            raise ValueError('identificativi di relazione e voci richiesti')
        if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0
               for v in (self.lookback_beats, self.fragment_beats)):
            raise ValueError('limiti temporali della relazione positivi e finiti richiesti')
        if type(self.strength) not in (int, float) or not math.isfinite(self.strength) or not 0 <= self.strength <= 1:
            raise ValueError('influenza della relazione richiesta in [0, 1]')
        if self.on_unavailable not in ('independent', 'silence', 'error'):
            raise ValueError('politica di indisponibilità sconosciuta')
        if len(set(self.roles)) != len(self.roles) or any(not isinstance(r, str) or not r for r in self.roles):
            raise ValueError('ruoli della relazione non validi')

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or data.get('scope') != 'history' or data.get('aspects') != ['rhythm']:
            raise ValueError('sono supportate relazioni history sul solo aspetto rhythm')
        allowed = {'id', 'source', 'target', 'scope', 'aspects', 'lookback_beats',
                   'fragment_beats', 'strength', 'on_unavailable', 'roles'}
        if data.keys()-allowed:
            raise ValueError('campi o trasformazioni della relazione non supportati')
        values = {k: v for k, v in data.items() if k not in ('scope', 'aspects')}
        if 'roles' in values:
            if not isinstance(values['roles'], list):
                raise ValueError('roles deve essere una lista')
            values['roles'] = tuple(values['roles'])
        try:
            return cls(**values)
        except TypeError as error:
            raise ValueError('campi obbligatori della relazione mancanti') from error


@dataclass(frozen=True)
class ResolvedRhythmRelation:
    spec: RhythmRelation
    gesture: Gesture | None
    phrase: Phrase | None
    unavailable_reason: str | None = None


def resolve_relation(spec, history, start, length, used, pending=None):
    if spec.fragment_beats > length:
        raise ValueError(f'{spec.id}: il frammento supera la finestra di destinazione')
    complete = [g for g in history if g.voice == spec.source and g.span.end <= start
                and g.span.start >= start-spec.lookback_beats]
    sounding = [g for g in complete if g.phrase.notes]
    candidates = [g for g in sounding if (spec.id, g.span.start, g.span.end) not in used]
    gesture = max(candidates, key=lambda g: g.span.end, default=None)
    reason = None
    if gesture is None:
        incomplete = any(v == spec.source and start-spec.lookback_beats <= a < start
                         for v, a, _ in (pending or {}))
        reason = 'consumed' if sounding else 'silent' if complete else 'incomplete' if incomplete else 'missing'
    else:
        offset = max(0., gesture.phrase.length_beats-spec.fragment_beats)
        notes = tuple(Note(n.beat-offset, n.pitch, n.duration, n.velocity)
                      for n in gesture.phrase.notes if offset <= n.beat < offset+spec.fragment_beats)
        if notes:
            return ResolvedRhythmRelation(spec, gesture, Phrase(length, notes))
        reason = 'empty_fragment'
    if spec.on_unavailable == 'error':
        raise ValueError(f'{spec.id}: nessun gesto completo disponibile ({reason})')
    return ResolvedRhythmRelation(spec, None, None, reason)


def record_gestures(pending, history, voice, spans, phrase, start, limit):
    """Aggiorna copie di lavoro; un gesto diventa storico solo a copertura completa."""
    for span in spans:
        if span.end-span.start > limit:
            raise ValueError(f'{voice}: il gesto supera history_beats')
        low, high = max(start, span.start), min(start+phrase.length_beats, span.end)
        if low >= high:
            raise ValueError('il gesto dichiarato non interseca la frase')
        key = (voice, span.start, span.end)
        parts = pending.setdefault(key, [])
        notes = []
        span_length = span.end-span.start
        offset = start-span.start
        for note in phrase.notes:
            absolute = start+note.beat
            if span.start <= absolute < span.end:
                if absolute+note.duration > span.end:
                    raise ValueError('una nota attraversa il confine del gesto')
                beat = offset+note.beat
                duration = min(note.duration, span_length-beat)
                if beat+duration > span_length:
                    duration = math.nextafter(duration, 0.)
                notes.append(Note(beat, note.pitch, duration, note.velocity))
        parts.append((low, high, tuple(notes)))
        cursor = span.start
        for a, b, _ in sorted(parts):
            if a != cursor:
                break
            cursor = b
        if cursor == span.end:
            material = tuple(sorted((n for _, _, part in parts for n in part), key=lambda n: (n.beat, n.pitch)))
            history.append(Gesture(voice, span, Phrase(span.end-span.start, material)))
            del pending[key]
