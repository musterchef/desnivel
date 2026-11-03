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
    dynamic = intent.dynamic_pressure or 0.
    bass = attack_rate(request.peers('bass_line'))
    percussion = attack_rate(request.peers('percussion'))
    pressure = bounded(.65*(bass or 0.)+.35*(percussion or 0.)/4, 0., 1.)
    result = {'velocity': ParameterTarget(bounded(base['velocity']+16*terrain+12*dynamic, 1, 127),
              'dinamica dal contesto e dalla pressione ambientale' if intent.dynamic_pressure is not None else
              'dinamica dal contesto locale' if intent.intensity is not None else 'dinamica di sezione: contesto locale indisponibile',
              8., integer=True, deadband=1.)}
    if intent.dynamic_pressure is not None:
        result['velocity'] = result['velocity'].with_contribution('dynamic_pressure', bounded(base['velocity']+16*terrain, 1, 127))
    if request.setting('development') > 0:
        result['activity'] = ParameterTarget(bounded(base['activity']+.18*terrain-.16*pressure, 0, 1),
            'attività dal terreno e dallo spazio lasciato dall’accompagnamento',
            16., request.length_beats*request.setting('phrase_windows'))
    if intent.material_change is not None:
        result['development'] = ParameterTarget(bounded(base['development']+.25*intent.material_change, 0, 1),
            'sviluppo dai cambiamenti ambientali', 16., request.length_beats*request.setting('phrase_windows')).with_contribution(
                'material_change', base['development'])
    return result
