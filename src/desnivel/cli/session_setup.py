"""Configurazione guidata delle voci e delle destinazioni Live, a trasporto fermo."""
from copy import deepcopy
import json
from pathlib import Path
import shlex
from uuid import uuid4

from desnivel.cli.session_config import save_configuration


class SessionSetup:
    def __init__(self, config, path, devices, apply, can_edit, *, port=9006):
        self.config, self.path = deepcopy(config), Path(path)
        self.devices, self.apply, self.can_edit, self.port = devices, apply, can_edit, port
        self.step = None
        self.pending = {}
        self.options = []
        self.notice = 'Associa una traccia del set per aggiungere una voce musicale.' if not config['voices'] else ''
        self.next_bind = 0.

    @property
    def waiting(self):
        return self.step is not None

    def cancel(self):
        self.step, self.pending, self.options = None, {}, []
        self.notice = 'Preparazione annullata.'

    def _question(self, step, notice, options=()):
        self.step, self.notice, self.options = step, notice, list(options)
        if step == 'destination':
            self._refresh_destinations()

    def _refresh_destinations(self):
        known = {device['device_id'] for device in self.options}
        bound = set(self.config.get('live_bindings', {}).values())
        for device in self.devices.available():
            if not device['error'] and device['device_id'] not in bound and device['device_id'] not in known:
                self.options.append(device)
                known.add(device['device_id'])

    def _choice(self, text):
        if not text.isdecimal() or not 1 <= int(text) <= len(self.options):
            raise ValueError('scegli un numero fra quelli elencati')
        return self.options[int(text)-1]

    def _commit(self, candidate):
        self.can_edit()
        self.apply(candidate)
        previous = set(self.config.get('live_bindings', {}).values())
        current = set(candidate.get('live_bindings', {}).values())
        self.config = candidate
        self.step, self.pending, self.options = None, {}, []
        self.next_bind = 0.
        self.notice = 'Configurazione applicata. Puoi associare un’altra traccia o salvare la sessione.'
        for device_id in previous-current:
            try:
                self.devices.release(device_id)
            except ValueError:
                pass  # Un device assente non può ricevere il rilascio.

    def submit(self, text):
        text = text.strip()
        if text == 'annulla':
            self.cancel()
            return
        if self.waiting:
            self.can_edit()
            self._answer(text)
            return
        parts = shlex.split(text)
        if parts == ['tracce']:
            self.notice = 'Ricerca dei controlli Desnivel nel set aperto. Le tracce compaiono appena rispondono.'
        elif parts == ['associa']:
            self.can_edit()
            if not self._voices():
                raise ValueError('non ci sono ancora voci da ricollegare: associa la prima traccia')
            self._question('existing_voice', 'Quale voce vuoi ricollegare?', self._voices())
        elif parts == ['salva']:
            save_configuration(self.path, self.config)
            self.notice = f'Configurazione salvata: {self.path}'
        elif parts == ['aggiungi', 'traccia'] or len(parts) == 2 and parts[0] == 'associa':
            self.can_edit()
            if 'arrangement' not in self.config:
                raise ValueError('la creazione guidata richiede una sessione dinamica: avvia il launcher senza --config organico')
            self.pending = {}
            if parts[0] == 'associa':
                if parts[1] not in self._voices():
                    raise ValueError('voce sconosciuta')
                self.pending['voice'] = parts[1]
            self._question('destination', 'Scegli una traccia disponibile oppure 0 per prepararla in Live.')
        elif len(parts) == 2 and parts[0] == 'rimuovi':
            self.can_edit()
            name = parts[1]
            if name not in self._voices():
                raise ValueError('voce sconosciuta')
            dependents = [key for key, spec in self.config['voices'].items() if name in
                          spec.get('dependencies', [])+spec.get('optional_dependencies', [])]
            references = [r['id'] for r in self.config.get('relations', []) if name in (r['source'], r['target'])]
            dependents += [key for key, spec in self.config.get('snake', {}).get('components', {}).items()
                           if spec['source'] == name]
            if dependents or references:
                raise ValueError('voce ancora usata da: '+', '.join(dependents+references))
            if self.config.get('rhythm_voice') == name:
                raise ValueError('scegli prima un’altra sorgente ritmica con :ritmo <voce|nessuna>')
            candidate = deepcopy(self.config)
            removed = candidate['voices'].pop(name, None)
            candidate.get('live_bindings', {}).pop(name, None)
            candidate.get('component_names', {}).pop(name, None)
            candidate.get('arrangement', {}).pop(name, None)
            for section in candidate.get('sections', []):
                section.get('assignments', {}).pop(name, None)
            if removed and not any(v['generator'] == removed['generator'] for v in candidate['voices'].values()):
                candidate['generators'].pop(removed['generator'])
            if not removed:
                candidate['snake']['components'].pop(name)
                if not candidate['snake']['components']:
                    candidate.pop('snake')
            if candidate['transport_voice'] == name:
                candidate['transport_voice'] = next(iter(self._voices(candidate)), None)
            self._commit(candidate)
        elif len(parts) == 2 and parts[0] in ('trasporto', 'ritmo'):
            self.can_edit()
            name = parts[1]
            candidate = deepcopy(self.config)
            if parts[0] == 'ritmo' and name == 'nessuna':
                candidate.pop('rhythm_voice', None)
            else:
                if name not in self._voices(candidate):
                    raise ValueError('voce sconosciuta')
                candidate['transport_voice' if parts[0] == 'trasporto' else 'rhythm_voice'] = name
            self._commit(candidate)
        else:
            self.notice = ('Comandi: tracce · aggiungi traccia · associa <id voce> · rimuovi <id voce> · '
                           'trasporto <id voce> · ritmo <id voce|nessuna> · salva · annulla')

    def _answer(self, text):
        if self.step == 'existing_voice':
            self.pending = {'voice': self._choice(text)}
            self._question('destination', 'Scegli la nuova traccia per questa voce.')
        elif self.step == 'destination':
            if text == '0':
                self._question('destination', 'Per una traccia già presente, scegli il suo numero nell’elenco. '
                               'Per crearne una nuova: in Live crea una traccia MIDI e inserisci Desnivel_Voice prima dello strumento. '
                               'Per Snake: Snake → Desnivel_Snake_Control → strumento. Poi scegli la traccia rilevata.')
                return
            device = self._choice(text)
            device = self.devices.find(device['device_id'])
            self.pending['device'] = device
            if 'voice' in self.pending:
                expected = 'snake' if self.pending['voice'] in self.config.get('snake', {}).get('components', {}) else 'voice'
                if device['device_kind'] != expected:
                    raise ValueError('tipo di controllo incompatibile con la voce')
                candidate = deepcopy(self.config)
                candidate.setdefault('live_bindings', {})[self.pending['voice']] = device['device_id']
                self._commit(candidate)
            else:
                self._question('name', f"Nome della voce; lascia vuoto per usare {device['track']['name']}.")
        elif self.step == 'name':
            name = text or self.pending['device']['track']['name']
            if not name or len(name) > 100 or not name.isprintable():
                raise ValueError('nome della voce richiesto, massimo 100 caratteri')
            self.pending['name'] = name
            roles = ['melody', 'bass_line', 'sustained_texture']
            if self.pending['device']['device_kind'] != 'snake':
                roles.append('percussion')
            self._question('voice', 'Quale voce musicale vuoi aggiungere?', roles)
        elif self.step == 'voice':
            self.pending['role'] = self._choice(text)
            if self.pending['device']['device_kind'] == 'snake':
                options = [('autonomous', 'autonomo'), ('coordinated', 'in relazione a una voce')]
            else:
                options = {
                    'melody': [('motif', 'sviluppo di un motivo')],
                    'bass_line': [('motif', 'autonomo'), ('responsive_line', 'in relazione a una voce')],
                    'sustained_texture': [('sustained_texture', 'segue l’armonia della sezione'),
                                          ('texture_follow', 'segue una voce')],
                    'percussion': [('percussion_pattern', 'pattern autonomo'),
                                   ('percussion_phrase', 'in relazione ad altre voci')],
                }[self.pending['role']]
            if not self.config['voices']:
                options = [option for option in options if option[0] not in (
                    'responsive_line', 'texture_follow', 'percussion_phrase', 'coordinated')]
            if len(options) == 1:
                self._select_behavior(options[0][0])
            else:
                self._question('behavior', 'Come deve comportarsi questa voce?', options)
        elif self.step == 'behavior':
            self._select_behavior(self._choice(text)[0])
        elif self.step == 'source':
            self.pending['dependencies'] = [self._choice(text)]
            self._add()
        elif self.step == 'texture_source':
            self.pending['optional_dependencies'] = [self._choice(text)]
            self.pending['definition'].setdefault('settings', {})['follow_source'] = 1
            self._add()
        elif self.step == 'support':
            self.pending['definition']['interaction']['support_source'] = self._choice(text)
            self._question('answer', 'Scegli la sorgente delle risposte percussive.', list(self.config['voices']))
        elif self.step == 'answer':
            sources = self.pending['definition']['interaction']
            sources['answer_source'] = self._choice(text)
            self.pending['dependencies'] = list(dict.fromkeys(sources.values()))
            self._add()
        elif self.step == 'snake_source':
            self.pending['source'] = self._choice(text)
            self._add()

    def _select_behavior(self, behavior):
        voices = list(self.config['voices'])
        if behavior in ('responsive_line', 'texture_follow', 'percussion_phrase', 'coordinated') and not voices:
            raise ValueError('questo comportamento richiede una voce sorgente già presente')
        if self.pending['device']['device_kind'] == 'snake':
            self.pending['mode'] = behavior
            if behavior == 'coordinated':
                self._question('snake_source', 'Scegli la voce sorgente.', voices)
            else:
                self.pending['source'] = 'none'
                self._add()
            return
        kind = 'sustained_texture' if behavior == 'texture_follow' else behavior
        if kind == 'percussion_pattern':
            from desnivel.adapters.percussion import PAD_NOTES
            from desnivel.music.percussion.catalog import reference_material
            definition = dict(type=kind, lanes=dict(PAD_NOTES),
                              patterns=[reference_material('regular_pulse_eighths').pattern()])
        else:
            template = json.loads((Path(__file__).resolve().parents[3]/'presets/organico.json').read_text())
            definition = next(deepcopy(s) for s in template['generators'].values() if s['type'] == kind)
        # Il seguito del groove richiede una sorgente ritmica scelta esplicitamente.
        if 'groove_follow' in definition.get('settings', {}):
            definition['settings']['groove_follow'] = 0.
        self.pending['definition'] = definition
        if behavior == 'responsive_line':
            self._question('source', 'Scegli la voce sorgente.', voices)
        elif behavior == 'texture_follow':
            self._question('texture_source', 'Quale voce deve seguire la nota sostenuta?', voices)
        elif behavior == 'percussion_phrase':
            self._question('support', 'Scegli la sorgente di supporto ritmico.', voices)
        else:
            self._add()

    def _voices(self, config=None):
        config = self.config if config is None else config
        return {**config['voices'], **{name: {'name': config.get('component_names', {}).get(name, name)}
                                      for name in config.get('snake', {}).get('components', {})}}

    def _add(self):
        self.devices.find(self.pending['device']['device_id'])
        candidate = deepcopy(self.config)
        name = 'voice_'+uuid4().hex[:12]
        if self.pending['device']['device_kind'] == 'snake':
            if 'snake' not in candidate:
                candidate['snake'] = json.loads((Path(__file__).resolve().parents[3]/'presets/snake.json').read_text())
                candidate['snake'].pop('port')
                candidate['snake']['components'] = {}
            candidate['snake']['components'][name] = {key: self.pending[key] for key in ('role', 'mode', 'source')}
            candidate.setdefault('component_names', {})[name] = self.pending['name']
        else:
            candidate['generators'][name] = self.pending['definition']
            candidate['voices'][name] = dict(name=self.pending['name'], generator=name, destination=name,
                                         **{k: self.pending[k] for k in ('dependencies', 'optional_dependencies') if k in self.pending})
            candidate['arrangement'][name] = {'role': self.pending['role']}
        candidate.setdefault('live_bindings', {})[name] = self.pending['device']['device_id']
        if candidate['transport_voice'] is None:
            candidate['transport_voice'] = name
        self._commit(candidate)
        self.notice = f"{self._voices()[name]['name']} associata. Puoi associare un’altra traccia o salvare la sessione."

    def tick(self, now):
        if now < self.next_bind:
            return
        self.next_bind = now+1.
        for voice, device_id in self.config.get('live_bindings', {}).items():
            try:
                self.devices.bind(device_id, voice, self.port)
            except ValueError:
                continue  # Assenze e conflitti sono esposti nell'inventario.

    def snapshot(self, voices=None):
        bindings = self.config.get('live_bindings', {})
        devices = self.devices.available()
        names = self._voices()
        if self.step == 'destination':
            self._refresh_destinations()
        tracks = []
        for device in devices:
            voice = next((name for name, uid in bindings.items() if uid == device['device_id']), None)
            choice = next((i for i, option in enumerate(self.options, 1)
                           if self.step == 'destination' and option['device_id'] == device['device_id']), None)
            connected = bool(voices and voices.get(voice, {}).get('connected'))
            status = ('conflict' if device['error'] else 'connected' if voice and connected else
                      'connecting' if voice else 'available')
            tracks.append(dict(name=device['track']['name'], position=device['track']['index']+1,
                               kind=device['device_kind'], status=status, choice=choice if status == 'available' else None,
                               voice_name=names[voice]['name'] if voice else None, reason=device['error']))
        present = {device['device_id'] for device in devices}
        for voice, uid in bindings.items():
            if uid not in present:
                tracks.append(dict(name=names[voice]['name'], position=None, kind=None, status='missing',
                                   choice=None, voice_name=names[voice]['name'], reason='controllo non rilevato in Live'))
        legacy = self.devices.unannounced()
        for control in legacy:
            tracks.append(dict(name='voce salvata: '+control['voice'], position=None, kind=None,
                               status='update_required', choice=None, voice_name=None,
                               reason='aggiornare e ricaricare il controllo nella traccia'))
        if self.step == 'destination':
            for i, device in enumerate(self.options, 1):
                if device['device_id'] not in present:
                    tracks.append(dict(name=device['track']['name'], position=None, kind=device['device_kind'],
                                       status='missing', choice=i, voice_name=None, reason='traccia non più disponibile'))
        labels = {'melody': 'melodia', 'bass_line': 'basso', 'sustained_texture': 'nota sostenuta',
                  'percussion': 'drums', 'autonomous': 'autonoma', 'coordinated': 'coordinata', 'nessuna': 'nessuna'}
        choices = []
        if self.step != 'destination':
            for i, option in enumerate(self.options, 1):
                label = (option[1] if isinstance(option, tuple) else names[option]['name'] if option in names
                         else labels.get(option, option))
                choices.append(dict(value=str(i), label=label))
        diagnostics = []
        if legacy:
            diagnostics.append('I controlli rispondono ma non inviano l’inventario: aggiorna i device nella User Library e ricaricali in Live.')
        elif not devices:
            diagnostics.append('In attesa di Live. Se i controlli sono già nelle tracce, verifica che siano aggiornati e ricaricati.')
        diagnostics.extend(dict.fromkeys(device['error'] for device in devices if device['error']))
        return dict(kind='guided',
                    status='waiting' if self.waiting else 'idle', step=self.step,
                    notice=self.notice, tracks=tracks, choices=choices, diagnostics=diagnostics,
                    counts=dict(detected=len(devices), available=sum(t['status'] == 'available' for t in tracks),
                                associated=len(bindings), connected=sum(t['status'] == 'connected' for t in tracks),
                                update_required=len(legacy)), next_check_s=None)
