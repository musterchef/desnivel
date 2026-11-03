"""Voci musicali esterne: previsione, note già sostenute e ruolo esplicito."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from desnivel.music.observation import VoiceObservation, observe_phrase
from desnivel.music.phrases import Phrase


@dataclass(frozen=True)
class MusicalSource:
    role: str
    phrase: Phrase | None
    carry_in: int = 0
    unavailable_reason: str | None = None

    def __post_init__(self):
        if not isinstance(self.role, str) or not self.role:
            raise ValueError('ruolo della sorgente richiesto')
        if type(self.carry_in) is not int or not 0 <= self.carry_in <= (len(self.phrase.notes) if self.phrase else 0):
            raise ValueError('numero di note sostenute non valido')
        if self.phrase is None and not self.unavailable_reason:
            raise ValueError('motivo di indisponibilità della sorgente richiesto')
        if self.phrase is not None and self.unavailable_reason is not None:
            raise ValueError('una sorgente disponibile non può avere un errore')
        if self.phrase and any(n.beat != 0 for n in self.phrase.notes[:self.carry_in]):
            raise ValueError('le note già sostenute devono iniziare al confine della finestra')

    def observation(self):
        if self.phrase is None:
            return VoiceObservation(0, None, None, None, 0.)
        return observe_phrase(self.phrase, carry_in=self.carry_in)

    def to_dict(self):
        return dict(role=self.role, available=self.phrase is not None,
                    unavailable_reason=self.unavailable_reason, carry_in=self.carry_in,
                    notes=[asdict(n) for n in self.phrase.notes] if self.phrase else None,
                    observation=asdict(self.observation()))
