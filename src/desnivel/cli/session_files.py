"""Percorsi e nomi delle configurazioni utente di sessione."""
import re


def saved_sessions(root):
    """Elenca le configurazioni utente, escludendo le librerie dei preset voce."""
    directory = root/'output/sessioni'
    paths = [path for path in directory.glob('*.json')
             if path.is_file() and not path.name.casefold().endswith('.voice-presets.json')]
    single = root/'output/sessione.json'
    if single.is_file():
        paths.append(single)
    return sorted(paths, key=lambda path: (path.stem.casefold(), str(path)))


def new_session_path(root, name):
    name = name.strip()
    if (not re.fullmatch(r'\w[\w .-]{0,79}', name) or name.endswith('.')
            or name.casefold().endswith(('.voice-presets', '.json'))):
        raise ValueError('Usa un nome da 1 a 80 caratteri: lettere, numeri, spazi, punti o trattini, senza estensione.')
    path = root/'output/sessioni'/f'{name}.json'
    if path.exists():
        raise ValueError(f'La sessione «{name}» esiste già: scegli un altro nome oppure caricala dal menu.')
    return path


