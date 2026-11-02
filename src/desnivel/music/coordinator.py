"""Coordinamento delle dipendenze tra voci musicali."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from copy import deepcopy
import math
from types import MappingProxyType
from typing import Callable, Mapping

from desnivel.music.director import MusicalContext
from desnivel.music.arrangement import Assignment
from desnivel.music.phrases import Phrase
from desnivel.music.presence import participates
from desnivel.music.rhythm import PreparedRhythm, RhythmReference
from desnivel.music.interactions import VoicePlan, resolve_relation, record_gestures
from desnivel.music.observation import EnsembleObservation, MusicalMemory


@dataclass(frozen=True)
class PlanningRequest:
    start: float
    length_beats: float
    context: MusicalContext | None
    dependencies: Mapping[str, Phrase]
    role: str | None = None
    parameters: Mapping = field(default_factory=dict)
    logical_start: float | None = None
    epoch: int = 0
    rhythm: RhythmReference | None = None
    relations: tuple = ()
    prepared_material: object = None
    participating: bool = True
    observation: EnsembleObservation | None = None


@dataclass(frozen=True)
class Voice:
    generate: Callable[[PlanningRequest], Phrase]
    dependencies: tuple[str, ...] = ()
    supported_roles: tuple[str, ...] = ()
    describe: Callable[[], dict] | None = None
    optional_dependencies: tuple[str, ...] = ()
    stage: Callable | None = None
    accept: Callable | None = None
    prepare_reference: Callable | None = None
    rhythmic_roles: tuple[str, ...] = ()
    accept_reference: Callable | None = None


class MusicCoordinator:
    """Ordina i generatori secondo le dipendenze e raccoglie le loro frasi.

    Le voci e le frasi sorgente sono identificate dal chiamante. Nessuna
    voce ha un ruolo privilegiato; ogni generatore riceve le sole dipendenze
    dichiarate e lo stesso intervallo e contesto musicale.
    """

    def __init__(self, voices: Mapping[str, Voice], *, rhythm_source=None, relations=(), history_beats=64.):
        self._voices = dict(voices)
        if any((v.stage is None) != (v.accept is None) for v in voices.values()):
            raise ValueError('stage e accept devono essere forniti insieme')
        self.rhythm_source = rhythm_source
        self.relations = tuple(relations)
        if type(history_beats) not in (int, float) or not math.isfinite(history_beats) or history_beats <= 0:
            raise ValueError('history_beats deve essere positivo e finito')
        self.history_beats = history_beats
        if rhythm_source is not None and (rhythm_source not in voices or voices[rhythm_source].prepare_reference is None):
            raise ValueError('produttore del riferimento ritmico sconosciuto o non supportato')
        if len({r.id for r in self.relations}) != len(self.relations):
            raise ValueError('identificativi delle relazioni duplicati')
        for relation in self.relations:
            if relation.source not in voices or relation.target not in voices:
                raise ValueError('sorgente o destinatario della relazione sconosciuti')
            if not voices[relation.target].rhythmic_roles:
                raise ValueError('il destinatario non supporta relazioni ritmiche')
            roles = relation.roles or voices[relation.target].supported_roles
            if set(roles)-set(voices[relation.target].rhythmic_roles):
                raise ValueError('ruolo destinatario non supportato dalla relazione ritmica')
            if relation.lookback_beats > history_beats:
                raise ValueError('history_beats insufficiente per la relazione')
        self._interactive = rhythm_source is not None or bool(self.relations)
        self.epoch = -1
        self.reset()

    def reset(self):
        """Invalida memoria, piani accettati e risposte della sequenza precedente."""
        self.epoch += 1
        self._origin = None
        self._history = []
        self._pending = {}
        self._used = set()
        self._accepted = None
        self._plan_serial = 0
        self.last_plan = None
        self._observations = MusicalMemory()

    @property
    def history(self):
        return tuple(self._history)

    def plan(self, start: float, length_beats: float,
             context: MusicalContext | None = None, *,
             sources: Mapping[str, Phrase] | None = None,
             assignments: Mapping[str, Assignment] | None = None,
             rhythm_parameters: Mapping | None = None) -> dict[str, Phrase]:
        if not math.isfinite(start) or start < 0:
            raise ValueError('start deve essere finito e non negativo')
        if not math.isfinite(length_beats) or length_beats <= 0:
            raise ValueError('length_beats deve essere finita e positiva')
        active = self._voices if assignments is None else {
            name: self._voices[name] for name in assignments if name in self._voices}
        if assignments is not None:
            if set(assignments) - self._voices.keys():
                raise ValueError('voce assegnata non registrata')
            for name, assignment in assignments.items():
                if assignment.role not in active[name].supported_roles:
                    raise ValueError(f'ruolo non supportato dalla voce {name}: {assignment.role}')
        phrases = dict(sources or {})
        if phrases.keys() & active.keys():
            raise ValueError('una voce non può essere anche una sorgente fornita')
        if any(p.length_beats != length_beats for p in phrases.values()):
            raise ValueError('le sorgenti devono coprire la finestra musicale')
        signature = deepcopy((context, {name: (a.role, dict(a.parameters), a.presence)
                                        for name, a in (assignments or {}).items()},
                              dict(sources or {}), dict(rhythm_parameters or {})))
        if self._interactive and self._accepted is not None and start <= self._accepted[0]:
            old_start, old_length, old_signature, result = self._accepted
            if (start, length_beats, signature) != (old_start, old_length, old_signature):
                raise ValueError('intervallo già accettato: reset richiesto prima di ripianificare')
            return dict(result)
        if self._interactive and self._accepted is not None and start < self._accepted[0]+self._accepted[1]:
            raise ValueError('finestre di pianificazione sovrapposte')
        if self._interactive and any(v.stage is None or v.accept is None for v in active.values()):
            raise ValueError('il dialogo richiede generatori con preparazione e accettazione separate')
        # Verifica tutto il grafo prima di chiamare generatori con eventuale stato.
        available = set(phrases)
        pending = dict(active)
        order = []
        while pending:
            ready = [name for name, voice in pending.items()
                     if (set(voice.dependencies) | (set(voice.optional_dependencies) & active.keys())) <= available]
            if not ready:
                raise ValueError('dipendenze mancanti o cicliche tra le voci')
            for name in ready:
                order.append(name)
                available.add(name)
                del pending[name]
        logical_start = start-(self._origin if self._origin is not None else start)
        observation = self._observations.before(start, self._voices)
        prepared = None
        if self.rhythm_source is not None:
            spec = (assignments or {}).get(self.rhythm_source)
            prepared = self._voices[self.rhythm_source].prepare_reference(PlanningRequest(
                start, length_beats, context, MappingProxyType({}),
                spec.role if spec else None,
                MappingProxyType(dict(spec.parameters) if spec else dict(rhythm_parameters or {})),
                logical_start, self.epoch, observation=observation))
            if not isinstance(prepared, PreparedRhythm) or prepared.reference.length_beats != length_beats:
                raise ValueError('il riferimento ritmico deve coprire la finestra')
        resolved = {name: [] for name in active}
        for relation in self.relations:
            role = (assignments or {}).get(relation.target)
            if (relation.target in active and relation.strength
                    and (not relation.roles or role is not None and role.role in relation.roles)):
                resolved[relation.target].append(resolve_relation(
                    relation, self._history, start, length_beats, self._used, self._pending))
        staged, next_pending, next_history = {}, deepcopy(self._pending), list(self._history)
        next_used = set(self._used)
        decisions = {}
        for name in order:
            voice = active[name]
            references = (*voice.dependencies, *(key for key in voice.optional_dependencies if key in phrases))
            dependencies = MappingProxyType({key: phrases[key] for key in references})
            assignment = assignments[name] if assignments is not None else None
            presence = assignment.presence if assignment else 1.
            participating = participates(name, start, presence)
            relation_silence = any(r.gesture is None and r.spec.on_unavailable == 'silence' for r in resolved[name])
            request = PlanningRequest(
                start, length_beats, context, dependencies,
                assignment.role if assignment else None,
                MappingProxyType(dict(assignment.parameters)) if assignment else MappingProxyType({}),
                logical_start if self._interactive else None, self.epoch,
                prepared.reference if prepared else None, tuple(resolved[name]),
                prepared.material if prepared and name == self.rhythm_source else None,
                participating and not relation_silence, observation)
            if voice.stage:
                result = voice.stage(request)
                if not isinstance(result, VoicePlan):
                    raise ValueError('il generatore deve restituire VoicePlan')
                staged[name] = result
                phrase = result.phrase
            else:
                phrase = voice.generate(request)
            if phrase.length_beats != length_beats:
                raise ValueError(f'la voce {name} deve coprire la finestra musicale')
            if not participating:
                phrase = Phrase(length_beats, ())
            if relation_silence:
                phrase = Phrase(length_beats, ())
            phrases[name] = phrase
            decisions[name] = {
                'presence': presence,
                'participating': participating,
                'role': assignment.role if assignment else None,
                'dependencies': list(references),
                'parameters': dict(assignment.parameters) if assignment else {},
                'notes': [asdict(note) for note in phrase.notes],
                'composition': dict(staged[name].decision) if name in staged else dict(voice.describe()) if voice.describe else None,
            }
            if self._interactive:
                if name in staged:
                    record_gestures(next_pending, next_history, name, staged[name].gestures,
                                    phrase, start, self.history_beats)
                decisions[name]['relations'] = [
                    {'id': r.spec.id, 'source': r.spec.source, 'strength': r.spec.strength,
                     'status': 'resolved' if r.gesture else 'unavailable',
                     'unavailable_reason': r.unavailable_reason,
                     'source_span': asdict(r.gesture.span) if r.gesture else None,
                     'on_unavailable': r.spec.on_unavailable} for r in resolved[name]]
                for r in resolved[name]:
                    if r.gesture is not None:
                        next_used.add((r.spec.id, r.gesture.span.start, r.gesture.span.end))
        next_observations = self._observations.accepted(
            start, length_beats, {name: phrases[name] for name in active})
        for name, result in staged.items():
            self._voices[name].accept(result)
        if prepared is not None and self._voices[self.rhythm_source].accept_reference:
            self._voices[self.rhythm_source].accept_reference(prepared)
        self.last_plan = {'start': start, 'length_beats': length_beats,
                          'order': order, 'voices': decisions, 'observation': observation.to_dict()}
        self._observations = next_observations
        if self._interactive:
            self._origin = start-logical_start
            self._plan_serial += 1
            self._history = [g for g in next_history if g.span.end > start-self.history_beats]
            self._pending = {k: v for k, v in next_pending.items() if k[2] > start}
            self._used = {key for key in next_used if key[2] > start-self.history_beats}
            self.last_plan.update(epoch=self.epoch, plan_id=self._plan_serial,
                                  logical_start=logical_start,
                                  rhythm=asdict(prepared.reference) if prepared else None,
                                  history_gestures=len(self._history))
            self._accepted = (start, length_beats, signature, {name: phrases[name] for name in active})
        return {name: phrases[name] for name in active}
