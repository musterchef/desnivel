"""Realizzazione di gradi di scala in altezze MIDI per le voci armoniche."""


def scale_degree_pitch(root, intervals, degree, octave=0):
    """Restituisce l'altezza MIDI di un grado, estendendo la scala per ottave."""
    index = degree % len(intervals)
    return root + 12*octave + intervals[index] + 12*(degree//len(intervals))


def diatonic_triad(root, intervals, degree, octave=0):
    """Realizza una triade per terze diatoniche a partire da un grado di scala."""
    pitches = tuple(scale_degree_pitch(root, intervals, degree+2*voice, octave) for voice in range(3))
    if any(not 0 <= pitch <= 127 for pitch in pitches):
        raise ValueError('accordo fuori dal registro MIDI')
    return pitches
