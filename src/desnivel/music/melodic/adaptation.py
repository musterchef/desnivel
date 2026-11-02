"""Attività e dinamica della melodia in relazione a percorso e accompagnamento."""
from desnivel.music.automation import ParameterTarget, attack_rate, bounded
from desnivel.music.texture.adaptation import targets as texture_targets


def targets(request):
    if request.role == 'sustained_texture':
        return texture_targets(request)
    if request.role != 'melody':
        return {}
    base, intent = request.parameters, request.intent
    terrain = 0. if intent.intensity is None else intent.intensity-.5
    bass = attack_rate(request.peers('bass_line'))
    percussion = attack_rate(request.peers('percussion'))
    pressure = bounded(.65*(bass or 0.)+.35*(percussion or 0.)/4, 0., 1.)
    result = {'velocity': ParameterTarget(bounded(base['velocity']+16*terrain, 1, 127),
              'dinamica dal contesto locale' if intent.intensity is not None else 'dinamica di sezione: contesto locale indisponibile',
              8., integer=True, deadband=1.)}
    if request.setting('development') > 0:
        result['activity'] = ParameterTarget(bounded(base['activity']+.18*terrain-.16*pressure, 0, 1),
            'attività dal terreno e dallo spazio lasciato dall’accompagnamento',
            16., request.length_beats*request.setting('phrase_windows'))
    return result
