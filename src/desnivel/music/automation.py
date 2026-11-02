"""Obiettivi numerici e transizioni dei parametri, senza regole di strumenti."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

from desnivel.music.director import MusicalContext
from desnivel.music.observation import EnsembleObservation


@dataclass(frozen=True)
class AdaptiveContext:
    intensity: float | None = None
    change: float | None = None
    persistence: float | None = None
    unavailable_reason: str | None = None

    def __post_init__(self):
        for value in (self.intensity, self.change, self.persistence):
            if value is not None and (type(value) not in (int, float)
                                      or not math.isfinite(value) or not 0 <= value <= 1):
                raise ValueError('indicazioni musicali adattive richieste tra 0 e 1')


@dataclass(frozen=True)
class AdaptationRequest:
    voice: str
    role: str
    parameters: Mapping
    context: MusicalContext
    intent: AdaptiveContext
    observation: EnsembleObservation
    roles: Mapping[str, str]
    length_beats: float
    manual: Mapping

    def setting(self, name):
        return self.manual.get(name, self.parameters[name])

    def peers(self, role):
        return tuple(value for name, value in self.observation.voices.items()
                     if name != self.voice and self.roles.get(name) == role and value.assigned_beats)


@dataclass(frozen=True)
class ParameterTarget:
    value: float
    reason: str
    transition_beats: float = 16.
    cadence_beats: float = 4.
    integer: bool = False
    deadband: float = .01

    def __post_init__(self):
        if (not all(math.isfinite(x) for x in (self.value, self.transition_beats, self.cadence_beats, self.deadband))
                or self.transition_beats <= 0 or self.cadence_beats <= 0 or self.deadband < 0):
            raise ValueError('obiettivo e tempi di adattamento non validi')


@dataclass(frozen=True)
class ParameterState:
    origin: float
    target: float
    start: float
    duration: float
    slot: int
    scope: tuple
    base: float
    reason: str
    manual: bool = False

    def at(self, beat):
        if self.manual:
            return self.origin
        amount = min(1., max(0., (beat-self.start)/self.duration))
        return self.origin+(self.target-self.origin)*amount


def resolve_parameters(base, targets, manual, previous, *, start, logical_start, scope):
    """Prepara valori e stato; il chiamante li accetta insieme al piano musicale."""
    values, states, decisions = {**base, **manual}, {}, {}
    for name, target in targets.items():
        if name not in base or type(base[name]) not in (int, float):
            raise ValueError(f'obiettivo per parametro numerico sconosciuto: {name}')
        old = previous.get(name)
        current = old.at(start) if old is not None else float(base[name])
        slot = math.floor(logical_start/target.cadence_beats)
        due = old is None or old.manual or old.scope != scope or old.base != base[name] or old.slot != slot
        wanted = (round(target.value) if target.integer else target.value) if due else old.target
        reason = target.reason if due else old.reason
        if old is not None and not old.manual and abs(wanted-old.target) <= target.deadband:
            wanted = old.target
        if name in manual:
            state = ParameterState(float(manual[name]), wanted, start, target.transition_beats,
                                   slot, scope, base[name], reason, True)
            effective = manual[name]
        else:
            changed = old is None or old.manual or wanted != old.target
            state = (ParameterState(current, wanted, start, target.transition_beats,
                                    slot, scope, base[name], reason) if changed else
                     ParameterState(old.origin, old.target, old.start, old.duration,
                                    slot, scope, base[name], reason))
            effective = round(current) if target.integer else current
        if not math.isfinite(effective):
            raise ValueError('valore adattivo non finito')
        values[name], states[name] = effective, state
        decisions[name] = dict(base=base[name], target=wanted, effective=effective,
                               source='manual' if name in manual else 'adaptive', reason=reason,
                               transition_beats=target.transition_beats)
    return values, states, decisions


def bounded(value, low, high):
    return min(high, max(low, value))


def attack_rate(peers):
    rates = [p.attacks_per_beat for p in peers if p.attacks_per_beat is not None]
    return sum(rates) if rates else None
