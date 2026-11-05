"""Inventario dei controlli Desnivel annunciati dal Live Set aperto."""
from copy import deepcopy
import re
import time

from desnivel.adapters.voice_device import ADDRESS


class LiveDevices:
    def __init__(self, send, *, clock=time.monotonic):
        self.send, self.clock = send, clock
        self.devices = {}
        self.controls = {}

    def observe_control(self, message):
        """Riconosce i controlli già caricati, anche senza il protocollo di inventario."""
        if message.get('action') not in ('hello', 'transport'):
            return
        if (message.get('version') != 1
                or any(not isinstance(message.get(key), str)
                       or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', message[key])
                       for key in ('instance', 'voice'))
                or type(message.get('reply_port')) is not int or not 1024 <= message['reply_port'] <= 65535
                or type(message.get('serial')) is not int or message['serial'] < 0):
            raise ValueError('identità o porta del controllo non valida')
        self.controls[message['instance']] = dict(instance=message['instance'], voice=message['voice'],
                                                  reply_port=message['reply_port'], seen=self.clock())

    def unannounced(self):
        active = {device['instance'] for device in self.available()}
        return [deepcopy(control) for control in self.controls.values()
                if self.clock()-control['seen'] < 3 and control['instance'] not in active]

    def observe(self, message):
        if message.get('version') != 1 or message.get('action') != 'discover':
            raise ValueError('annuncio di device non valido')
        for key in ('device_id', 'instance'):
            if not isinstance(message.get(key), str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', message[key]):
                raise ValueError('identità del device non valida')
        port = message.get('reply_port')
        track = message.get('track')
        if (type(port) is not int or not 1024 <= port <= 65535
                or message.get('device_kind') not in ('voice', 'snake')
                or not isinstance(track, dict) or set(track) != {'name', 'index', 'id'}
                or not isinstance(track['name'], str) or not track['name'].isprintable()
                or type(track['index']) is not int or track['index'] < 0
                or type(track['id']) is not int or track['id'] <= 0):
            raise ValueError('traccia o porta del device non valida')
        self.devices[message['instance']] = {key: deepcopy(message[key]) for key in (
            'device_id', 'instance', 'reply_port', 'track', 'device_kind')}
        self.devices[message['instance']]['seen'] = self.clock()
        self.devices[message['instance']]['playing'] = message.get('playing') == 1

    def available(self):
        devices = [deepcopy(d) for d in self.devices.values() if self.clock()-d['seen'] < 3]
        for device in devices:
            errors = []
            for other in devices:
                if other['instance'] == device['instance']:
                    continue
                if other['device_id'] == device['device_id']:
                    errors.append('identità duplicata: reinserire il controllo copiato')
                if other['reply_port'] == device['reply_port']:
                    errors.append('porta Receive duplicata')
                if other['track']['id'] == device['track']['id']:
                    errors.append('più controlli Desnivel sulla stessa traccia')
            device['error'] = '; '.join(dict.fromkeys(errors)) or None
        return sorted(devices, key=lambda d: (d['track']['index'], d['instance']))

    def find(self, device_id):
        matches = [d for d in self.available() if d['device_id'] == device_id]
        if len(matches) != 1 or matches[0]['error']:
            raise ValueError('device assente o ambiguo: controllare le tracce in Live')
        return matches[0]

    def bind(self, device_id, voice, backend_port):
        device = self.find(device_id)
        self.send(device['reply_port'], ADDRESS, dict(version=1, kind='binding',
                  instance=device['instance'], device_id=device_id, voice=voice, backend_port=backend_port))

    def release(self, device_id):
        device = self.find(device_id)
        self.send(device['reply_port'], ADDRESS, dict(version=1, kind='release',
                  instance=device['instance'], device_id=device_id))
