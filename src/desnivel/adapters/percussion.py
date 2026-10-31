"""Mappa dei ruoli musicali sui pad del Drum Rack della prova di ascolto."""
from types import MappingProxyType

from desnivel.music.percussion.catalog import HIT_ROLES


PAD_NOTES = MappingProxyType({
    'kick': 36,
    'rim': 37,
    'snare': 38,
    'clap': 39,
    'kick_alt': 40,
    'snare_alt': 41,
    'hat': 42,
    'snare_alt_2': 43,
    'tom_low': 44,
    'tom_mid': 45,
    'hat_open': 46,
    'tom_high': 47,
    'crash': 48,
    'crash_alt': 49,
    'ride': 50,
    'ride_alt': 51,
})

if set(PAD_NOTES) != set(HIT_ROLES) or len(set(PAD_NOTES.values())) != len(PAD_NOTES):
    raise ValueError('mappa percussiva incompleta o con pad duplicati')
