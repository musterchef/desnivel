# Configurazioni di Desnivel

## Sessione multivoce

La prova corrente usa quattro file, con responsabilità distinte:

| File | Cosa contiene | Chi lo legge |
|---|---|---|
| `organico.json` | Voci, generatori, impostazioni e preset; sezioni manuali; parametri della timeline in beat | `cli.ensemble`; `cli.analyze_trip --timeline-session` per l'anteprima |
| `direzione-viaggio.json` | Tavolozze e motivo automatici, override, assetti delle famiglie e criteri del percorso | `cli.trip_direction`, tramite `direction` della sessione o `--direction` |
| `analisi-percorso.json` | Campionamento per distanza, soglie delle fasce e persistenza | `trip.analysis`, tramite i comandi di analisi o di sessione |
| `macrosezioni-percorso.json` | Appartenenza delle fasce alle famiglie | `trip.sections`, tramite i comandi di analisi o di sessione |

Per modificare una voce o i suoi preset si interviene su `organico.json`.
L'organico principale abilita la guida delle drums, l'adesione regolabile
di melodia e basso e l'influenza ritmica dalle drums precedenti verso la
melodia. Le configurazioni di direzione possono cambiare i parametri
delle sezioni senza sostituire queste relazioni.
Per cambiarne il comportamento in salita, discesa o pianura si interviene su
`direzione-viaggio.json`. I due file di analisi descrivono il percorso e non
contengono decisioni musicali. Aggiungere una voce non richiede un nuovo JSON.

I percorsi `analysis` e `grouping` nella direzione sono relativi al file di
direzione. I criteri possono essere condivisi fra analisi visuale e ascolto.
Il riferimento dei campi e delle precedenze è in
[Configurazione](../doc/CONFIGURAZIONE.md).
`organico.json` carica la direzione tramite il campo
`direction`. Soglie, tavolozze, motivo e override sono descritti in
[Direzione musicale dal percorso](../doc/DIREZIONE-MUSICALE.md).
`--manual-sections` mantiene l'ascolto delle sezioni esplicite del file.

I colpi e i profili percussivi sono definiti una sola volta nel catalogo
`src/desnivel/music/percussion/catalog.py`. La configurazione contiene
riferimenti come `material: "spaced_impacts"` e
`standard_material: "regular_pulse_eighths"`, senza liste di colpi.
La mappa del Drum Rack è in `src/desnivel/adapters/percussion.py`.
Per coordinare la tessitura con la melodia usare **Segui sorgente** nel
device; per gli spostamenti percussivi usare `displacement_beats`.

## Altre configurazioni operative

| File o cartella | Funzione | Riferimento |
|---|---|---|
| `movimento.json`, `sforzo.json`, `misto.json` | Pesi di velocità e stima di sforzo nella composizione `journey.compose` | [Tappe e preset](../doc/TAPPE-E-PRESET.md) |
| `tappe/*.json` | Motivo, sezioni armoniche e parametri temporali per `trip_music --stage-music` | [Tappe e preset](../doc/TAPPE-E-PRESET.md) |
| `quota.json` | Regola a soglia altimetrica per `trip_music --rules` | [Tappe e preset](../doc/TAPPE-E-PRESET.md) |
| `phrases/*.json` | Frasi MIDI esplicite per le prove da file | [Dispositivo di voce](../doc/VOCE-M4L.md) |

Questi file sono usati da comandi distinti dalla sessione `ensemble`.
I JSON in `doc/proposte/` sono bozze di progettazione, non configurazioni
caricate dalla sessione.

## Criteri di organizzazione

- Mantenere i dati della stessa sessione nei rispettivi file di organico e
  direzione; usare i preset interni per le varianti di parametri di una voce.
- Per le varianti della stessa sessione usare controlli e preset utente;
  conservare un solo organico operativo e riferimenti al catalogo musicale.
- Conservare le frasi esplicite in `phrases/` e le configurazioni di tappa
  del relativo comando in `tappe/`.
- Salvare analisi e report generati in `output/`, separati dai preset.
- Accompagnare ogni nuova struttura JSON con significato dei campi,
  unità, limiti e componente che la legge.
