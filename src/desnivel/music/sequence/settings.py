"""Validazione della ricetta musicale delle voci cicliche, senza valori impliciti."""
import math

from desnivel.music.rhythm import SUBDIVISIONS

ROLES = ('melody', 'bass_line', 'sustained_texture')
CONTROL_LIMITS = {'octave': (-3, 3, True), 'activity': (0, 1, False),
                  'velocity': (1, 127, True), 'length_ms': (10, 10000, False),
                  'movement': (0, 1, False)}
CONTROLS = (*CONTROL_LIMITS, 'pulse')


def _fields(value, names, path):
    if not isinstance(value, dict):
        raise ValueError(f'{path}: oggetto richiesto')
    missing = sorted(set(names)-set(value))
    unknown = sorted(set(value)-set(names))
    errors = []
    if missing:
        errors.append('campi mancanti: '+', '.join(missing))
    if unknown:
        errors.append('campi sconosciuti: '+', '.join(unknown))
    if errors:
        raise ValueError(f'{path}: {"; ".join(errors)}')


def _number(value, low, high, path, integer=False):
    if (type(value) not in (int, float) or not math.isfinite(value)
            or not low <= value <= high or integer and type(value) is not int):
        raise ValueError(f'{path}: valore {"intero " if integer else ""}richiesto fra {low} e {high}')


def validate_parameters(values, path='sequence.parameters'):
    _fields(values, CONTROLS, path)
    _validate_numeric_parameters({name: values[name] for name in CONTROL_LIMITS}, path)
    if not isinstance(values['pulse'], str) or values['pulse'] not in SUBDIVISIONS:
        raise ValueError(f'{path}.pulse: suddivisione non valida')


def _validate_numeric_parameters(values, path):
    _fields(values, CONTROL_LIMITS, path)
    for name, (low, high, integer) in CONTROL_LIMITS.items():
        _number(values[name], low, high, f'{path}.{name}', integer)


def _validate_role(role, spec):
    path = f'music.roles.{role}'
    _fields(spec, ('parameters', 'response', 'pulse'), path)
    _validate_numeric_parameters(spec['parameters'], path+'.parameters')
    _validate_pulse(spec['pulse'], path+'.pulse')
    _fields(spec['response'], ('activity', 'velocity', 'articulation'), path+'.response')
    for name, limit in (('activity', 2), ('velocity', 127), ('articulation', 2)):
        _number(spec['response'][name], -limit, limit, path+'.response.'+name)


def _validate_adaptation(adaptation):
    _fields(adaptation, ('transition_beats', 'movement_change', 'movement_persistence',
                       'movement_material_change', 'velocity_pressure', 'length_persistence', 'length_change'),
           'music.adaptation')
    for name, value in adaptation.items():
        if name == 'transition_beats':
            low, high = .001, 1024
        elif name == 'velocity_pressure':
            low, high = -127, 127
        else:
            low, high = -2, 2
        _number(value, low, high, 'music.adaptation.'+name)


def _validate_pulse(pulse, path):
    _fields(pulse, ('fastest', 'slowest'), path)
    for name in ('fastest', 'slowest'):
        if not isinstance(pulse[name], str) or pulse[name] not in SUBDIVISIONS:
            raise ValueError(f'{path}.{name}: suddivisione non valida')
    if SUBDIVISIONS[pulse['fastest']] > SUBDIVISIONS[pulse['slowest']]:
        raise ValueError(f'{path}: fastest deve essere più rapido o uguale a slowest')


def _validate_phrasing(phrasing):
    _fields(phrasing, ('accents', 'velocity_accent', 'velocity_movement', 'length_accent', 'length_movement'),
           'music.phrasing')
    if not isinstance(phrasing['accents'], list) or not 1 <= len(phrasing['accents']) <= 128:
        raise ValueError('music.phrasing.accents: lista richiesta con 1–128 pesi')
    for value in phrasing['accents']:
        _number(value, -1, 1, 'music.phrasing.accents')
    for name in ('velocity_accent', 'velocity_movement', 'length_accent', 'length_movement'):
        _number(phrasing[name], 0, 127 if name.startswith('velocity') else 1, 'music.phrasing.'+name)


def validate_music(settings):
    _fields(settings, ('roles', 'adaptation', 'phrasing'), 'music')
    _fields(settings['roles'], ROLES, 'music.roles')
    for role, spec in settings['roles'].items():
        _validate_role(role, spec)
    _validate_adaptation(settings['adaptation'])
    _validate_phrasing(settings['phrasing'])
