"""Ingresso del generatore di accompagnamento nel coordinamento multivoce."""
from dataclasses import replace
import math

from desnivel.music.bass.generator import BassSettings, plan_bass
from desnivel.music.phrases import Note, Phrase
from desnivel.music.interactions import VoicePlan, GestureSpan
from desnivel.music.rhythm import shape_rhythm, rhythm_influences
from .adaptation import targets


class BassVoice:
    def adapt(self, request):
        return targets(request, self.validate(request.role, {**request.parameters, **request.manual}), self.last_decision)

    def __init__(self, settings=None):
        values = dict(settings or {})
        self.groove_follow = values.pop('groove_follow', 0.)
        self.settings = BassSettings(**values)
        self.validate('bass_line', {})
        self.previous = None
        self.previous_end = None
        self.last_decision = None

    def validate(self, role, parameters):
        if role != 'bass_line':
            raise ValueError('ruolo non supportato dal generatore di accompagnamento')
        if 'strategy' in parameters:
            raise ValueError('strategy seleziona i valori iniziali: usarlo soltanto in settings')
        values = dict(parameters)
        amount = values.pop('groove_follow', self.groove_follow)
        if type(amount) not in (int, float) or not math.isfinite(amount) or not 0 <= amount <= 1:
            raise ValueError('groove_follow deve essere in [0, 1]')
        return replace(self.settings, **values)

    def stage(self, request):
        settings = self.validate(request.role, request.parameters)
        if len(request.dependencies) != 1:
            raise ValueError('l’accompagnamento richiede una sola frase di riferimento')
        source = next(iter(request.dependencies.values()))
        last = self.previous if self.previous_end == request.start else None
        amount = request.parameters.get('groove_follow', self.groove_follow)
        independent = not source.notes and amount > 0
        if independent:
            if request.context is None:
                raise ValueError('il basso autonomo richiede un contesto armonico')
            # Materiale proprio: appoggio della tonica nel registro configurato.
            candidates = [p for p in range(settings.lowest, settings.highest+1)
                          if p % 12 == request.context.root % 12]
            center = last if last is not None else (settings.lowest+settings.highest)/2
            pitch = min(candidates, key=lambda p: (abs(p-center), p))
            source = Phrase(request.length_beats, (Note(0, pitch, request.length_beats, 85),))
        result, density = plan_bass(source, settings, last,
                                    phrase_index=round(request.start / request.length_beats))
        guided = shape_rhythm(result, rhythm_influences(request, amount))
        decision = {'method': 'responsive_line', 'material_source': 'section' if independent else 'dependency',
                    'participating': request.participating,
                    'groove_follow': amount,
                    'historical_sources': [r.spec.source for r in request.relations if r.phrase is not None],
                    'moved_attacks': sum(a.beat != b.beat for a, b in zip(result.notes, guided.notes)),
                    'density': density,
                    'summary': 'appoggio di sezione' if independent else 'accompagnamento della sorgente'}
        state = (guided.notes[-1].pitch if guided.notes else None, request.start+request.length_beats)
        return VoicePlan(guided, state, decision, (GestureSpan(request.start, request.start+request.length_beats),))

    def accept(self, plan):
        self.previous, self.previous_end = plan.state
        self.last_decision = plan.decision

    def __call__(self, request):
        plan = self.stage(request)
        self.accept(plan)
        return plan.phrase

    def reset(self):
        self.previous = self.previous_end = None
        self.last_decision = None

    def describe_controls(self, role, parameters):
        detail = {'label': 'densità richiesta',
                  'description': 'attacchi desiderati per beat, limitati da candidati e spaziatura; il riepilogo riguarda l’ultimo piano accettato'}
        density = self.last_decision.get('density') if self.last_decision else None
        if self.last_decision and not self.last_decision['participating']:
            detail['value_hint'] = 'voce non partecipante'
        elif density and density['capacity_attacks'] is not None:
            detail['value_hint'] = (f"{density['selected_attacks']}/{density['capacity_attacks']} attacchi"
                                    + (' · saturo' if density['saturated'] else ''))
            detail['description'] += (f"; densità richiesta {density['requested']:g}, "
                                       f"{density['active_beats']:g} beat disponibili")
        return {'density': detail}
