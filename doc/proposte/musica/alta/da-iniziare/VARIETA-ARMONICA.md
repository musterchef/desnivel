# Varietà armonica tra le tappe

Stato: proposta, non implementata. Scadenza di lavorazione: novembre 2026.

## Problema

Con la configurazione attuale di `presets/direzione-viaggio.json` le 12 tappe usano solo 9 coppie tonica/scala, distribuite in 3 palette da 3 contesti ciascuna:

| Palette | Pendenza media | Contesti (home / related / colour) | Tappe |
|---|---|---|---|
| `gentle` | sotto il 3% | 50 major / 57 mixolydian / 50 lydian | 01, 02, 07, 08, 09, 10, 12 |
| `rolling` | dal 3% al 4% | 55 dorian / 50 minor / 55 mixolydian | 03, 05, 06, 11 |
| `steep` | dal 4% | 52 minor / 59 phrygian / 52 dorian | 04 |

Sette tappe su dodici condividono la stessa palette e quindi le stesse tinte armoniche. Il motivo melodico è diverso in tutte le tappe, mentre l'armonia tende a risultare uniforme.

## Leve possibili

1. Aggiungere palette o soglie di pendenza più fini, così da separare meglio le tappe `gentle`.
2. Assegnare contesti diversi a ciascuna palette.
3. Verificare l'effetto all'ascolto e con i test di direzione.

Nessuna di queste leve è stata scelta né implementata.

## Riferimenti

- Configurazione: `presets/direzione-viaggio.json`, blocco `automatic_music`.
- Selezione della palette: `select_palette` in `src/desnivel/music/harmony.py`.
- Calcolo dello stato per sezione: `src/desnivel/cli/trip_direction.py`.
