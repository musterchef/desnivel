"""Collegamento fra libreria persistente e controlli esposti dalle voci."""
from functools import partial


def connect_preset_library(library, voices):
    if library.voices.keys()-voices.keys():
        raise ValueError('la libreria contiene voci non presenti nella configurazione')
    for voice, spec in voices.items():
        custom = library.voices.get(voice, {})
        migrated = {}
        if custom.keys() & spec.presets.keys():
            raise ValueError(f'{voice}: un preset utente usa il nome di un preset base')
        for name, values in custom.items():
            if not isinstance(name, str) or not name.strip() or len(name) > 64 or not name.isprintable():
                raise ValueError('nome del preset non valido')
            if not isinstance(values, dict):
                raise ValueError(f'{voice}/{name}: controlli del preset incompatibili con la voce')
            values, changes = spec.migrate_preset(values) if spec.migrate_preset else (values, {})
            missing = spec.controls.keys()-values.keys()
            if values.keys()-spec.controls.keys() or missing-spec.preset_defaults.keys():
                raise ValueError(f'{voice}/{name}: controlli del preset incompatibili con la voce')
            values = {**{key: spec.preset_defaults[key] for key in missing}, **values}
            for key, value in values.items():
                spec.controls[key].validate(value)
            migrated[name] = values
            if missing or changes:
                spec.preset_migrations[name] = {**changes, **{key: values[key] for key in sorted(missing)}}
        spec.presets.update(migrated)
        spec.editable_presets = set(custom)
        spec.save_preset = partial(library.save, voice)
