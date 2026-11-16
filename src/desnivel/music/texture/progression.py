"""Progressioni armoniche autonome, indipendenti da sorgenti e destinazioni."""
from __future__ import annotations

from dataclasses import dataclass
import math

from desnivel.music.interactions import GestureSpan, VoicePlan
from desnivel.music.patterns import SCALES
from desnivel.music.phrases import Note, Phrase
from .voicing import diatonic_triad


ROLES = ('harmony',)
DEFAULTS = dict(octave=0, velocity=85, articulation=.9)


@dataclass(frozen=True)
class ProgressionStep:
    degree: int
    beats: float

    def __post_init__(self):
        if type(self.degree) is not int or self.degree < 0:
            raise ValueError('ogni grado della progressione deve essere un intero non negativo')
        if (type(self.beats) not in (int, float) or not math.isfinite(self.beats)
                or self.beats <= 0):
            raise ValueError('la durata di ogni grado deve essere positiva e finita')


@dataclass(frozen=True)
class ProgressionState:
    last_start: float
    last_end: float
    section_index: int
    progression_id: str
    step_index: int
    step_start: float
    step_end: float


def progression_steps(data):
    """Converte i passi serializzabili di una progressione in dati validati."""
    if not isinstance(data, list) or not data:
        raise ValueError('steps richiede una lista non vuota di passi')
    steps = []
    for item in data:
        if not isinstance(item, dict) or set(item) != {'degree', 'beats'}:
            raise ValueError('ogni passo richiede soltanto degree e beats')
        steps.append(ProgressionStep(item['degree'], item['beats']))
    return tuple(steps)


@dataclass(frozen=True)
class HarmonicProgression:
    id: str
    label: str
    steps: tuple[ProgressionStep, ...]


def progression_catalog(data):
    """Valida il catalogo serializzabile selezionato dal controllo della voce."""
    if not isinstance(data, list) or not data:
        raise ValueError('progressions richiede una lista non vuota')
    catalog = []
    for item in data:
        if not isinstance(item, dict) or set(item) != {'id', 'label', 'steps'}:
            raise ValueError('ogni progressione richiede soltanto id, label e steps')
        if not isinstance(item['id'], str) or not item['id']:
            raise ValueError('id della progressione richiesto')
        if not isinstance(item['label'], str) or not item['label']:
            raise ValueError('label della progressione richiesta')
        catalog.append(HarmonicProgression(item['id'], item['label'], progression_steps(item['steps'])))
    if len({progression.id for progression in catalog}) != len(catalog):
        raise ValueError('id della progressione duplicato')
    return tuple(catalog)


class HarmonicProgressionGenerator:
    """Percorre gradi diatonici e realizza triadi con stato accettato a finestre."""
    supported_roles = ROLES

    def __init__(self, progressions, settings=None):
        self.progressions = progression_catalog(progressions)
        self._by_id = {progression.id: progression for progression in self.progressions}
        self.settings = {**DEFAULTS, 'progression': self.progressions[0].id, **(settings or {})}
        self.validate('harmony', {})
        self.reset()

    def validate(self, role, parameters):
        if role not in self.supported_roles:
            raise ValueError('ruolo non supportato dalla progressione armonica')
        values = {**self.settings, **parameters}
        if set(values) != {*DEFAULTS, 'progression'}:
            raise ValueError('parametri sconosciuti per la progressione armonica')
        if type(values['octave']) is not int or not -5 <= values['octave'] <= 5:
            raise ValueError('octave deve essere un intero tra -5 e 5')
        if type(values['velocity']) is not int or not 1 <= values['velocity'] <= 127:
            raise ValueError('velocity deve essere un intero tra 1 e 127')
        if (type(values['articulation']) not in (int, float)
                or not math.isfinite(values['articulation']) or not .05 <= values['articulation'] <= 1):
            raise ValueError('articulation deve essere finita e in [0.05, 1]')
        if values['progression'] not in self._by_id:
            raise ValueError('progressione sconosciuta')
        return values

    def reset(self):
        self._state = None
        self._previous_state = None
        self.last_decision = None

    def _initial_state(self, request, progression):
        first = progression.steps[0]
        return ProgressionState(request.start, request.start, request.context.section_index, progression.id, 0,
                                request.start, request.start+first.beats)

    def _state_for(self, request, progression):
        state = self._state
        if state is not None and request.start == state.last_start:
            if (progression.id != state.progression_id
                    or request.context.section_index != state.section_index):
                return self._initial_state(request, progression)
            return self._previous_state or self._initial_state(request, progression)
        if (state is None or request.start != state.last_end or request.context.section_index != state.section_index
                or progression.id != state.progression_id):
            if state is not None and request.start < state.last_end:
                raise ValueError('la progressione richiede reset prima di una ripartenza precedente')
            return self._initial_state(request, progression)
        return state

    def stage(self, request):
        values = self.validate(request.role, request.parameters)
        if request.context is None:
            raise ValueError('la progressione armonica richiede tonica e scala')
        progression = self._by_id[values['progression']]
        state = self._state_for(request, progression)
        intervals = SCALES[request.context.scale]
        cursor, end = request.start, request.start+request.length_beats
        index, step_start, step_end = state.step_index, state.step_start, state.step_end
        notes, chords, gestures = [], [], []
        while cursor < end:
            step = progression.steps[index]
            part_end = min(step_end, end)
            pitches = diatonic_triad(request.context.root, intervals, step.degree, values['octave'])
            duration = (part_end-cursor)*values['articulation']
            relative = cursor-request.start
            notes.extend(Note(relative, pitch, duration, values['velocity']) for pitch in pitches)
            chords.append({'beat': relative, 'degree': step.degree, 'pitches': list(pitches)})
            gestures.append(GestureSpan(step_start, step_end))
            cursor = part_end
            if cursor >= step_end:
                index = (index+1) % len(progression.steps)
                step_start, step_end = step_end, step_end+progression.steps[index].beats
        next_state = ProgressionState(request.start, end, request.context.section_index, progression.id,
                                      index, step_start, step_end)
        decision = {'method': 'harmonic_progression', 'steps': [
            {'degree': step.degree, 'beats': step.beats} for step in progression.steps
        ], 'progression': progression.id, 'chords': chords, 'section_index': request.context.section_index,
                    'summary': progression.label}
        return VoicePlan(Phrase(request.length_beats, tuple(notes)), next_state, decision,
                         tuple(dict.fromkeys(gestures)))

    def accept(self, plan):
        self._previous_state = self._state
        self._state = plan.state
        self.last_decision = plan.decision

    def __call__(self, request):
        plan = self.stage(request)
        self.accept(plan)
        return plan.phrase
