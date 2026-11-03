"""Sostegno del basso secondo lo spazio della melodia e la capacità recente."""
from desnivel.music.automation import ParameterTarget, attack_rate, bounded


def targets(request, settings, last_decision):
    base = request.parameters
    rate = attack_rate(request.peers('melody'))
    busy = bounded(rate/1.5, 0, 1) if rate is not None else None
    movement = 0. if busy is None else .18-.42*busy
    bass_pressure = bounded(sum(p.occupied_ratio or 0. for p in request.peers('bass_line')), 0, 1)
    capacity = min(4., 1/settings.min_spacing)
    density = last_decision.get('density') if last_decision else None
    if density and density.get('active_beats') and density['capacity_attacks'] is not None:
        capacity = min(4., density['capacity_attacks']/density['active_beats'])
    return {
        'density': ParameterTarget(bounded((base['density']+movement)*(1-.4*bass_pressure), 0, capacity),
            'densità secondo melodia, altri bassi e capacità ritmica recente' if busy is not None or bass_pressure else
            'base limitata dalla capacità ritmica: storia melodica indisponibile'),
        'syncopation': ParameterTarget(bounded(base['syncopation']+(0. if busy is None else .16-.24*busy), 0, 1),
            'più movimento negli spazi melodici, meno sincopi con melodia fitta' if busy is not None else
            'sincopi di sezione: storia melodica indisponibile'),
    }
