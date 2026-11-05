"""Sessione musicale multivoce: generatori, assegnazioni e destinazioni fornite dal chiamante."""
from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable, Mapping

from desnivel.music.arrangement import Assignment
from desnivel.music.coordinator import MusicCoordinator, Voice, PlanningRequest
from desnivel.music.director import MusicDirector
from desnivel.music.phrases import Phrase
from desnivel.music.interactions import RhythmRelation


@dataclass(frozen=True)
class Generator:
    generate: Callable[[PlanningRequest], Phrase]
    supported_roles: tuple[str, ...]
    validate: Callable | None = None
    describe: Callable | None = None
    stage: Callable | None = None
    accept: Callable | None = None
    prepare_reference: Callable | None = None
    rhythmic_roles: tuple[str, ...] = ()
    accept_reference: Callable | None = None
    parameter_defaults: Mapping = field(default_factory=dict)
    adapt: Callable | None = None


class EnsembleSession:
    """Carica dati JSON già letti e collega implementazioni fornite dal chiamante.

    Le destinazioni ricevono inizio in beat e frase. Adattamento e trasporto
    sono responsabilità delle funzioni registrate, non del motore musicale.
    """

    def __init__(self, config: dict, generators: Mapping[str, Generator],
                 destinations: Mapping[str, Callable[[float, Phrase], None]]):
        config = deepcopy(config)
        if config['selection_mode'] != 'manual':
            raise ValueError('selection_mode deve essere manual')
        voices = {}
        self._destinations = {}
        self._generators = {}
        for name, spec in config['voices'].items():
            generator = generators[spec['generator']]
            self._generators[name] = generator
            voices[name] = Voice(generator.generate, tuple(spec.get('dependencies', ())),
                                 generator.supported_roles, generator.describe,
                                 tuple(spec.get('optional_dependencies', ())),
                                 generator.stage, generator.accept, generator.prepare_reference,
                                 generator.rhythmic_roles, generator.accept_reference, generator.adapt, generator.validate)
            self._destinations[name] = destinations[spec['destination']]
        self.director = MusicDirector(config['sections'])
        for voice in voices.values():
            optional = voice.optional_dependencies
            if (any(name not in voices for name in optional)
                    or len(set(optional)) != len(optional) or set(optional) & set(voice.dependencies)):
                raise ValueError('dipendenze facoltative sconosciute, duplicate o già obbligatorie')
        self._section_progress = tuple(section['from_progress'] for section in config['sections'])
        # Valida tutte le sezioni prima della prima generazione o trasmissione.
        for section in config['sections']:
            assignments = self.director.assignments_at(section['from_progress'])
            for name, assignment in assignments.items():
                if name not in voices:
                    raise ValueError(f'voce non registrata: {name}')
                if assignment.role not in voices[name].supported_roles:
                    raise ValueError(f'ruolo non supportato: {name}/{assignment.role}')
                if self._generators[name].validate:
                    self._generators[name].validate(assignment.role, assignment.parameters)
            pending, available = set(assignments), set()
            while pending:
                ready = {name for name in pending if (set(voices[name].dependencies)
                         | (set(voices[name].optional_dependencies) & assignments.keys())) <= available}
                if not ready:
                    raise ValueError('dipendenze mancanti o cicliche nella sezione')
                pending -= ready
                available |= ready
        relations = tuple(RhythmRelation.from_dict(data) for data in config.get('relations', []))
        self.coordinator = MusicCoordinator(voices, rhythm_source=config.get('rhythm_voice'),
                                           relations=relations, history_beats=config.get('history_beats', 64.))
        for progress in self._section_progress:
            for name, assignment in self.director.assignments_at(progress).items():
                if assignment.parameters.get('groove_follow', 0) and self.coordinator.rhythm_source is None:
                    raise ValueError('groove_follow richiede rhythm_voice nella configurazione')
        self._manual_parameters = {}
        self._parameter_progress = 0.
        self._presence_multipliers = {}
        self._supported_roles = {name: spec.supported_roles for name, spec in voices.items()}

    @classmethod
    def from_file(cls, path, generators, destinations):
        """Legge una configurazione JSON e collega i componenti registrati."""
        return cls(json.loads(Path(path).read_text()), generators, destinations)

    def plan(self, progress: float, start: float, length_beats: float, *, adaptive_context=None, external_sources=None):
        """Produce le frasi della sezione senza inviarle alle destinazioni."""
        assignments = {
            name: Assignment(spec.role, self.base_parameters_at(name, progress) if adaptive_context is not None
                             else {**self.base_parameters_at(name, progress), **self._manual_parameters.get(name, {})},
                             self.presence_state(name, progress)['effective'])
            for name, spec in self.director.assignments_at(progress).items()
        }
        phrases = self.coordinator.plan(
            start, length_beats, self.director.context_at(progress), assignments=assignments,
            rhythm_parameters=(self.base_parameters_at(self.coordinator.rhythm_source, progress)
                               if adaptive_context is not None else
                               {**self.base_parameters_at(self.coordinator.rhythm_source, progress),
                                **self._manual_parameters.get(self.coordinator.rhythm_source, {})})
            if self.coordinator.rhythm_source is not None else None,
            adaptive_context=adaptive_context, manual_parameters=self._manual_parameters, external_sources=external_sources)
        self._parameter_progress = progress
        return {name: phrase for name, phrase in phrases.items() if name in self._destinations}

    def set_role(self, voice: str, role: str | None):
        """Valida la scelta manuale prima di comunicarla al Director."""
        if voice not in self._supported_roles:
            raise ValueError('voce non registrata')
        if role is not None and role not in self._supported_roles[voice]:
            raise ValueError(f'ruolo non supportato: {voice}/{role}')
        validator = self._generators[voice].validate
        if validator:
            for progress in self._section_progress:
                section = self.director.section_assignments_at(progress)
                if voice in section:
                    spec = section[voice]
                    validator(role or spec.role, {**spec.parameters, **self._manual_parameters.get(voice, {})})
        self.director.set_role(voice, role)

    def role_state(self, voice: str, progress: float):
        """Stato del ruolo per il dispositivo, comprese le voci inattive."""
        if voice not in self._supported_roles:
            raise ValueError('voce non registrata')
        section = self.director.section_assignments_at(progress).get(voice)
        manual = self.director.manual_role(voice)
        return {
            'presence': self.presence_state(voice, progress),
            'supported_roles': list(self._supported_roles[voice]),
            'role_mode': 'manual' if manual is not None else 'section',
            'section_role': section.role if section else None,
            'role': manual if manual is not None else (section.role if section else None),
            'active': section is not None,
            'inactive_reason': None if section else 'not_assigned_to_section',
            'next_entry_progress': next((start for start in self._section_progress
                                         if start > progress and voice in self.director.section_assignments_at(start)), None)
                                   if section is None else None,
        }

    def presence_state(self, voice: str, progress: float):
        """Quota automatica della sezione e moltiplicatore manuale della voce."""
        if voice not in self._generators:
            raise ValueError('voce non registrata')
        assignment = self.director.section_assignments_at(progress).get(voice)
        automatic = assignment.presence if assignment else 0.
        multiplier = self._presence_multipliers.get(voice, 1.)
        return {'automatic': automatic, 'multiplier': multiplier,
                'effective': min(1., automatic * multiplier)}

    def set_presence_multiplier(self, voice: str, value: float):
        if voice not in self._generators:
            raise ValueError('voce non registrata')
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 10:
            raise ValueError('moltiplicatore della presenza richiesto tra 0 e 10')
        self._presence_multipliers[voice] = value

    def base_parameters_at(self, voice: str, progress: float):
        if voice not in self._generators:
            raise ValueError('voce non registrata')
        assignment = self.director.assignments_at(progress).get(voice)
        return {**self._generators[voice].parameter_defaults,
                **(assignment.parameters if assignment else {})}

    def parameters_at(self, voice: str, progress: float, *, beat=None):
        details = self.coordinator.parameter_states_at(voice, beat)
        return {**self.base_parameters_at(voice, progress),
                **{name: state['effective'] for name, state in details.items()},
                **self._manual_parameters.get(voice, {})}

    def manual(self, voice: str, name: str):
        if voice not in self._generators:
            raise ValueError('voce non registrata')
        return name in self._manual_parameters.get(voice, {})

    def set_manual(self, voice: str, name: str, value: bool, *, progress=None, beat=None):
        """Mantiene un parametro o lo restituisce agli assetti delle sezioni."""
        if type(value) is not bool:
            raise ValueError('manual richiede un booleano')
        current = self.manual(voice, name)
        if value and not current:
            progress = self._parameter_progress if progress is None else progress
            self.set_parameter(voice, name, self.parameters_at(voice, progress, beat=beat)[name])
        elif not value:
            parameters = dict(self._manual_parameters.get(voice, {}))
            parameters.pop(name, None)
            self.set_parameters(voice, parameters)

    def set_parameter(self, voice: str, name: str, value):
        """Modifica un solo override, conservando gli altri e i parametri di sezione."""
        self.set_parameters(voice, {**self._manual_parameters.get(voice, {}), name: value})

    def set_parameters(self, voice: str, parameters: Mapping):
        """Modifiche manuali applicate alle prossime frasi, anche tra sezioni."""
        if voice not in self._destinations:
            raise ValueError('voce non registrata')
        if parameters.get('groove_follow', 0) and self.coordinator.rhythm_source is None:
            raise ValueError('groove_follow richiede rhythm_voice nella configurazione')
        validator = self._generators[voice].validate
        if validator:
            for progress in self._section_progress:
                section = self.director.section_assignments_at(progress)
                if voice in section:
                    spec = section[voice]
                    validator(self.director.manual_role(voice) or spec.role, {**spec.parameters, **parameters})
        self._manual_parameters[voice] = deepcopy(dict(parameters))

    def clear_parameters(self, voice: str):
        """Ripristina i parametri delle sezioni per la voce indicata."""
        self._manual_parameters.pop(voice, None)

    def manual_parameters(self, voice: str):
        if voice not in self._generators:
            raise ValueError('voce non registrata')
        return deepcopy(self._manual_parameters.get(voice, {}))

    def send(self, start: float, phrases: Mapping[str, Phrase]):
        """Invia un piano tramite le destinazioni registrate dal chiamante."""
        for name in phrases:
            if name not in self._destinations:
                raise ValueError(f'destinazione non registrata per {name}')
        for name, phrase in phrases.items():
            self._destinations[name](start, phrase)


