"""Selettori di file macOS usati dal launcher interattivo."""
from pathlib import Path
import subprocess


def choose_file(prompt, extensions):
    """Selettore macOS per un file esistente; None riporta alla scelta chiamante."""
    result = subprocess.run([
        'osascript', '-e',
        'on run argv\n'
        'try\n'
        'set selectedFile to choose file with prompt (item 1 of argv) '
        'of type (items 2 thru -1 of argv)\n'
        'return POSIX path of selectedFile\n'
        'on error number -128\n'
        'return ""\n'
        'end try\n'
        'end run',
        prompt, *[extension.lstrip('.') for extension in extensions],
    ], capture_output=True, text=True)
    if result.returncode:
        raise ValueError('Impossibile aprire il selettore file: ' + result.stderr.strip())
    selected = result.stdout.strip()
    if not selected:
        return None
    path = Path(selected)
    if path.suffix.lower() not in extensions or not path.is_file():
        raise ValueError('Seleziona un file esistente con estensione '+', '.join(extensions)+'.')
    return path


def choose_track():
    """Apre il selettore FIT/GPX; restituisce None se viene annullato."""
    return choose_file('Seleziona una traccia FIT o GPX', ('.fit', '.gpx'))


