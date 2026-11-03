"""Previsione di una singola istanza Snake da stato e note MIDI osservate."""
from dataclasses import replace
import math
import time

from desnivel.adapters.snake_sequence import SnakeState, SPEEDS, predict
from desnivel.music.phrases import Note, Phrase
from desnivel.music.sources import MusicalSource


class SnakeForecast:
    def __init__(self, *, clock=time.monotonic, max_age_s=.75):
        self.clock, self.max_age_s = clock, max_age_s
        self.packet = None
        self.received = 0.
        self.error = 'telemetria non disponibile'
        self.seen = None

    def invalidate(self, reason):
        self.packet, self.error = None, reason

    def update(self, packet):
        if packet is None:
            self.invalidate('telemetria non disponibile o precedente alla revisione dei banchi')
            return
        try:
            identity = (packet['source'], packet['serial'])
            if not isinstance(identity[0], str) or not identity[0] or type(identity[1]) is not int or identity[1] < 0:
                raise ValueError('identità o seriale della telemetria non validi')
            if self.seen and identity[0] == self.seen[0] and identity[1] <= self.seen[1]:
                return
            self.seen = identity
            if packet.get('version') != 1 or packet.get('observation_version') != 1:
                raise ValueError('aggiornare la mod Snake con osservazione MIDI')
            if packet.get('error'):
                raise ValueError(str(packet['error']))
            if packet.get('playing') != 1:
                raise ValueError('trasporto Snake fermo')
            if not math.isfinite(packet['beat']) or packet['beat'] < 0:
                raise ValueError('beat Snake non valido')
            state = SnakeState.from_dict(packet['state'])
            for note in packet['active_notes']:
                if (type(note['pitch']) is not int or not 0 <= note['pitch'] <= 127
                        or type(note['velocity']) is not int or not 1 <= note['velocity'] <= 127
                        or not math.isfinite(note['remaining_ms']) or not 0 < note['remaining_ms'] <= 10000):
                    raise ValueError('nota sostenuta Snake non valida')
            if len(packet['active_notes']) > 128:
                raise ValueError('troppe note sostenute Snake')
        except (ValueError, KeyError, TypeError) as error:
            self.packet = None
            self.error = str(error)
            return
        self.packet, self.state = packet, state
        self.received, self.error = self.clock(), None

    def project(self, role, start, length_beats, *, beat, bpm):
        try:
            if self.packet is None:
                raise ValueError(self.error)
            if self.clock()-self.received > self.max_age_s:
                raise ValueError('telemetria Snake scaduta')
            packet, state = self.packet, self.state
            if bpm is None or abs(state.bpm-bpm) > .01:
                raise ValueError('BPM Snake non allineati alla sessione')
            lag = beat-packet['beat']
            if abs(lag) > bpm/60*self.max_age_s:
                raise ValueError('posizione Snake non allineata alla sessione')
            elapsed = start-packet['beat']
            if elapsed < 0:
                raise ValueError('previsione richiesta prima dello stato Snake')
            lanes = {}
            for name in ('notes_lane', 'gates_lane', 'velocities_lane'):
                lane = getattr(state, name)
                period = float(SPEEDS[lane.speed])*lane.steps
                lanes[name] = replace(lane, phase_beats=round((lane.phase_beats+elapsed)%period, 9))
            phrase = predict(replace(state, **lanes), length_beats)
            # Le code già emesse sono osservate all'uscita di makenote, non ricostruite
            # usando banchi che potrebbero essere cambiati dopo il loro attacco.
            carried = []
            for note in packet['active_notes']:
                remaining = note['remaining_ms']*bpm/60000-elapsed
                next_attack = min((n.beat for n in phrase.notes if n.pitch == note['pitch']), default=length_beats)
                duration = min(remaining, next_attack, length_beats)
                if duration > 0:
                    carried.append(Note(0., note['pitch'], duration, note['velocity']))
            return MusicalSource(role, Phrase(length_beats, (*carried, *phrase.notes)), len(carried))
        except (ValueError, KeyError, TypeError) as error:
            return MusicalSource(role, None, unavailable_reason=str(error))
