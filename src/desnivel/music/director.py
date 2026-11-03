"""Contesto musicale delle sezioni del viaggio."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from desnivel.music.arrangement import Assignment
import math

from desnivel.music.patterns import SCALES


@dataclass(frozen=True)
class MusicalContext:
    section_index: int
    name: str
    root: int
    scale: str


class MusicDirector:
    """Seleziona il contesto armonico dalla progressione del viaggio."""

    def __init__(self, sections):
        sections = tuple(sections)
        starts = [s['from_progress'] for s in sections]
        if (not starts or starts[0] != 0
                or any(not math.isfinite(x) or not 0 <= x < 1 for x in starts)
                or any(a >= b for a, b in zip(starts, starts[1:]))):
            raise ValueError('sezioni ordinate, dalla progressione 0 a meno di 1')
        for section in sections:
            if section['scale'] not in SCALES or type(section['root']) is not int:
                raise ValueError('scala o tonica non valida')
        self._assignments = tuple(MappingProxyType({
            name: Assignment(spec['role'], MappingProxyType(dict(spec.get('parameters', {}))),
                             spec.get('presence', 1.))
            for name, spec in section.get('assignments', {}).items()
        }) for section in sections)
        self._manual_roles = {}
        self._sections = tuple(
            (s['from_progress'], MusicalContext(i, s['name'], s['root'], s['scale']))
            for i, s in enumerate(sections)
        )

    def context_at(self, progress: float) -> MusicalContext:
        if not math.isfinite(progress) or not 0 <= progress <= 1:
            raise ValueError('progress deve essere finito e in [0, 1]')
        return next(context for start, context in reversed(self._sections) if progress >= start)

    def assignments_at(self, progress: float):
        """Restituisce l'organico esplicito della sezione, senza ereditarietà."""
        return MappingProxyType({
            name: Assignment(self._manual_roles.get(name, spec.role), spec.parameters, spec.presence)
            for name, spec in self.section_assignments_at(progress).items()
        })

    def section_assignments_at(self, progress: float):
        """Assegnazioni originali della sezione, prima delle scelte manuali."""
        return self._assignments[self.context_at(progress).section_index]

    def set_role(self, voice: str, role: str | None):
        """Mantiene il ruolo manuale tra sezioni; None ripristina la sezione."""
        if not any(voice in section for section in self._assignments):
            raise ValueError('voce senza assegnazioni nelle sezioni')
        if role is None:
            self._manual_roles.pop(voice, None)
        elif not isinstance(role, str) or not role:
            raise ValueError('ruolo non valido')
        else:
            self._manual_roles[voice] = role

    def manual_role(self, voice: str):
        return self._manual_roles.get(voice)

    def decision_at(self, progress: float, *, external_sources=None):
        """Descrive la selezione configurata, senza attribuirle criteri aggiuntivi."""
        context = self.context_at(progress)
        start = self._sections[context.section_index][0]
        end = self._sections[context.section_index+1][0] if context.section_index+1 < len(self._sections) else 1.
        return {'section': context.name, 'from_progress': start, 'until_progress': end,
                'external_sources': {name: dict(role=source.role, available=source.phrase is not None,
                    unavailable_reason=source.unavailable_reason) for name, source in (external_sources or {}).items()},
                'root': context.root, 'scale': context.scale,
                'assignments': {name: {'role': spec.role, 'presence': spec.presence,
                                      'source': 'manual' if name in self._manual_roles else 'section'}
                                for name, spec in self.assignments_at(progress).items()}}
