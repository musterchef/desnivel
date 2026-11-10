"""Ripetizione di pattern ritmici configurati, indipendente da device e trasporto."""
from __future__ import annotations

from copy import deepcopy
import math

from desnivel.music.phrases import Note, Phrase
from desnivel.music.interactions import VoicePlan, GestureSpan


DEFAULTS = {'pattern': 0, 'velocity_ratio': 1., 'gate_beats': .1}
ROLES = ('percussion',)


class PercussionGenerator:
    supported_roles = ROLES

    def __init__(self, lanes, patterns, settings=None):
        if settings is not None and not isinstance(settings, dict):
            raise ValueError('settings deve essere una mappa di parametri')
        if (not isinstance(lanes, dict) or not lanes
                or any(not isinstance(name, str) or not name for name in lanes)
                or any(type(pitch) is not int or not 0 <= pitch <= 127 for pitch in lanes.values())
                or len(set(lanes.values())) != len(lanes)):
            raise ValueError('lanes richiede nomi distinti e altezze MIDI distinte tra 0 e 127')
        if not isinstance(patterns, list) or not patterns:
            raise ValueError('almeno un pattern percussivo richiesto')
        self.patterns = []
        names = set()
        for pattern in patterns:
            if not isinstance(pattern, dict) or set(pattern) != {'name', 'length_beats', 'hits'}:
                raise ValueError('ogni pattern richiede name, length_beats e hits')
            name, length = pattern['name'], pattern['length_beats']
            if not isinstance(name, str) or not name or name in names:
                raise ValueError('nomi di pattern non vuoti e distinti richiesti')
            names.add(name)
            if type(length) not in (int, float) or not math.isfinite(length) or length <= 0:
                raise ValueError('lunghezza del pattern positiva e finita richiesta')
            if not isinstance(pattern['hits'], list) or len(pattern['hits']) > 128:
                raise ValueError('hits deve essere una lista con al massimo 128 attacchi')
            hits, occupied = [], set()
            for hit in pattern['hits']:
                if not isinstance(hit, dict) or set(hit) != {'beat', 'lane', 'velocity'}:
                    raise ValueError('ogni attacco richiede beat, lane e velocity')
                beat, lane, velocity = hit['beat'], hit['lane'], hit['velocity']
                if (type(beat) not in (int, float) or not math.isfinite(beat) or not 0 <= beat < length
                        or not isinstance(lane, str) or lane not in lanes
                        or type(velocity) is not int or not 1 <= velocity <= 127):
                    raise ValueError('attacco percussivo non valido')
                key = (beat, lanes[lane])
                if key in occupied:
                    raise ValueError('attacchi duplicati sulla stessa altezza MIDI')
                occupied.add(key)
                hits.append((beat, lanes[lane], velocity))
            self.patterns.append((name, length, tuple(sorted(hits))))
        self.settings = {**DEFAULTS, **deepcopy(settings or {})}
        self.validate('percussion', {})
        self.last_decision = None

    def validate(self, role, parameters):
        if role not in self.supported_roles:
            raise ValueError('ruolo non supportato dal generatore percussivo')
        values = {**self.settings, **parameters}
        if set(values) != set(DEFAULTS):
            raise ValueError('parametri percussivi sconosciuti')
        if type(values['pattern']) is not int or not 0 <= values['pattern'] < len(self.patterns):
            raise ValueError('indice di pattern fuori intervallo')
        for name in ('velocity_ratio', 'gate_beats'):
            value = values[name]
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 1:
                raise ValueError(f'{name} deve essere in (0, 1]')
        return values

    def stage(self, request):
        values = self.validate(request.role, request.parameters)
        start, length = request.start, request.length_beats
        if (not math.isfinite(start) or start < 0 or not math.isfinite(length) or length <= 0):
            raise ValueError('inizio non negativo e lunghezza positiva richiesti')
        end = start+length
        if not math.isfinite(end) or end <= start:
            raise ValueError('finestra percussiva non rappresentabile alla posizione richiesta')
        name, cycle, hits = self.patterns[values['pattern']]
        events = []
        # Per ogni attacco ricava soltanto le ripetizioni comprese nella frase.
        # La fase è ancorata al beat zero: non riparte a ogni richiesta.
        for offset, pitch, velocity in hits:
            repetition = max(0, math.ceil((start-offset)/cycle))
            absolute = offset + repetition*cycle
            while absolute < end:
                if len(events) >= 128:
                    raise ValueError('il pattern supera 128 attacchi nella finestra')
                events.append((absolute-start, pitch, velocity))
                repetition += 1
                following = offset + repetition*cycle
                if following <= absolute:
                    raise ValueError('periodo percussivo non rappresentabile alla posizione richiesta')
                absolute = following
        events.sort()
        notes, next_attack = [], {}
        for beat, pitch, velocity in reversed(events):
            duration = min(values['gate_beats'], length-beat, next_attack.get(pitch, length)-beat)
            notes.append(Note(beat, pitch, duration, max(1, min(127, round(velocity*values['velocity_ratio'])))))
            next_attack[pitch] = beat
        decision = {'method': 'percussion_pattern', 'pattern': name,
                              'summary': f'pattern {name} · {len(notes)} attacchi'}
        spans = tuple(GestureSpan(i*cycle, (i+1)*cycle)
                      for i in range(math.floor(start/cycle), math.ceil(end/cycle)))
        return VoicePlan(Phrase(length, tuple(reversed(notes))), decision=decision, gestures=spans)

    def accept(self, plan):
        self.last_decision = plan.decision

    def __call__(self, request):
        plan = self.stage(request)
        self.accept(plan)
        return plan.phrase
