"""Protocollo del dispositivo MIDI di voce: controlli e piani da Python."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
import re
import time
from typing import Callable
from uuid import uuid4

from desnivel.music.phrases import Phrase

ADDRESS = '/desnivel/v1/voice/message'
CONTROL_ADDRESS = '/desnivel/v1/voice/control'


@dataclass(frozen=True)
class Control:
    minimum: float
    maximum: float
    integer: bool = False
    toggle: bool = False

    def validate(self, value):
        if (type(value) not in (int, float) or not math.isfinite(value)
                or not self.minimum <= value <= self.maximum
                or (self.integer and int(value) != value)):
            raise ValueError('valore del controllo fuori dai limiti')
        return int(value) if self.integer else value

    def __post_init__(self):
        if not all(math.isfinite(v) for v in (self.minimum, self.maximum)) or self.minimum > self.maximum:
            raise ValueError('limiti del controllo non validi')
        if self.toggle and (not self.integer or self.minimum != 0 or self.maximum != 1):
            raise ValueError('uno switch richiede valori interi 0 e 1')


@dataclass(frozen=True)
class ChoiceControl:
    """Scelta nominale: identificativi persistenti e descrizioni per il device."""
    choices: tuple[tuple[str, str], ...]

    def __post_init__(self):
        object.__setattr__(self, 'choices', tuple(tuple(choice) for choice in self.choices))
        if (not self.choices or any(len(c) != 2 or any(not isinstance(s, str) or not s for s in c)
                                    for c in self.choices)
                or len({c[0] for c in self.choices}) != len(self.choices)):
            raise ValueError('scelte nominali non vuote con identificativi distinti richieste')

    def validate(self, value):
        if not isinstance(value, str) or value not in {c[0] for c in self.choices}:
            raise ValueError('scelta del controllo sconosciuta')
        return value


@dataclass
class DeviceVoice:
    """Controlli realmente esposti dal componente Python associato alla voce."""

    controls: dict[str, Control | ChoiceControl] = field(default_factory=dict)
    values: dict[str, float | str] = field(default_factory=dict)
    presets: dict[str, dict[str, float | str]] = field(default_factory=dict)
    apply: Callable[[dict], None] | None = None
    role: str | None = None
    preset: str | None = None
    role_state: Callable[[], dict] | None = None
    apply_role: Callable[[str | None], None] | None = None
    read_values: Callable[[], dict] | None = None
    save_preset: Callable | None = None
    editable_presets: set[str] = field(default_factory=set)
    apply_presence: Callable[[float], None] | None = None
    describe_controls: Callable[[str | None, dict], dict] | None = None
    preset_defaults: dict = field(default_factory=dict)
    preset_migrations: dict = field(default_factory=dict)
    apply_parameter: Callable[[str, float | str], None] | None = None
    migrate_preset: Callable | None = None

    @classmethod
    def for_session(cls, session, voice: str, progress: Callable[[], float], **controls):
        """Collega ruoli e controlli alla sessione con avanzamento fornito dal chiamante."""
        session.role_state(voice, progress())
        defaults = dict(controls.get('values', {}))
        def read_values():
            parameters = {**defaults, **session.parameters_at(voice, progress())}
            return {name: parameters[name] for name in defaults}
        return cls(
            read_values=read_values,
            role_state=lambda: session.role_state(voice, progress()),
            apply_role=lambda role: session.set_role(voice, role),
            apply_presence=lambda value: session.set_presence_multiplier(voice, value),
            apply_parameter=lambda name, value: session.set_parameter(voice, name, value),
            apply=lambda values: session.set_parameters(voice, values), **controls)

    def __post_init__(self):
        if self.preset_defaults.keys()-self.controls.keys():
            raise ValueError('default di migrazione per controlli sconosciuti')
        for name, value in self.preset_defaults.items():
            self.controls[name].validate(value)
        if set(self.controls) != set(self.values):
            raise ValueError('ogni controllo richiede un valore iniziale')
        for name, value in self.values.items():
            self.controls[name].validate(value)
        for values in self.presets.values():
            if set(values) != set(self.controls):
                raise ValueError('ogni preset deve definire tutti i controlli esposti')
            for name, value in values.items():
                self.controls[name].validate(value)
        if self.controls and self.apply is None:
            raise ValueError('i controlli richiedono una funzione di applicazione')


class VoiceDeviceBridge:
    """Collega istanze identificate a voci e destinazioni UDP locali.

    Il chiamante serializza le richieste e le chiamate di pianificazione.
    Non genera note e non decide ruoli o preset musicali.
    """

    def __init__(self, voices: dict[str, DeviceVoice], send: Callable, *, clock=time.monotonic):
        self.voices = voices
        self.send = send  # send(port, address, payload_dict)
        self.clock = clock
        self.connections = {}
        self.session = uuid4().hex
        self.serial = 0
        self.last_plans = {}

    def _snapshot(self, voice):
        spec = self.voices[voice]
        roles = spec.role_state() if spec.role_state else {
            'role': spec.role, 'role_mode': 'section', 'section_role': spec.role,
            'supported_roles': [], 'active': None,
        }
        values = spec.read_values() if spec.read_values else spec.values
        details = spec.describe_controls(roles['role'], values) if spec.describe_controls else {}
        return {**roles, 'preset': spec.preset, 'presets': list(spec.presets),
                'can_save_presets': spec.save_preset is not None,
                'editable_presets': sorted(spec.editable_presets),
                'preset_migrations': spec.preset_migrations,
                'controls': {name: {**asdict(control), 'value': values[name], **details.get(name, {})}
                             for name, control in spec.controls.items()}}

    def handle(self, message: dict):
        """Valida una richiesta, applica i controlli e risponde alla stessa istanza."""
        if message.get('version') != 1:
            raise ValueError('versione non supportata')
        voice, instance = message['voice'], message['instance']
        port, serial, action = message['reply_port'], message['serial'], message['action']
        capabilities = message.get('capabilities', [])
        if (not isinstance(voice, str) or voice not in self.voices
                or not isinstance(instance, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', instance)
                or type(port) is not int or not 1024 <= port <= 65535
                or type(serial) is not int or serial < 0
                or not isinstance(capabilities, list) or any(not isinstance(c, str) for c in capabilities)):
            raise ValueError('identità, porta o seriale non valido')
        now = self.clock()
        previous = self.connections.get(voice)
        if previous and previous['instance'] != instance and now - previous['seen'] < 3:
            raise ValueError('voce già associata a un altro dispositivo')
        for name, connection in self.connections.items():
            if name != voice and connection['port'] == port and now - connection['seen'] < 3:
                raise ValueError('porta già associata a un’altra voce')
        if not previous or previous['instance'] != instance:
            if action != 'hello':
                raise ValueError('collegare il dispositivo prima di inviare controlli')
            previous = {'instance': instance, 'port': port, 'serial': -1, 'seen': now}
            self.connections[voice] = previous
        if previous['port'] != port:
            raise ValueError('porta cambiata: riconnettere il dispositivo')
        duplicate = serial <= previous['serial']
        if not duplicate:
            spec = self.voices[voice]
            if action == 'role':
                if spec.apply_role is None or spec.role_state is None:
                    raise ValueError('selezione del ruolo non disponibile')
                role = message['role']
                if role is not None and role not in spec.role_state()['supported_roles']:
                    raise ValueError('ruolo non supportato')
                spec.apply_role(role)
            elif action == 'preset':
                name = message['preset']
                values = dict(spec.presets[name])
                spec.apply(values)
                spec.values, spec.preset = values, name
            elif action == 'presence':
                if spec.apply_presence is None:
                    raise ValueError('controllo della presenza non disponibile')
                spec.apply_presence(Control(0, 10).validate(message['value']))
            elif action == 'save_preset':
                if spec.save_preset is None:
                    raise ValueError('salvataggio dei preset non disponibile')
                name, overwrite = message['preset'], message.get('overwrite', False)
                if (not isinstance(name, str) or not name.strip() or name != name.strip()
                        or len(name) > 64 or not name.isprintable() or type(overwrite) is not bool):
                    raise ValueError('nome del preset non valido: usare da 1 a 64 caratteri')
                if name in spec.presets and name not in spec.editable_presets:
                    raise ValueError('preset base protetto: salvare con un nuovo nome')
                current = spec.read_values() if spec.read_values else spec.values
                values = {key: control.validate(current[key]) for key, control in spec.controls.items()}
                spec.save_preset(name, values, overwrite)
                spec.presets[name] = values
                spec.preset_migrations.pop(name, None)
                spec.editable_presets.add(name)
            elif action == 'parameter':
                name = message['parameter']
                value = spec.controls[name].validate(message['value'])
                current = spec.read_values() if spec.read_values else spec.values
                values = {**current, name: value}
                if spec.apply_parameter is not None:
                    spec.apply_parameter(name, value)
                else:
                    spec.apply(values)
                spec.values, spec.preset = values, None
            elif action == 'panic':
                self.reset(voice)
            elif action not in ('hello', 'transport'):
                raise ValueError('azione non supportata')
            previous['serial'] = serial
        previous['seen'] = now
        previous['capabilities'] = capabilities
        reply = {'version': 1, 'kind': 'state', 'voice': voice, 'instance': instance,
                 'serial': serial, 'session': self.session, **self._snapshot(voice)}
        if action == 'save_preset':
            reply['notice'] = f'Preset salvato: {message["preset"]}'
        self.send(port, ADDRESS, reply)
        return reply

    def error(self, message, error):
        """Risponde soltanto a identità e porte riconosciute dal protocollo."""
        port = message.get('reply_port')
        if (type(port) is int and 1024 <= port <= 65535
                and isinstance(message.get('instance'), str)):
            self.send(port, ADDRESS, {'version': 1, 'kind': 'error',
                                     'voice': message.get('voice'), 'instance': message['instance'],
                                     'error': str(error)})

    def _plan(self, voice, plan):
        connection = self.connections[voice]
        if self.clock() - connection['seen'] >= 3:
            raise ValueError(f'dispositivo non collegato: {voice}')
        self.serial += 1
        payload = {'version': 1, 'session': self.session, 'serial': self.serial, **plan}
        if plan.get('reset'):
            self.last_plans.pop(voice, None)
        else:
            self.last_plans[voice] = {'start': plan['start'], 'length_beats': plan['phrase']['length_beats'],
                                      'notes': len(plan['phrase']['notes'])}
        self.send(connection['port'], ADDRESS,
                  {'version': 1, 'kind': 'plan', 'voice': voice,
                   'instance': connection['instance'], 'plan': payload})

    def connected(self, voice):
        connection = self.connections.get(voice)
        return bool(connection and self.clock() - connection['seen'] < 3)

    def status(self):
        return {name: {**self._snapshot(name), 'connected': self.connected(name),
                       'port': self.connections[name]['port'] if name in self.connections else None,
                       'last_plan': self.last_plans.get(name)} for name in self.voices}

    def destination(self, voice):
        """Restituisce una destinazione compatibile con EnsembleSession."""
        if voice not in self.voices:
            raise ValueError('voce non registrata')

        def deliver(start: float, phrase: Phrase):
            if not math.isfinite(start) or start < 0:
                raise ValueError('beat iniziale non valido')
            ends = {}
            for note in sorted(phrase.notes, key=lambda n: n.beat):
                if note.beat < ends.get(note.pitch, 0):
                    raise ValueError('il player non supporta sovrapposizioni della stessa altezza')
                if round((start + note.beat + note.duration) * 480) <= round((start + note.beat) * 480):
                    raise ValueError('durata inferiore a un tick')
                ends[note.pitch] = note.beat + note.duration
            self._plan(voice, {'start': start, 'revision': self.serial + 1, 'phrase': asdict(phrase)})
        return deliver

    def reset(self, voice):
        self._plan(voice, {'reset': True})

    def control_transport(self, voice, action):
        """Invia un comando Live alla sola voce scelta come sorgente del trasporto."""
        if action not in ('pause', 'resume', 'restart'):
            raise ValueError('comando di trasporto non supportato')
        if not self.connected(voice):
            raise ValueError('collegare la voce del trasporto prima di controllare Live')
        connection = self.connections[voice]
        if 'transport_control' not in connection.get('capabilities', []):
            raise ValueError('aggiornare il device Desnivel_Voice per controllare Live')
        self.serial += 1
        self.send(connection['port'], ADDRESS, {'version': 1, 'kind': 'transport',
                  'voice': voice, 'instance': connection['instance'],
                  'session': self.session, 'serial': self.serial, 'action': action})
