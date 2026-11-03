from copy import deepcopy

from desnivel.adapters.weather_status import describe_weather


def plan():
    return {'voices': {'synth': {'participating': True}},
            'local_trip': {'environment': {'weather': {'interpretation_enabled': True, 'channels': {
                'wind_speed_kmh': {'status': 'available'}, 'precipitation_change_mm': {'status': 'available'}}}}},
            'automation': {'synth': {'velocity': {'contributions': {'dynamic_pressure': 12}},
                                     'development': {'contributions': {'material_change': .25}}}}}


def test_weather_status_separates_configuration_from_current_voice_contributions():
    assert describe_weather(False, False, None, 'synth', lambda _: False)['status'] == 'not_loaded'
    assert describe_weather(True, False, None, 'synth', lambda _: False)['status'] == 'disabled'
    assert describe_weather(True, True, None, 'synth', lambda _: False)['status'] == 'waiting'
    state = describe_weather(True, True, plan(), 'synth', lambda _: False)
    assert state['status'] == 'active'
    assert state['parameters'] == ['velocity', 'development']


def test_weather_toggle_reports_current_contribution_until_queued_plans_change():
    state = describe_weather(True, False, plan(), 'synth', lambda _: False)
    assert state['status'] == 'active' and state['pending']
    assert 'disattivazione in coda' in state['label']
    current = plan()
    current['local_trip']['environment']['weather']['interpretation_enabled'] = False
    state = describe_weather(True, True, current, 'synth', lambda _: False)
    assert state['status'] == 'disabled' and state['pending']
    assert state['label'] == 'attivazione in coda'


def test_manual_parameters_and_voices_without_weather_are_explicit():
    state = describe_weather(True, True, plan(), 'synth', lambda _: True)
    assert state['status'] == 'manual' and not state['parameters']
    state = describe_weather(True, True, plan(), 'synth', lambda name: name == 'velocity')
    assert state['status'] == 'active'
    assert state['parameters'] == ['development'] and state['blocked_parameters'] == ['velocity']
    current = plan()
    current['automation']['synth'] = {}
    assert describe_weather(True, True, current, 'synth', lambda _: False)['status'] == 'not_used'
    current['voices']['synth']['participating'] = False
    assert describe_weather(True, True, current, 'synth', lambda _: False)['status'] == 'inactive'


def test_neutral_conditions_are_distinct_from_missing_data():
    current = deepcopy(plan())
    for parameter in current['automation']['synth'].values():
        parameter['contributions'] = {name: 0 for name in parameter['contributions']}
    assert describe_weather(True, True, current, 'synth', lambda _: False)['status'] == 'neutral'
    for channel in current['local_trip']['environment']['weather']['channels'].values():
        channel['status'] = 'partial'
    assert describe_weather(True, True, current, 'synth', lambda _: False)['status'] == 'unavailable'
