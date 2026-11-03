"""Dinamica della tessitura, con spazio per il registro melodico."""
from desnivel.music.automation import ParameterTarget, bounded


def targets(request):
    base, intent = request.parameters, request.intent
    terrain = 0. if intent.intensity is None else intent.intensity-.5
    low = request.context.root+12*request.setting('octave')
    pressure = 0.
    for peer in request.peers('melody'):
        if peer.register is None or peer.occupied_ratio is None:
            continue
        a, b = peer.register
        overlap = max(0, min(low+11, b)-max(low, a)+1)/(b-a+1)
        pressure = max(pressure, overlap*peer.occupied_ratio)
    target = ParameterTarget(bounded(base['velocity']*(1+.3*terrain+.15*(intent.dynamic_pressure or 0.))*(1-.2*pressure), 1, 127),
            'sostegno dinamico con alleggerimento nel registro occupato dalla melodia'+
            (' e pressione ambientale' if intent.dynamic_pressure is not None else ''),
            8., integer=True, deadband=1.)
    if intent.dynamic_pressure is not None:
        target = target.with_contribution('dynamic_pressure', bounded(base['velocity']*(1+.3*terrain)*(1-.2*pressure), 1, 127))
    return {'velocity': target}
