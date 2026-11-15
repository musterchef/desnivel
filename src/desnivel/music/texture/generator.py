"""Realizzazioni dell'armonia di sezione, indipendenti o coordinate con una sorgente."""
from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import math

from desnivel.music.automation import bounded
from desnivel.music.observation import observe_phrase
from desnivel.music.patterns import SCALES
from desnivel.music.phrases import Note, Phrase
from desnivel.music.interactions import VoicePlan, GestureSpan
from .adaptation import targets


ROLES = ('harmony',)
DEFAULTS = dict(octave=0, velocity=85, realization='chord', step_beats=1.,
                articulation=.9, follow_source=0, support_source=0)


@dataclass(frozen=True)
class HarmonyRealization:
    label: str
    voicing: Callable[[int, tuple[int, ...], int], tuple[int, ...]]
    timing: Callable[[tuple[int, ...], float, Mapping, int], tuple[Note, ...]]


def _pitch(root, intervals, degree, octave):
    index = degree % len(intervals)
    return root + 12*octave + intervals[index] + 12*(degree//len(intervals))


def _degree_for_pitch_class(pitch_class, root, intervals):
    scale_pitch_classes = tuple((root+interval) % 12 for interval in intervals)
    return min(range(len(intervals)),
               key=lambda i: min((scale_pitch_classes[i]-pitch_class) % 12,
                                 (pitch_class-scale_pitch_classes[i]) % 12))


def _chord_voicing(root, intervals, degree):
    root_offset = _pitch(0, intervals, degree, 0)
    pitches = tuple(
        root + _pitch(0, intervals, degree+2*voice, 0) - root_offset
        for voice in range(3)
    )
    if any(not 0 <= pitch <= 127 for pitch in pitches):
        raise ValueError('accordo fuori dal registro MIDI')
    return pitches


def _single_note_voicing(root, intervals, degree):
    return (root,)


def _sustained_notes(pitches, length, settings, velocity):
    return tuple(Note(0, pitch, length, velocity) for pitch in pitches)


def _repeated_notes(pitches, length, settings, velocity):
    if not pitches:
        return ()
    step = settings['step_beats']
    count = math.ceil(length/step)
    if count > 128:
        raise ValueError('l’armonia supera 128 note nella finestra')
    return tuple(
        Note(i*step, pitches[0], min(step, length-i*step)*settings['articulation'], velocity)
        for i in range(count)
    )


REALIZATIONS = {
    'chord': HarmonyRealization('accordi di sezione', _chord_voicing, _sustained_notes),
    'repeated_note': HarmonyRealization('nota ripetuta', _single_note_voicing, _repeated_notes),
}
REALIZATION_CHOICES = tuple((name, realization.label) for name, realization in REALIZATIONS.items())


class TextureGenerator:
    adapt = staticmethod(targets)
    supported_roles = ROLES

    def __init__(self, degree=0, settings=None):
        if type(degree) is not int or degree < 0:
            raise ValueError('degree richiede un grado intero non negativo')
        self.degree = degree
        self.settings = {**DEFAULTS, **(settings or {})}
        self.validate('harmony', {})
        self.reset()

    def validate(self, role, parameters):
        if role not in self.supported_roles:
            raise ValueError('ruolo non supportato dall’armonia di sezione')
        values = {**self.settings, **parameters}
        if set(values) != set(DEFAULTS):
            raise ValueError('parametri sconosciuti per l’armonia di sezione')
        if type(values['octave']) is not int or not -5 <= values['octave'] <= 5:
            raise ValueError('octave deve essere un intero tra -5 e 5')
        if type(values['velocity']) is not int or not 1 <= values['velocity'] <= 127:
            raise ValueError('velocity deve essere un intero tra 1 e 127')
        if (not isinstance(values['realization'], str)
                or values['realization'] not in REALIZATIONS):
            raise ValueError('realization sconosciuta')
        if (type(values['step_beats']) not in (int, float)
                or not math.isfinite(values['step_beats']) or not .25 <= values['step_beats'] <= 8):
            raise ValueError('step_beats deve essere finito e tra 0.25 e 8')
        if (type(values['articulation']) not in (int, float)
                or not math.isfinite(values['articulation']) or not .05 <= values['articulation'] <= 1):
            raise ValueError('articulation deve essere finita e in [0.05, 1]')
        if type(values['follow_source']) is not int or values['follow_source'] not in (0, 1):
            raise ValueError('follow_source deve essere 0 o 1')
        if type(values['support_source']) is not int or values['support_source'] not in (0, 1):
            raise ValueError('support_source deve essere 0 o 1')
        if values['follow_source'] and values['support_source']:
            raise ValueError('follow_source e support_source non possono essere attivi insieme')
        return values

    def reset(self):
        self.previous_pitch = self.previous_end = None
        self.last_start = self.last_reference = None
        self.last_decision = None

    def stage(self, request):
        values = self.validate(request.role, request.parameters)
        if request.context is None:
            raise ValueError('l’armonia richiede tonica e scala')
        intervals = SCALES[request.context.scale]
        degree = self.degree
        base = _pitch(request.context.root, intervals, degree, values['octave'])
        if not 0 <= base <= 127:
            raise ValueError('armonia fuori dal registro MIDI')
        # Ripianificare la stessa finestra conserva il riferimento di continuità.
        reference = None
        if request.start == self.last_start:
            reference = self.last_reference
        elif request.start == self.previous_end:
            reference = self.previous_pitch
        register = (base, min(127, base+11))
        root, velocity, source, reason, source_register = base, values['velocity'], None, None, None
        chord_events = None
        if values['follow_source'] or values['support_source']:
            if len(request.dependencies) > 1:
                raise ValueError('l’armonia coordinata ammette una sola sorgente')
            if not request.dependencies:
                root, reason = None, 'source_unavailable'
            else:
                source, phrase = next(iter(request.dependencies.items()))
                if not phrase.notes:
                    if values['follow_source']:
                        root, reason = None, 'source_silent'
                elif values['follow_source']:
                    if values['realization'] == 'repeated_note':
                        weights = defaultdict(float)
                        for note in phrase.notes:
                            weights[note.pitch % 12] += note.duration*note.velocity
                        peak = max(weights.values())
                        center = base if reference is None else reference
                        candidates = [p for p in range(register[0], register[1]+1) if p % 12 in weights]
                        if not candidates:
                            raise ValueError('nessuna altezza sorgente nel registro dell’armonia')
                        root = max(candidates, key=lambda p: (weights[p % 12]/peak-abs(p-center)/12,
                                                              -abs(p-center), -p))
                    else:
                        chord_events = []
                        notes_by_beat = defaultdict(list)
                        for note in phrase.notes:
                            notes_by_beat[note.beat].append(note)
                        for beat, attacks in sorted(notes_by_beat.items()):
                            weights = defaultdict(float)
                            for note in attacks:
                                weights[note.pitch % 12] += note.duration*note.velocity
                            pitch_class = max(weights, key=weights.get)
                            chord_degree = _degree_for_pitch_class(
                                pitch_class, request.context.root, intervals)
                            chord_root = _pitch(request.context.root, intervals, chord_degree, values['octave'])
                            chord = REALIZATIONS['chord'].voicing(chord_root, intervals, chord_degree)
                            if not chord_events or chord_events[-1][1] != chord:
                                chord_events.append((beat, chord, chord_root))
                        root = chord_events[-1][2]
                        degree = _degree_for_pitch_class(
                            root % 12, request.context.root+12*values['octave'], intervals)
                else:
                    observation = observe_phrase(phrase)
                    source_register = observation.register
                    low, high = source_register
                    velocity = round(bounded(velocity*(1-observation.occupied_ratio), 1, 127))

        realization = REALIZATIONS[values['realization']]
        pitches = () if root is None else realization.voicing(root, intervals, degree)
        if values['support_source'] and source_register is not None and pitches:
            low, high = source_register
            anchor = base if reference is None else reference
            pitches = self._outside_register(pitches, low, high, anchor)
            if pitches is None:
                pitches = ()
                reason = 'register_contested'
            else:
                root = pitches[0]
        if chord_events:
            notes = tuple(
                Note(beat, pitch, end-beat, velocity)
                for index, (beat, chord, _) in enumerate(chord_events)
                for end in (chord_events[index+1][0] if index+1 < len(chord_events)
                            else request.length_beats,)
                for pitch in chord
            )
            decision_chords = [{'beat': beat, 'pitches': list(chord)}
                               for beat, chord, _ in chord_events]
            pitches = chord_events[-1][1]
        else:
            notes = realization.timing(pitches, request.length_beats, values, velocity)
            decision_chords = ([{'beat': 0, 'pitches': list(pitches)}]
                               if values['realization'] == 'chord' and pitches else [])
        mode = 'follow_source' if values['follow_source'] else 'support_source' if values['support_source'] else 'independent'
        summary_label = {'follow_source': 'accordi sui cambi della sorgente',
                         'support_source': 'supporto senza sovrapposizione',
                         'independent': 'sostegno di sezione'}[mode]
        decision = {'method': 'sustained_texture', 'realization': values['realization'],
                              'follow_source': values['follow_source'],
                              'support_source': values['support_source'],
                              'source': source, 'reference_pitch': base, 'register': list(register),
                              'source_register': list(source_register) if source_register is not None else None,
                              'pitches': list(pitches), 'chords': decision_chords, 'silence_reason': reason,
                              'summary': summary_label + (' · silenzio' if not notes else
                                                          ' · MIDI ' + ', '.join(map(str, pitches)))}
        return VoicePlan(Phrase(request.length_beats, notes),
                         (root, request.start+request.length_beats, request.start, reference),
                         decision, (GestureSpan(request.start, request.start+request.length_beats),))

    @staticmethod
    def _outside_register(pitches, low, high, anchor):
        shifts = (12*octave for octave in range(-10, 11))
        candidates = [
            tuple(pitch+shift for pitch in pitches)
            for shift in shifts
            if all(0 <= pitch+shift <= 127 and not low <= pitch+shift <= high
                   for pitch in pitches)
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda chord: (abs(chord[0]-anchor), chord))

    def accept(self, plan):
        self.previous_pitch, self.previous_end, self.last_start, self.last_reference = plan.state
        self.last_decision = plan.decision

    def __call__(self, request):
        plan = self.stage(request)
        self.accept(plan)
        return plan.phrase

    def describe_controls(self, role, parameters):
        return {'follow_source': {'label': 'segui sorgente'},
                'support_source': {'label': 'supporta sorgente'}}
