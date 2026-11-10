"""Una nota sostenuta per finestra, indipendente o in relazione a una sorgente."""
from collections import defaultdict

from desnivel.music.patterns import SCALES
from desnivel.music.phrases import Note, Phrase
from desnivel.music.interactions import VoicePlan, GestureSpan
from .adaptation import targets


ROLES = ('sustained_texture',)
DEFAULTS = dict(octave=0, velocity=85, follow_source=0)


class TextureGenerator:
    adapt = staticmethod(targets)
    supported_roles = ROLES

    def __init__(self, degree=0, settings=None):
        if type(degree) is not int or degree < 0:
            raise ValueError('degree richiede un grado intero non negativo')
        self.degree = degree
        self.settings = {**DEFAULTS, **(settings or {})}
        self.validate('sustained_texture', {})
        self.reset()

    def validate(self, role, parameters):
        if role not in self.supported_roles:
            raise ValueError('ruolo non supportato dalla tessitura sostenuta')
        values = {**self.settings, **parameters}
        if set(values) != set(DEFAULTS):
            raise ValueError('parametri sconosciuti per la tessitura sostenuta')
        if type(values['octave']) is not int or not -5 <= values['octave'] <= 5:
            raise ValueError('octave deve essere un intero tra -5 e 5')
        if type(values['velocity']) is not int or not 1 <= values['velocity'] <= 127:
            raise ValueError('velocity deve essere un intero tra 1 e 127')
        if type(values['follow_source']) is not int or values['follow_source'] not in (0, 1):
            raise ValueError('follow_source deve essere 0 o 1')
        return values

    def reset(self):
        self.previous_pitch = self.previous_end = None
        self.last_start = self.last_reference = None
        self.last_decision = None

    def stage(self, request):
        values = self.validate(request.role, request.parameters)
        if request.context is None:
            raise ValueError('la tessitura richiede tonica e scala')
        intervals = SCALES[request.context.scale]
        degree = self.degree
        base = (request.context.root + 12*values['octave']
                + intervals[degree % len(intervals)] + 12*(degree//len(intervals)))
        if not 0 <= base <= 127:
            raise ValueError('tessitura fuori dal registro MIDI')
        # Ripianificare la stessa finestra conserva il riferimento di continuità.
        reference = None
        if request.start == self.last_start:
            reference = self.last_reference
        elif request.start == self.previous_end:
            reference = self.previous_pitch
        register = (base, min(127, base+11))
        pitch, source, reason = base, None, None
        if values['follow_source']:
            if len(request.dependencies) > 1:
                raise ValueError('la tessitura coordinata ammette una sola sorgente')
            if not request.dependencies:
                pitch, reason = None, 'source_unavailable'
            else:
                source, phrase = next(iter(request.dependencies.items()))
                if not phrase.notes:
                    pitch, reason = None, 'source_silent'
                else:
                    weights = defaultdict(float)
                    for note in phrase.notes:
                        weights[note.pitch % 12] += note.duration*note.velocity
                    candidates = [p for p in range(register[0], register[1]+1) if p % 12 in weights]
                    if not candidates:
                        raise ValueError('nessuna altezza sorgente nel registro della tessitura')
                    peak = max(weights.values())
                    center = base if reference is None else reference
                    pitch = max(candidates, key=lambda p: (weights[p % 12]/peak-abs(p-center)/12,
                                                           -abs(p-center), -p))
        notes = () if pitch is None else (Note(0, pitch, request.length_beats, values['velocity']),)
        decision = {'method': 'sustained_texture', 'follow_source': values['follow_source'],
                              'source': source, 'reference_pitch': base, 'register': list(register),
                              'pitch': pitch, 'silence_reason': reason,
                              'summary': ('sostegno della sorgente' if values['follow_source'] else 'sostegno di sezione')
                                         + (' · silenzio' if pitch is None else f' · MIDI {pitch}')}
        return VoicePlan(Phrase(request.length_beats, notes),
                         (pitch, request.start+request.length_beats, request.start, reference),
                         decision, (GestureSpan(request.start, request.start+request.length_beats),))

    def accept(self, plan):
        self.previous_pitch, self.previous_end, self.last_start, self.last_reference = plan.state
        self.last_decision = plan.decision

    def __call__(self, request):
        plan = self.stage(request)
        self.accept(plan)
        return plan.phrase

    def describe_controls(self, role, parameters):
        return {'follow_source': {'label': 'Segui sorgente'}}
