"""Contratto dei comandi di sessione condiviso da terminale e HTTP."""
from desnivel.adapters.live_recording import RECORDING_ACTIONS

SIMPLE_ACTIONS = frozenset({
    'pause', 'resume', 'restart', 'toggle', 'weather_toggle', 'scan',
    'setup_begin', 'setup_associate', 'setup_cancel', 'setup_save',
    'component_prepare', 'component_check',
}) | RECORDING_ACTIONS
VALUE_ACTIONS = frozenset({'setup_reply', 'setup_command'})


def validate_command(command):
    if not isinstance(command, dict) or not isinstance(command.get('action'), str):
        raise ValueError('atteso un comando con action')
    action = command['action']
    if action in SIMPLE_ACTIONS and set(command) == {'action'}:
        return dict(command)
    if (action in VALUE_ACTIONS and set(command) == {'action', 'value'}
            and isinstance(command['value'], str) and len(command['value']) <= 512
            and all(char.isprintable() for char in command['value'])):
        return dict(command)
    raise ValueError('comando di sessione non valido')
