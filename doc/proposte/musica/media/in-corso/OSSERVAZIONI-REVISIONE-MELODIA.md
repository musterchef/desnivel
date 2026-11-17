# Osservazioni emerse durante la revisione melodica

Stato: da rivedere separatamente; non fa parte della semplificazione melodica.

## Ruoli dichiarati da `MotifGenerator`

[`generator.py`](../../../../../src/desnivel/music/melodic/generator.py)
dichiara i ruoli `melody`,
`bass_line` e `harmony`. Nel codice attuale sviluppa il motivo per `melody`,
mantiene la forma letterale per `bass_line` e delega `harmony` a
[`TextureGenerator`](../../../../../src/desnivel/music/texture/generator.py).
I preset [`organico.json`](../../../../../doc/archivio/organico.json) e
[`direzione-viaggio.json`](../../../../../presets/direzione-viaggio.json)
assegnano effettivamente questi ruoli.

Questa osservazione segnala soltanto una responsabilità condivisa nel
generatore melodico. **Non propone di eliminare `bass_line` o `harmony`.**
L'eventuale separazione dei moduli, o la scelta di mantenere l'implementazione
attuale, va valutata a parte senza cambiare l'organico né il comportamento
musicale in questa revisione.
