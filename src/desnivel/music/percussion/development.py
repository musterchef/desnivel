"""Sviluppo di un materiale percussivo lungo richieste musicali consecutive."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import math
import random

from desnivel.music.phrases import Note, Phrase
from .generator import PercussionGenerator, ROLES
from desnivel.music.interactions import VoicePlan, GestureSpan
from desnivel.music.rhythm import PreparedRhythm, RhythmReference
from .catalog import STYLE_BY_ID, STYLE_ROLES
from .styles import StyleMaterial, transition_for, transition_events
from .adaptation import targets


DEFAULTS = {'style': 'none', 'transition_beats': 16., 'variation': .7, 'displacement_beats': .25, 'velocity_ratio': .85,
            'gate_beats': .1, 'seed': 7, 'support_tolerance_beats': .5, 'answer_clearance_beats': .25}
OPERATIONS = {'statement', 'subtract', 'displace', 'accent', 'silence'}


class PercussionPhraseGenerator:
    def adapt(self, request):
        style = request.setting('style')
        cycle = STYLE_BY_ID[style].cycle_beats if style != 'none' else self.standard[1] if self.standard else self.cycle
        return targets(request, cycle)

    def __init__(self, lanes, material, anchor_beats, development, interaction, settings=None, *,
                 standard_material=None):
        # Riutilizza la validazione dei materiali espliciti e della mappa MIDI.
        parsed = PercussionGenerator(lanes, [material])
        self.name, self.cycle, self.hits = parsed.patterns[0]
        self.standard = (PercussionGenerator(lanes, [standard_material]).patterns[0]
                         if standard_material is not None else None)
        if (not isinstance(anchor_beats, list) or not anchor_beats
                or any(type(b) not in (int, float) or not math.isfinite(b) for b in anchor_beats)
                or len(set(anchor_beats)) != len(anchor_beats)
                or not set(anchor_beats) <= {hit[0] for hit in self.hits}):
            raise ValueError('anchor_beats deve indicare attacchi distinti presenti nel materiale')
        self.anchors = frozenset(anchor_beats)
        if (not isinstance(development, list) or not development
                or any(not isinstance(op, str) or op not in OPERATIONS for op in development)
                or development[0] != 'statement'):
            raise ValueError('development deve iniziare con statement e contenere operazioni supportate')
        self.development = tuple(development)
        fields = {'support_source', 'support_lanes', 'answer_source', 'answer_lanes'}
        if not isinstance(interaction, dict) or set(interaction) != fields:
            raise ValueError('interaction richiede sorgenti e canali di sostegno e risposta')
        if any(not isinstance(interaction[k], str) or not interaction[k] for k in ('support_source', 'answer_source')):
            raise ValueError('nomi delle sorgenti di interazione non vuoti richiesti')
        support = interaction['support_lanes']
        answers = interaction['answer_lanes']
        if (not isinstance(support, list) or not support or not isinstance(answers, list) or not answers
                or any(not isinstance(lane, str) or lane not in lanes for lane in support+answers)
                or len(set(support+answers)) != len(support+answers)
                or set(support+answers) != set(lanes)):
            raise ValueError('ogni canale deve essere assegnato una volta al sostegno o alla risposta')
        self.interaction = deepcopy(interaction)
        self.support_pitches = frozenset(lanes[lane] for lane in support)
        self.style_lanes = {role: lanes[role] for role in STYLE_ROLES} if set(STYLE_ROLES) <= lanes.keys() else None
        if settings is not None and not isinstance(settings, dict):
            raise ValueError('settings deve essere una mappa di parametri')
        self.settings = {**DEFAULTS, **deepcopy(settings or {})}
        self.validate('percussion', {})
        self.reset()

    def reset(self):
        self.position = 0.
        self.last_start = None
        self.last_position = 0.
        self.last_decision = None
        self.style_transition = None

    def describe_controls(self, role, parameters):
        """Disponibilità dei controlli secondo materiali e trasformazioni configurati."""
        values = {**self.settings, **parameters}
        details = {'transition_beats': {'label': 'Transizione (beat)'}, 'variation': {'label': 'Variazione'}, 'style': {'label': 'Stile'}}
        if values['style'] == 'none':
            details['transition_beats']['inactive_reason'] = 'Richiede uno stile selezionato'
        if self.style_lanes is None:
            details['style']['inactive_reason'] = 'Richiede i ruoli kick, snare e hat nella mappa'
        if values['variation'] == 0:
            for name in ('displacement_beats', 'support_tolerance_beats', 'answer_clearance_beats', 'seed'):
                details[name] = {'inactive_reason': 'Figura base: nessuno sviluppo o interazione'}
        elif 'displace' not in self.development:
            details['displacement_beats'] = {'inactive_reason': 'Richiede trasformazione displace attiva'}
        if (values['style'] != 'none' and self.style_lanes is not None
                and all(self.style_lanes[r] not in self.support_pitches for r in ('snare', 'hat'))):
            details['support_tolerance_beats'] = {'inactive_reason': 'Lo stile conserva i sostegni strutturali'}
        return details

    def validate(self, role, parameters):
        if role not in ROLES:
            raise ValueError('ruolo non supportato dal generatore percussivo')
        values = {**self.settings, **parameters}
        if set(values) != set(DEFAULTS):
            raise ValueError('parametri percussivi sconosciuti')
        if not isinstance(values['style'], str) or values['style'] not in ('none', *STYLE_BY_ID):
            raise ValueError('stile percussivo sconosciuto')
        if values['style'] != 'none' and self.style_lanes is None:
            raise ValueError('ruoli kick, snare e hat richiesti per selezionare uno stile')
        for key in ('variation', 'displacement_beats', 'velocity_ratio', 'gate_beats',
                    'support_tolerance_beats', 'answer_clearance_beats'):
            value = values[key]
            if (type(value) not in (int, float) or not math.isfinite(value)
                    or not 0 <= value <= 1 or (key in ('velocity_ratio', 'gate_beats') and value == 0)):
                raise ValueError(f'{key} fuori intervallo')
        if (type(values['transition_beats']) not in (int, float) or not math.isfinite(values['transition_beats'])
                or not 0 <= values['transition_beats'] <= 128):
            raise ValueError('transition_beats deve essere tra 0 e 128')
        if type(values['seed']) is not int or not 0 <= values['seed'] <= 2147483647:
            raise ValueError('seed deve essere un intero tra 0 e 2147483647')
        return values

    def _cycle(self, index, values):
        operation = self.development[index % len(self.development)] if values['variation'] else 'statement'
        # Candidato completo: Variazione decide poi quanto ammetterne nel risultato.
        if operation == 'silence':
            return operation, ()
        rng = random.Random((values['seed'] << 32)+index)
        direction = rng.choice((-1, 1))
        events = {}
        # Gli attacchi protetti hanno precedenza in caso di coincidenza.
        for beat, pitch, velocity in sorted(self.hits, key=lambda hit: hit[0] not in self.anchors):
            if beat not in self.anchors:
                if operation == 'subtract':
                    continue
                if operation == 'displace':
                    beat = (beat+direction*values['displacement_beats']) % self.cycle
                if operation == 'accent':
                    velocity = max(1, min(127, velocity+direction*64))
            events.setdefault((beat, pitch), velocity)
        return operation, tuple((b, p, v) for (b, p), v in sorted(events.items()))

    def _interact(self, events, dependencies, values):
        definition = self.interaction
        answer_name, support_name = definition['answer_source'], definition['support_source']
        if answer_name not in dependencies:
            raise ValueError(f'frase di riferimento richiesta: {answer_name}')
        support = dependencies.get(support_name)
        attacks = support.notes if support is not None else ()
        foreground = dependencies[answer_name].notes
        result, supported, omitted = {}, 0, 0
        for beat, pitch, velocity in events:
            if pitch in self.support_pitches:
                if not attacks:
                    continue
                nearest = min(attacks, key=lambda n: (abs(n.beat-beat), -n.velocity, n.beat))
                if abs(nearest.beat-beat) > values['support_tolerance_beats']:
                    continue
                beat = nearest.beat
                velocity = round((velocity+nearest.velocity)/2)
                supported += 1
            elif (not foreground or any(abs(n.beat-beat) < values['answer_clearance_beats'] for n in foreground)):
                omitted += 1
                continue
            key = (beat, pitch)
            result[key] = max(result.get(key, 0), velocity)
        trace = {'support_source': support_name, 'answer_source': answer_name,
                 'available_sources': list(dependencies), 'supported_hits': supported,
                 'omitted_answer_hits': omitted, 'support_available': support is not None}
        return [(beat, pitch, velocity) for (beat, pitch), velocity in sorted(result.items())], trace

    def _standard_events(self, start, end):
        _, cycle, hits = self.standard if self.standard is not None else (self.name, self.cycle, self.hits)
        events = []
        for offset, pitch, velocity in hits:
            repetition = max(0, math.ceil((start-offset)/cycle))
            while offset+repetition*cycle < end:
                if len(events) >= 128:
                    raise ValueError('il groove standard supera 128 attacchi nella finestra')
                events.append((offset+repetition*cycle-start, pitch, velocity))
                repetition += 1
        return events

    def _vary(self, standard, developed_events, start, values):
        """Scelta coerente per ciclo e canale, riproducibile anche fra finestre."""
        amount = values['variation']
        cycle = (STYLE_BY_ID[values['style']].cycle_beats if values['style'] != 'none' else self.cycle)
        regular = {(beat, pitch): velocity for beat, pitch, velocity in standard}
        developed = {(beat, pitch): velocity for beat, pitch, velocity in developed_events}
        result = []
        for beat, pitch in sorted(regular.keys() | developed.keys()):
            if (beat, pitch) in regular and (beat, pitch) in developed:
                velocity = round(regular[beat, pitch]*(1-amount)+developed[beat, pitch]*amount)
            else:
                rng = random.Random(f'{values["seed"]}:{math.floor((start+beat)/cycle)}:{pitch}')
                source = developed if rng.random() < amount else regular
                velocity = source.get((beat, pitch))
            if velocity is not None:
                result.append((beat, pitch, velocity))
        return result

    def prepare_reference(self, request):
        """Prepara gli appoggi senza leggere le altre voci o avanzare il periodo."""
        values = self.validate('percussion', request.parameters)
        start = request.logical_start
        if start is None:
            raise ValueError('il riferimento richiede una posizione musicale logica')
        if values['style'] != 'none':
            style = STYLE_BY_ID[values['style']]
            transition = transition_for(self.style_transition, style.id, start, values['transition_beats'],
                                        values['seed'], values['variation'])
            # Conserva il ciclo completo per trasformazioni indipendenti dai tagli di finestra.
            low = math.floor(start/style.cycle_beats)*style.cycle_beats
            high = math.ceil((start+request.length_beats)/style.cycle_beats)*style.cycle_beats
            events = transition_events(transition, self.style_lanes, low, high, values['seed'], values['variation'])
            if sum(start <= event[0] < start+request.length_beats for event in events) > 128:
                raise ValueError('il riferimento supera 128 attacchi')
            points = {}
            for beat, _, velocity, _, _ in events:
                if start <= beat < start+request.length_beats:
                    points[beat-start] = max(points.get(beat-start, 0), velocity/127)
            return PreparedRhythm(RhythmReference(request.length_beats, style.cycle_beats,
                                                  start % style.cycle_beats, tuple(sorted(points.items()))),
                                  StyleMaterial(events, transition))
        _, cycle, hits = self.standard if self.standard is not None else (self.name, self.cycle, self.hits)
        events = []
        for offset, pitch, velocity in hits:
            repetition = max(0, math.ceil((start-offset)/cycle))
            while offset+repetition*cycle < start+request.length_beats:
                if len(events) >= 128:
                    raise ValueError('il riferimento supera 128 attacchi')
                events.append((offset+repetition*cycle-start, pitch, velocity))
                repetition += 1
        points = {}
        for beat, _, velocity in events:
            points[beat] = max(points.get(beat, 0), velocity/127)
        structural = tuple(sorted(event for event in events if event[1] in self.support_pitches))
        reference = RhythmReference(request.length_beats, cycle, start % cycle, tuple(sorted(points.items())))
        return PreparedRhythm(reference, structural)

    def stage(self, request):
        values = self.validate(request.role, request.parameters)
        if (not math.isfinite(request.start) or request.start < 0
                or not math.isfinite(request.length_beats) or request.length_beats <= 0):
            raise ValueError('inizio non negativo e lunghezza positiva richiesti')
        # Ripianificare lo stesso inizio non consuma due volte il materiale.
        start = (request.logical_start if request.prepared_material is not None else
                 self.last_position if request.start == self.last_start else self.position)
        end = start+request.length_beats
        if not math.isfinite(end) or end <= start:
            raise ValueError('finestra percussiva non rappresentabile')
        if values['style'] != 'none':
            return self._style_plan(request, values, start, end)
        first, last = math.floor(start/self.cycle), math.ceil(end/self.cycle)
        if last-first > 128:
            raise ValueError('la richiesta supera 128 cicli percussivi')
        events, operations = [], []
        for index in range(first, last):
            operation, hits = self._cycle(index, values)
            operations.append({'cycle': index, 'operation': operation})
            for beat, pitch, velocity in hits:
                absolute = index*self.cycle+beat
                if start <= absolute < end:
                    events.append((absolute-start, pitch, velocity))
        if len(events) > 128:
            raise ValueError('lo sviluppo supera 128 attacchi nella finestra')
        interaction = {'support_source': self.interaction['support_source'],
                       'answer_source': self.interaction['answer_source'],
                       'available_sources': list(request.dependencies), 'supported_hits': 0,
                       'omitted_answer_hits': 0, 'support_available': self.interaction['support_source'] in request.dependencies}
        if values['variation']:
            events, interaction = self._interact(events, request.dependencies, values)
        if values['variation'] < 1:
            standard = self._standard_events(start, end)
            events = (self._vary(standard, events, start, values) if values['variation'] else sorted(standard))
        structural = []
        if request.prepared_material is not None:
            for beat, pitch, velocity in request.prepared_material:
                operation = self._cycle(math.floor((start+beat)/self.cycle), values)[0]
                if values['variation'] == 0 or operation != 'silence':
                    structural.append((beat, pitch, velocity))
            merged = {(b, p): v for b, p, v in events}
            for beat, pitch, velocity in structural:
                merged[beat, pitch] = max(merged.get((beat, pitch), 0), velocity)
            events = [(b, p, v) for (b, p), v in sorted(merged.items())]
        if len(events) > 128:
            raise ValueError('la combinazione supera 128 attacchi nella finestra')
        notes, next_attack = [], {}
        for beat, pitch, velocity in reversed(events):
            duration = min(values['gate_beats'], request.length_beats-beat,
                           next_attack.get(pitch, request.length_beats)-beat)
            notes.append(Note(beat, pitch, duration, max(1, min(127, round(velocity*values['velocity_ratio'])))))
            next_attack[pitch] = beat
        phrase = Phrase(request.length_beats, tuple(reversed(notes)))
        decision = {'method': 'percussion_phrase', 'material': self.name,
                              'style': 'none', 'style_weights': {},
                              'variation': values['variation'],
                              'standard_material': self.standard[0] if self.standard else None,
                              'logical_start': start, 'cycles': operations,
                              'interaction': interaction,
                              'structural_hits': len(structural),
                              'summary': f'variazione {values["variation"]:.2f} · {self.name} · ' + ', '.join(o['operation'] for o in operations)
                                         + f' · {interaction["supported_hits"]} sostegni, '
                                         + f'{interaction["omitted_answer_hits"]} risposte omesse · {len(notes)} attacchi'}
        origin = request.start-start
        spans = tuple(GestureSpan(origin+i*self.cycle, origin+(i+1)*self.cycle) for i in range(first, last))
        return VoicePlan(phrase, (request.start, start, end), decision, spans)

    def _style_plan(self, request, values, start, end):
        style = STYLE_BY_ID[values['style']]
        first, last = math.floor(start/style.cycle_beats), math.ceil(end/style.cycle_beats)
        if last-first > 128:
            raise ValueError('la richiesta supera 128 cicli percussivi')
        # Lo sviluppo avviene su cicli completi per conservare fase e selezione
        # dei complementi anche quando il ciclo attraversa più finestre.
        prepared = request.prepared_material
        if not isinstance(prepared, StyleMaterial):
            prepared = self.prepare_reference(replace(request, logical_start=start)).material
        regular, developed, answers, cores, operations = [], [], [], [], []
        for index in range(first, last):
            low, high = index*style.cycle_beats, (index+1)*style.cycle_beats
            material = [event for event in prepared.events if low <= event[0] < high]
            if len(material) > 128:
                raise ValueError('il ciclo di stile supera 128 attacchi')
            operation = self.development[index % len(self.development)] if values['variation'] else 'statement'
            operations.append({'cycle': index, 'operation': operation})
            rng = random.Random((values['seed'] << 32)+index)
            direction = rng.choice((-1, 1))
            for beat, pitch, velocity, core, response in material:
                if start <= beat < end:
                    regular.append((beat-start, pitch, velocity))
                    if core and (operation != 'silence' or values['variation'] == 0):
                        cores.append((beat-start, pitch, velocity))
                if operation == 'silence':
                    continue
                if not core:
                    if operation == 'subtract':
                        continue
                    if operation == 'displace':
                        beat = low+(beat-low+direction*values['displacement_beats']) % style.cycle_beats
                    if operation == 'accent':
                        velocity = max(1, min(127, velocity+direction*64))
                if not core and start <= beat < end:
                    (answers if response else developed).append((beat-start, pitch, velocity))
        # Le risposte dialogano; piatti di accompagnamento e appoggi mantengono
        # la propria autonomia anche quando le sorgenti sono silenziose.
        if values['variation']:
            answers, interaction = self._interact(answers, request.dependencies, values)
        else:
            interaction = {'supported_hits': 0, 'omitted_answer_hits': 0, 'available_sources': []}
        developed.extend(answers)
        developed.extend(cores)
        if values['variation'] == 0:
            events = regular
        elif values['variation'] == 1:
            events = developed
        else:
            events = self._vary(regular, developed, start, values)
        # Un complemento spostato su un evento strutturale non lo sostituisce.
        merged = {}
        for beat, pitch, velocity in events+cores:
            merged[beat, pitch] = max(merged.get((beat, pitch), 0), velocity)
        if len(merged) > 128:
            raise ValueError('la combinazione supera 128 attacchi nella finestra')
        notes, next_attack = [], {}
        for (beat, pitch), velocity in sorted(merged.items(), reverse=True):
            boundary = (math.floor((start+beat)/style.cycle_beats)+1)*style.cycle_beats-start
            duration = min(values['gate_beats'], request.length_beats-beat,
                           next_attack.get(pitch, request.length_beats)-beat, boundary-beat)
            notes.append(Note(beat, pitch, duration, max(1, min(127, round(velocity*values['velocity_ratio'])))))
            next_attack[pitch] = beat
        origin = request.start-start
        period = 4*style.cycle_beats
        spans = tuple(GestureSpan(origin+i*period, origin+(i+1)*period)
                      for i in range(math.floor(start/period), math.ceil(end/period)))
        decision = {'method': 'percussion_phrase', 'style': style.id, 'style_label': style.label,
                    'style_weights': prepared.transition.weights(start),
                    'transition_end_weights': prepared.transition.weights(end),
                    'transition_beats': prepared.transition.duration, 'style_cycle_beats': style.cycle_beats,
                    'meter': list(style.meter),
                    'style_variants': [{'cycle': i, 'variant': prepared.transition.variant(style.id, i, values['seed'], values['variation'])}
                                       for i in range(math.floor(start/style.cycle_beats), math.ceil(end/style.cycle_beats))],
                    'swing_delay_beats': style.swing_delay, 'logical_start': start,
                    'variation': values['variation'], 'cycles': operations,
                    'interaction': interaction, 'structural_hits': len(cores),
                    'summary': f'{style.label} · ' + ', '.join(f'{STYLE_BY_ID[name].label} {weight:.0%}'
                               for name, weight in prepared.transition.weights(end).items()) + f' · variazione {values["variation"]:.2f} · {len(notes)} attacchi'}
        return VoicePlan(Phrase(request.length_beats, tuple(reversed(notes))), (request.start, start, end, prepared.transition), decision, spans)

    def accept_reference(self, prepared):
        self.style_transition = (prepared.material.transition
                                 if isinstance(prepared.material, StyleMaterial) else None)

    def accept(self, plan):
        self.last_start, self.last_position, self.position = plan.state[:3]
        self.style_transition = plan.state[3] if len(plan.state) == 4 else None
        self.last_decision = plan.decision

    def __call__(self, request):
        plan = self.stage(request)
        self.accept(plan)
        return plan.phrase
