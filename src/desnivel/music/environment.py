"""Traduzione musicale del meteo; le misure fisiche rimangono nel viaggio."""
from dataclasses import replace

from desnivel.music.automation import AdaptiveContext, bounded


def weather_intent(context, description):
    """Vento assoluto per la dinamica, variazione oraria della pioggia per lo sviluppo.

    Nessuna normalizzazione relativa alla singola tappa: condizioni uguali danno
    indicazioni uguali. Canali incompleti rimangono indisponibili separatamente.
    """
    channels = description['channels']
    def complete(name):
        channel = channels[name]
        return channel['value'] if channel['status'] == 'available' else None
    wind = complete('wind_speed_kmh')
    # Si aggrega il modulo del cambiamento: aumenti e diminuzioni simultanei
    # in porzioni diverse della finestra non devono cancellarsi fra loro.
    rain = complete('precipitation_change_mm')
    if rain is not None:
        records = description['records']
        weight = sum(r['weight'] for r in records)
        rain = sum(r['weight']*abs(r['values']['precipitation_change_mm']) for r in records)/weight
    return replace(context or AdaptiveContext(),
                   dynamic_pressure=None if wind is None else bounded(wind/40., 0, 1),
                   material_change=None if rain is None else bounded((rain-.2)/1.8, 0, 1))
