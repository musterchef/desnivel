"""Collega componenti Snake alla sessione esistente, senza un secondo replay."""
import json
import re
import time
from copy import deepcopy
from pathlib import Path

from desnivel.adapters.snake_control import bank_parameters, validate_paths
from desnivel.adapters.voice_device import ADDRESS, ChoiceControl, Control, DeviceVoice
from desnivel.cli.voice_device import VoiceDeviceServer
from desnivel.music.director import MusicalContext
from desnivel.music.phrases import Phrase
from desnivel.music.sequence.material import compose
from desnivel.music.sequence.settings import CONTROLS, CONTROL_LIMITS, ROLES, validate_music
from desnivel.music.sequence.adaptation import PULSES, pulse, rhythm, rhythm_target, targets
from desnivel.music.automation import AdaptiveContext, resolve_parameters
from desnivel.adapters.snake_forecast import SnakeForecast
from desnivel.music.sources import MusicalSource


class SnakeControlSession:
    """Un server per più istanze; ogni componente ha ruolo, sorgente e override propri."""

    def __init__(self, config, sources, *, server_factory=VoiceDeviceServer, clock=time.monotonic):
        if not isinstance(config, dict) or set(config) != {'port', 'components', 'music', 'paths'}:
            raise ValueError('configurazione Snake: port, components, music e paths richiesti')
        if type(config['port']) is not int or not 1024 <= config['port'] <= 65535:
            raise ValueError('porta Snake richiesta fra 1024 e 65535')
        if not isinstance(config['components'], dict) or not config['components']:
            raise ValueError('almeno un componente Snake richiesto')
        validate_music(config['music'])
        validate_paths(config['paths'])
        self.music = deepcopy(config['music'])
        self.paths = tuple(config['paths'])
        self.port = config['port']
        self.clock, self.transport_epoch = clock, None
        self.components = {}
        controls = {**{name: Control(*limits) for name, limits in CONTROL_LIMITS.items()},
                    'pulse': ChoiceControl(tuple((p, p) for p in PULSES)),
                    'mode': ChoiceControl((('autonomous', 'autonomo'), ('coordinated', 'coordinato'))),
                    'source': ChoiceControl(tuple((name, value['name']) for name, value in sources.items()))}
        devices = {}
        for name, spec in config['components'].items():
            if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', name) or not isinstance(spec, dict)
                    or name in sources or set(spec) != {'role', 'mode', 'source'} or spec['role'] not in ROLES
                    or spec['mode'] not in ('autonomous', 'coordinated')
                    or not isinstance(spec['source'], str) or spec['source'] not in sources):
                raise ValueError('componente Snake: identificativo, role, mode e source validi richiesti')
            component = dict(defaults=dict(spec), role=spec['role'], manual_role=None, overrides={},
                             sent=None, instance=None, notice='in attesa della sessione', error=None,
                             automatic={}, automation={}, decisions={}, window=None,
                             forecast=SnakeForecast(clock=clock), hold_until=0., pending=False,
                             source_status='telemetria non disponibile', received_serial=-1)
            self.components[name] = component
            def values(c=component):
                recipe = self.music['roles'][c['role']]
                return {**recipe['parameters'], 'pulse': recipe['pulse']['slowest'], **c['automatic'], 'mode': c['defaults']['mode'],
                        'source': c['defaults']['source'], **c['overrides']}
            def apply(parameters, c=component):
                c['overrides'] = dict(parameters)
            def parameter(key, value, c=component):
                c['overrides'][key] = value
            def manual(key, enabled, c=component, read=values):
                if enabled:
                    c['overrides'][key] = read()[key]
                else:
                    c['overrides'].pop(key, None)
            def role(value, c=component):
                c['manual_role'] = value
                c['role'] = value or c['defaults']['role']
                c['automatic'], c['automation'], c['window'] = {}, {}, None
            def status(c=component):
                return dict(role=c['role'], section_role=c['defaults']['role'],
                            role_mode='manual' if c['manual_role'] else 'section',
                            role_follow_label='ruolo configurato',
                            supported_roles=list(ROLES), active=True, notice=c['notice'])
            devices[name] = DeviceVoice(controls=controls, values=values(), apply=apply,
                read_values=values, apply_parameter=parameter,
                read_manual=lambda key, c=component: key in c['overrides'], apply_manual=manual,
                read_automation=lambda c=component: c['decisions'],
                apply_role=role, role_state=status, describe_controls=lambda role, params: {
                    'source': {'inactive_reason': 'Usata soltanto in modalità coordinata'}
                    if params['mode'] == 'autonomous' else {},
                    'activity': {'label': 'attività dei gate'}, 'length_ms': {'label': 'durata di riferimento (ms)'},
                    'movement': {'label': 'movimento del percorso'}, 'pulse': {'label': 'suddivisione'}})
        self.server = server_factory(devices, config['port'], self.on_message, self.on_error) if server_factory else None
        if self.server:
            self.server.server.timeout = 0

    @classmethod
    def from_file(cls, path, sources, main_port):
        config = json.loads(Path(path).read_text())
        if isinstance(config, dict) and config.get('port') == main_port:
            raise ValueError('porta del controllo Snake e porta della sessione devono essere distinte')
        return cls(config, sources)

    def on_error(self, error):
        print(f'Snake: {error}', flush=True)

    def on_message(self, bridge, message):
        component = self.components[message['voice']]
        if component['instance'] == message['instance'] and message['serial'] <= component['received_serial']:
            return
        component['received_serial'] = message['serial']
        device = message.get('device_state', {})
        if not isinstance(device, dict):
            raise ValueError('stato del componente non valido')
        component['error'] = device.get('error')
        if component['error']:
            component['notice'] = str(component['error'])
        if component['instance'] != message['instance']:
            component['instance'], component['sent'] = message['instance'], None
            component['forecast'] = SnakeForecast(clock=self.clock)
            component['hold_until'] = 0.
        component['ready'] = device.get('ready') is True and 'bank_control' in message.get('capabilities', [])
        if 'bank_control' not in message.get('capabilities', []):
            component['notice'] = 'caricare Desnivel_Snake_Control per controllare i banchi'
        component['applied'] = device.get('applied')
        component['has_instrument'] = device.get('has_instrument') is True if 'has_instrument' in device else None
        component['source_protocol'] = device.get('source_protocol')
        component['forecast'].update(device.get('telemetry'))

    def forecasts(self, start, length_beats, *, beat, bpm, epoch):
        """Sorgenti musicali neutre; una previsione accettata trattiene la revisione dei banchi."""
        self.server.poll()
        if self.transport_epoch != epoch:
            for component in self.components.values():
                component['hold_until'], component['pending'] = 0., False
                if self.transport_epoch is not None:
                    component['forecast'].invalidate('trasporto cambiato: attendo un nuovo stato Snake')
            self.transport_epoch = epoch
        result = {}
        for name, component in self.components.items():
            reason = None
            if not self.server.bridge.connected(name) or not component.get('ready'):
                reason = 'controllo non collegato o non pronto'
            elif component.get('has_instrument') is not True:
                reason = 'strumento non disponibile dopo il controllo'
            elif component['pending']:
                reason = 'aggiornamento dei banchi in attesa delle finestre accettate'
            elif ('payload' not in component or 'Note_01' not in component['payload']['parameters']
                  or component.get('applied') != component['payload']['serial']):
                reason = 'revisione dei banchi non ancora confermata'
            source = (MusicalSource(component['role'], None, unavailable_reason=reason) if reason else
                      component['forecast'].project(component['role'], start, length_beats, beat=beat, bpm=bpm))
            component['source_status'] = source.unavailable_reason or 'previsione disponibile'
            if source.phrase is not None:
                component['hold_until'] = max(component['hold_until'], start+length_beats)
            result[name] = source
        return result

    def setup_missing(self):
        """Distingue collegamento, compatibilità dei banchi e presenza dello strumento."""
        missing = {}
        for name, component in self.components.items():
            if not self.server.bridge.connected(name):
                missing[name] = 'controllo non collegato'
            elif component['error']:
                missing[name] = str(component['error'])
            elif not component.get('ready'):
                missing[name] = 'Snake con Length e controllo compatibile richiesti'
            elif component.get('has_instrument') is None:
                missing[name] = 'aggiorna e ricarica Desnivel_Snake_Control'
            elif not component['has_instrument']:
                missing[name] = 'inserisci uno strumento dopo il controllo'
            elif component.get('source_protocol') != 1:
                missing[name] = 'aggiorna e ricarica Snake e Snake Control con telemetria per istanza'
        return missing

    def _send(self, name, parameters, key):
        bridge = self.server.bridge
        component = self.components[name]
        connection = bridge.connections[name]
        if component['sent'] == key:
            if component.get('applied') == component['payload']['serial']:
                return
        else:
            bridge.serial += 1
            component['payload'] = dict(version=1, kind='parameters', voice=name,
                instance=connection['instance'], session=bridge.session, serial=bridge.serial, parameters=parameters)
            component['sent'] = key
        bridge.send(connection['port'], ADDRESS, component['payload'])

    def tick(self, state):
        self.server.poll()
        bridge = self.server.bridge
        for name, component in self.components.items():
            if not bridge.connected(name) or not component.get('ready'):
                continue
            try:
                if state['state'] != 'playing':
                    component['hold_until'], component['pending'] = 0., False
                    component['source_status'] = 'trasporto fermo · nessuna previsione attiva'
                    self._send(name, {f'Gate_{i:02d}': 0 for i in range(1, 17)}, ('silent',))
                    component['notice'] = 'in attesa di Play · gate silenziati'
                    continue
                current = state.get('planning', {}).get('current')
                if current is None:
                    component['notice'] = 'in attesa del piano corrente'
                    self._send(name, {f'Gate_{i:02d}': 0 for i in range(1, 17)}, ('waiting',))
                    continue
                self._adapt(component, current, state.get('adaptation_enabled', True))
                values = bridge.voices[name].read_values()
                context = MusicalContext(current['section_index'], current['section'], current['root'], current['scale'])
                source = None
                if values['mode'] == 'coordinated':
                    part = current['voices'].get(values['source'])
                    source = Phrase.from_dict(dict(length_beats=current['length_beats'], notes=part['notes'] if part else []))
                material = compose(context,
                    component['role'], {k: values[k] for k in CONTROLS}, phrasing=self.music['phrasing'],
                    motif=(state.get('trip_music') or {}).get('motif_degrees', (0, 2, 4, 1)),
                    source=source, coordinated=values['mode'] == 'coordinated')
                parameters = bank_parameters(material, self.paths)
                key = json.dumps(parameters, sort_keys=True)
                if component['sent'] != key and state.get('transport', {}).get('beat', float('inf')) < component['hold_until']:
                    component['pending'] = True
                    component['notice'] = f"banchi invariati fino al beat {component['hold_until']:g} · nuova interpretazione in attesa"
                    continue
                component['pending'] = False
                self._send(name, parameters, key)
                component['notice'] = f"{component['role']} · {values['mode']}" + (
                    f" · sorgente {values['source']}" if values['mode'] == 'coordinated' else '')
                if component['pulse_notice'] and 'pulse' not in component['overrides']:
                    component['notice'] += ' · '+component['pulse_notice']
                if component['error']:
                    component['notice'] = 'errore device: '+str(component['error'])
            except (ValueError, KeyError, TypeError) as error:
                component['notice'] = f'errore: {error}'
                self._send(name, {f'Gate_{i:02d}': 0 for i in range(1, 17)}, ('error', str(error)))
        return {name: dict(role=c['role'], status=c['notice'], connected=bridge.connected(name),
                          automation=c['decisions'], source_status=c['source_status'], hold_until=c['hold_until'])
                for name, c in self.components.items()}

    def _adapt(self, component, current, enabled):
        """Legge soltanto la finestra in esecuzione; nessuna anticipazione dei piani futuri."""
        key = (current.get('epoch'), current['start'], component['role'], enabled,
               json.dumps(component['overrides'], sort_keys=True))
        if component['window'] == key:
            return
        previous = component['window']
        if previous and (previous[0] != key[0] or previous[1] > key[1]):
            component['automation'] = {}
        recipe = self.music['roles'][component['role']]
        base = recipe['parameters']
        intent = AdaptiveContext(**(current.get('adaptive_context') or {}))
        wanted = targets(component['role'], intent, current['length_beats'], self.music) if enabled else {}
        coupled = enabled and not {'activity', 'pulse'}.intersection(component['overrides'])
        if coupled:
            density = rhythm_target(component['role'], intent, current['length_beats'], self.music)
            # La prima finestra parte dal viaggio; le successive dal valore in corso.
            base = {**base, 'attack_rate': density.value}
            wanted.pop('activity')
            wanted['attack_rate'] = density
        values, states, decisions = resolve_parameters(base, wanted, component['overrides'], component['automation'],
            start=current['start'], logical_start=current.get('logical_start', current['start']),
            scope=(component['role'], current['section_index']))
        if coupled:
            values['activity'], values['pulse'] = rhythm(values['attack_rate'], recipe)
            target_activity, _ = rhythm(density.value, recipe)
            decisions['activity'] = dict(base=recipe['parameters']['activity'], target=target_activity,
                effective=values['activity'], source='adaptive', reason=density.reason,
                transition_beats=density.transition_beats)
        else:
            automatic_pulse = pulse(intent, recipe['pulse']) if enabled else recipe['pulse']['slowest']
            values['pulse'] = component['overrides'].get('pulse', automatic_pulse)
        if not enabled:
            component['pulse_notice'] = 'adattamento disattivato: pulse al limite lento del ruolo'
        elif intent.intensity is None:
            component['pulse_notice'] = 'intensità non disponibile: pulse al limite lento del ruolo'
        else:
            component['pulse_notice'] = ''
        component.update(automatic={k: values[k] for k in CONTROLS}, automation=states,
                         decisions=decisions, window=key)

    def close(self):
        if self.server is None:
            return
        for name in self.components:
            if self.server.bridge.connected(name):
                self._send(name, {f'Gate_{i:02d}': 0 for i in range(1, 17)}, ('closed',))
        self.server.close()
