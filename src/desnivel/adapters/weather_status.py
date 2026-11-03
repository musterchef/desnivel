"""Stato leggibile del meteo sul piano corrente di una singola voce."""


def describe_weather(configured, enabled, plan, voice, manual):
    state = dict(configured=configured, enabled=enabled, status='not_loaded',
                 label='non caricato', parameters=[], blocked_parameters=[], pending=False)
    def result(status, label):
        if state['pending'] and not enabled:
            label += ' · disattivazione in coda'
        return dict(state, status=status, label=label)
    if not configured:
        return state
    if plan is None:
        return (result('waiting', 'abilitato · in attesa del piano corrente') if enabled
                else result('disabled', 'disattivato'))
    description = plan.get('local_trip', {}).get('environment', {}).get('weather', {})
    current_enabled = description.get('interpretation_enabled', False)
    state['pending'] = enabled != current_enabled
    if not current_enabled:
        return result('disabled', 'attivazione in coda' if enabled else 'disattivato')
    phrase = plan.get('voices', {}).get(voice)
    if not phrase or not phrase.get('participating', True):
        return result('inactive', 'abilitato · voce fuori dal piano')
    channels = description.get('channels', {})
    if not any(channels.get(name, {}).get('status') == 'available'
               for name in ('wind_speed_kmh', 'precipitation_change_mm')):
        return result('unavailable', 'abilitato · dati indisponibili')
    candidates = []
    for name, parameter in plan.get('automation', {}).get(voice, {}).items():
        contributions = parameter.get('contributions', {})
        effects = {key: value for key, value in contributions.items()
                   if key in ('dynamic_pressure', 'material_change')}
        if not effects:
            continue
        candidates.append(name)
        if any(abs(value) > 1e-9 for value in effects.values()):
            if manual(name):
                state['blocked_parameters'].append(name)
            else:
                state['parameters'].append(name)
    if state['parameters']:
        return result('active', 'in uso · '+', '.join(state['parameters']))
    if state['blocked_parameters']:
        return result('manual', 'escluso dai parametri manuali')
    if candidates:
        return result('neutral', 'abilitato · nessun nuovo contributo')
    return result('not_used', 'abilitato · non applicato a questa voce')
