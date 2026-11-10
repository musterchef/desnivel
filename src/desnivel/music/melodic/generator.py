"""Frasi da gradi della scala: motivo articolato o nota sostenuta."""
from __future__ import annotations

import math
from dataclasses import replace

from desnivel.music.patterns import SCALES
from desnivel.music.phrases import Note, Phrase
from desnivel.music.melodic.development import develop
from desnivel.music.texture.generator import TextureGenerator
from desnivel.music.interactions import VoicePlan, GestureSpan
from desnivel.music.rhythm import shape_rhythm, rhythm_influences
from .adaptation import targets

ROLES = ('melody', 'sustained_texture', 'bass_line')
DEFAULTS = dict(octave=0, step_beats=1.0, articulation=.8, velocity=85,
                development=0., activity=.75, phrase_windows=4, seed=0, groove_follow=0.)


class MotifGenerator:
    adapt = staticmethod(targets)
    supported_roles = ROLES
    rhythmic_roles = ('melody', 'bass_line')

    def __init__(self, degrees, settings=None):
        self.degrees = tuple(degrees)
        if not self.degrees or any(type(d) is not int or d < 0 for d in self.degrees):
            raise ValueError('il motivo richiede gradi interi non negativi')
        self.settings = {**DEFAULTS, **(settings or {})}
        self.validate('melody', {})
        self.last_decision = None
        self._development = self._previous_development = None
        self._last_start = None
        self._texture = TextureGenerator(self.degrees[0])

    def validate(self, role, parameters):
        if role not in self.supported_roles:
            raise ValueError('ruolo non supportato dal generatore di motivo')
        values = {**self.settings, **parameters}
        if set(values) != set(DEFAULTS):
            raise ValueError('parametri sconosciuti per il motivo')
        for name in ('step_beats', 'articulation'):
            if not isinstance(values[name], (int, float)) or not math.isfinite(values[name]) or values[name] <= 0:
                raise ValueError(f'{name} deve essere positivo e finito')
        if values['articulation'] > 1:
            raise ValueError('articulation deve essere al massimo 1')
        if type(values['velocity']) is not int or not 1 <= values['velocity'] <= 127:
            raise ValueError('velocity deve essere un intero tra 1 e 127')
        for name in ('development', 'activity', 'groove_follow'):
            if type(values[name]) not in (int, float) or not math.isfinite(values[name]) or not 0 <= values[name] <= 1:
                raise ValueError(f'{name} deve essere in [0, 1]')
        if type(values['phrase_windows']) is not int or not 2 <= values['phrase_windows'] <= 8:
            raise ValueError('phrase_windows deve essere un intero tra 2 e 8')
        if type(values['seed']) is not int or not 0 <= values['seed'] <= 2147483647:
            raise ValueError('seed deve essere un intero tra 0 e 2147483647')
        if type(values['octave']) is not int or not -5 <= values['octave'] <= 5:
            raise ValueError('octave deve essere un intero tra -5 e 5')

    def stage(self, request):
        self.validate(request.role, request.parameters)
        if request.context is None:
            raise ValueError('il motivo richiede tonica e scala')
        values = {**self.settings, **request.parameters}
        if request.role == 'sustained_texture':
            texture = self._texture.stage(replace(request, parameters={
                'octave': values['octave'], 'velocity': values['velocity']}))
            return VoicePlan(texture.phrase, (texture, None, None, request.start), texture.decision, texture.gestures)
        intervals = SCALES[request.context.scale]
        root = request.context.root + 12 * values['octave']
        degrees = self.degrees
        if any(not 0 <= root+intervals[d % len(intervals)]+12*(d//len(intervals)) <= 127 for d in degrees):
            raise ValueError('motivo fuori dal registro MIDI')
        if request.role == 'melody' and values['development'] > 0:
            if not 0 <= root <= 127:
                raise ValueError('lo sviluppo richiede una tonica nel registro MIDI')
            if self._last_start is not None and request.start < self._last_start:
                raise ValueError('lo sviluppo richiede reset prima di una ripartenza precedente')
            previous = self._previous_development if request.start == self._last_start else self._development
            phrase, decision, state = develop(self.degrees, intervals, root, request, values, previous)
            span = GestureSpan(state.period_start, state.period_start+state.period_beats)
            return self._plan(request, values, phrase, decision, span, state, previous)
        decision = {'method': 'literal_motif', 'summary': 'motivo letterale'}
        notes = []
        count = math.ceil(request.length_beats / values['step_beats'])
        if count > 128:
            raise ValueError('il motivo supera 128 note nella finestra')
        offset = math.floor(request.start / values['step_beats'])
        positions = [(i * values['step_beats'], self.degrees[(offset+i) % len(self.degrees)],
                      min(values['step_beats'], request.length_beats-i*values['step_beats']) * values['articulation'])
                     for i in range(count)]
        for beat, degree, duration in positions:
            pitch = root + intervals[degree % len(intervals)] + 12 * (degree // len(intervals))
            notes.append(Note(beat, pitch, duration, values['velocity']))
        return self._plan(request, values, Phrase(request.length_beats, tuple(notes)), decision,
                          GestureSpan(request.start, request.start+request.length_beats))

    def _plan(self, request, values, phrase, decision, span, state=None, previous=None):
        guided = shape_rhythm(phrase, rhythm_influences(request, values['groove_follow']))
        decision['rhythm'] = {'groove_follow': values['groove_follow'],
                              'historical_sources': [r.spec.source for r in request.relations if r.phrase is not None],
                              'moved_attacks': sum(a.beat != b.beat for a, b in zip(phrase.notes, guided.notes))}
        return VoicePlan(guided, (None, state, previous, request.start), decision, (span,))

    def accept(self, plan):
        texture, self._development, self._previous_development, self._last_start = plan.state
        if texture is not None:
            self._texture.accept(texture)
        self.last_decision = plan.decision

    def __call__(self, request):
        plan = self.stage(request)
        self.accept(plan)
        return plan.phrase

    def reset(self):
        """La prima finestra successiva apre un nuovo periodo melodico."""
        self._development = self._previous_development = None
        self._last_start = None
        self.last_decision = None
        self._texture.reset()

    def describe_controls(self, role, parameters):
        """Segnala i controlli senza effetto nel ruolo e nella modalità correnti."""
        values = {**self.settings, **parameters}
        inactive = {}
        if role == 'sustained_texture':
            inactive = {name: 'Nota sostenuta: usa registro e velocity'
                        for name in DEFAULTS if name not in ('octave', 'velocity')}
        elif role != 'melody' or values['development'] == 0:
            inactive = {name: 'Richiede sviluppo melodico attivo'
                        for name in ('activity', 'phrase_windows', 'seed')}
            if role != 'melody':
                inactive['development'] = 'Richiede il ruolo melody'
        return {name: {'inactive_reason': reason} for name, reason in inactive.items()}
