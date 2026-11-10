"""Collegamento dei componenti esterni alla sessione e al server comuni."""
from copy import deepcopy

from desnivel.cli.snake_control import SnakeControlSession


def snake_session(config, *, previous=None):
    definition = config.get('snake')
    if definition is None:
        return None
    if not isinstance(definition, dict) or set(definition) != {'components', 'music', 'paths'}:
        raise ValueError('Snake nella sessione richiede components, music e paths')
    sources = {name: {'name': spec.get('name', name)} for name, spec in config['voices'].items()}
    session = SnakeControlSession({'port': 9006, **definition}, sources, server_factory=None)
    if previous:
        for name in session.components.keys() & previous.components.keys():
            old = previous.components[name]
            if old['defaults'] == session.components[name]['defaults']:
                for key, value in old['overrides'].items():
                    session.devices[name].controls[key].validate(value)
                session.components[name].update(deepcopy(old))
    return session


class LiveComponents:
    """Adattatori Live e preparazione dei componenti, esterni al controllo generico."""

    def __init__(self, config, config_path, port, *, previous=None, guide=None):
        from pathlib import Path
        self.session = snake_session(config, previous=previous)
        self.config_path, self.port = Path(config_path), port
        self.guided = 'arrangement' in config
        self.guide = guide
        self.names = dict(config.get('component_names', {}))

    @property
    def voices(self):
        return self.session.devices if self.session else {}

    @property
    def waiting(self):
        return bool(self.guide and self.guide.waiting)

    def candidate(self, config):
        return LiveComponents(config, self.config_path, self.port, previous=self.session, guide=self.guide)

    def attach(self, runtime):
        if self.guide is None:
            from desnivel.cli.snake_setup import SnakeSetup
            self.guide = SnakeSetup(self.config_path.parent/'snake.json', runtime.voice_descriptions, self.port)
        else:
            self.guide.sources = runtime.voice_descriptions
        self.guide.can_change_role = runtime.can_change_role
        if self.guide.session is not None:
            self.guide.session.bridge.can_change_role = self.guide.can_change_role
        if self.session:
            self.session.attach_bridge(runtime.bridge)
            for name in self.voices:
                runtime.voice_descriptions[name]['name'] = self.names.get(name, name)
        runtime.external_source_provider = self.forecasts

    def forecasts(self, *args, **kwargs):
        return (self.session or self.guide).forecasts(*args, **kwargs)

    def prepare(self, *, playing, recording_busy):
        self.guide.begin(playing=playing, recording_busy=recording_busy)

    def confirm(self):
        self.guide.confirm()

    def cancel(self):
        self.guide.cancel()

    def on_message(self, bridge, message):
        if self.session and message['voice'] in self.session.components:
            self.session.on_message(bridge, message)

    def tick(self, state):
        return (self.session or self.guide).tick(state)

    def setup_state(self):
        return self.guide.snapshot() if not self.guided and self.guide.status != 'idle' else None

    def close(self):
        if self.session:
            self.session.close()
        if self.guide:
            self.guide.close()
