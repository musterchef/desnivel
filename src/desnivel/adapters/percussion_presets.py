"""Conversione esplicita dei preset percussivi con due controlli di sviluppo."""
import math


def migrate_preset(values):
    """Conserva il file originale e segnala i valori sostituiti nello snapshot.

    Il prodotto conserva lo zero di ciascun vecchio controllo. La conversione
    non garantisce identità musicale con il precedente generatore.
    """
    if 'conceptuality' not in values:
        return values, {}
    values = dict(values)
    amount = values.pop('conceptuality')
    variation = values.get('variation')
    for name, value in (('conceptuality', amount), ('variation', variation)):
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f'{name} fuori intervallo nel preset percussivo')
    values['variation'] = amount*variation
    return values, {'removed_controls': {'conceptuality': amount},
                    'variation': {'previous': variation, 'value': values['variation']}}
