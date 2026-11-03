"""Traduzione di celle musicali nei banchi della mod Snake con Length."""
from desnivel.music.sequence.material import SequenceMaterial
from desnivel.adapters.snake_sequence import SHAPES, SPEEDS

LANES = ('Notes', 'Gates', 'Velocities')
# Dal percorso lineare a serpentine, spirale e diagonali, secondo il movimento.
PATHS = (1, 7, 5, 11, 9)


def bank_parameters(material: SequenceMaterial):
    if any(len(values) != 16 for values in (material.notes, material.gates, material.velocities, material.lengths_ms)):
        raise ValueError('Snake richiede 16 celle per banco')
    # In Chromatic/C il parametro nota di Snake è MIDI - 24.
    if any(type(n) is not int or not 24 <= n <= 107 for n in material.notes):
        raise ValueError('Snake in chromatic/c supporta note MIDI da 24 a 107')
    low, high = min(material.lengths_ms), max(material.lengths_ms)
    if not 10 <= low <= high <= 10000:
        raise ValueError('durate Snake richieste fra 10 e 10000 ms')
    result = {'Scales': 0, 'Length_Min_ms': low, 'Length_Max_ms': high}
    shape = PATHS[min(len(PATHS)-1, int(material.movement*len(PATHS)))]
    speed = next(i for i, step in enumerate(SPEEDS.values()) if float(step) == material.step_beats)
    for lane in LANES:
        prefix = f'{lane}_Sequencer_'
        result.update({prefix+'Snake_Shape': shape-1, prefix+'Speed': speed,
                       prefix+'Length': 16, prefix+'Direction': 0, prefix+'Steps_Shift': 1})
    for i, (note, gate, velocity, length) in enumerate(zip(
            material.notes, material.gates, material.velocities, material.lengths_ms), 1):
        # Il materiale è in ordine musicale: collocarlo lungo il percorso scelto.
        # Length viene letto dalla stessa cella di Notes nella mod esistente.
        suffix = f'{SHAPES[shape-1][i-1]+1:02d}'
        result.update({f'Note_{suffix}': note-24, f'Gate_{suffix}': gate,
                       f'Velocity_{suffix}': velocity,
                       f'Length_{suffix}': round((length-low)/(high-low)*127) if high > low else 0})
    return result
