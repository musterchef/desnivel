# Direzione musicale dal percorso

La direzione automatica sceglie tavolozza armonica e materiale melodico
prima della sessione, usando il profilo GPX analizzato. Le macrosezioni
conservano organico, presenza e parametri delle famiglie configurate;
root e scala risolte sono condivise da tutte le voci.

## Avvio

`organico.json` contiene
`"direction": "direzione-viaggio.json"`, relativo alla cartella del file.
La direzione viene quindi caricata anche senza un'opzione aggiuntiva:

```sh
.venv/bin/python -m desnivel.cli.ensemble \
  --gpx gpx/tappa05_Firenze_San_Gimignano.gpx \
  --config presets/organico.json --speed 50
```

`--direction altro.json` prevale sul percorso configurato.
`--manual-sections` usa invece `sections` del file di sessione e il materiale
originale dei generatori. Le due opzioni si escludono. La modalità
`--timing allocated` richiede una direzione configurata o esplicita e non
accetta `--speed`. `--dry-run` verifica tutte le sezioni senza inviare note.

## Profilo e tavolozza

`trip/profile.py` usa le finestre dell'analisi esistente:

- Media della pendenza assoluta, pesata per distanza: somma di
  `abs(slope_ratio) × lunghezza finestra`, divisa per la distanza totale.
- Quota media in otto intervalli di uguale distanza, pesata per le porzioni
  di finestra comprese in ciascun intervallo.
- Forma normalizzata tra minimo e massimo di queste otto quote; su un
  profilo costante tutti i valori sono 0,5.

I dati derivano dai tratti osservati. Non vengono introdotti collegamenti
altimetrici attraverso le interruzioni escluse dal loader. Il nome del file
non determina le scelte musicali; l'identificativo della tappa serve agli override.

La media della pendenza assoluta seleziona una tavolozza da
`automatic_music.palettes`, usando soglie crescenti. La configurazione corrente è:

| Tavolozza | Pendenza assoluta media | Contesti disponibili, con intensità 0 / 0,5 / 1 |
|---|---|---|
| `gentle` | Da 0 a meno del 3% | Re maggiore (root 50), La misolidio (57), Re lidio (50) |
| `rolling` | Dal 3% a meno del 4% | Sol dorico (55), Re minore (50), Sol misolidio (55) |
| `steep` | Dal 4% | Mi minore (52), Si frigio (59), Mi dorico (52) |

Sono scelte compositive modificabili, non classificazioni universali del
terreno o relazioni naturali fra pendenza e tonalità. Percorsi con
caratteristiche simili possono condividere una tavolozza.

## Evoluzione nelle macrosezioni

Per ogni macrosezione viene misurata la pendenza assoluta media locale.
L'intensità obiettivo è `min(1, media_locale / (2 × media_tappa))`;
con media della tappa nulla vale zero. Salite e discese di pari intensità
possono quindi condividere un contesto armonico, mantenendo diversi i
parametri ritmici degli assetti di famiglia.

`music/harmony.py` confronta l'obiettivo con l'intensità dei contesti della
tavolozza. Il punteggio è distanza dall'obiettivo più
`0,15 × (1 − proporzione di classi di altezza comuni al contesto precedente)`.
La proporzione usa come denominatore la maggiore delle due dimensioni.
A parità prevale l'ordine configurato. Un nuovo contesto viene scelto solo
se migliora il punteggio oltre `switch_margin`, attualmente 0,15.

I contesti automatici di una tavolozza devono condividere almeno tre classi
di altezza per ogni coppia. La scelta usa root e scala; non introduce accordi,
cadenze armoniche o cambi di BPM. I confini rimangono quelli delle macrosezioni.

## Materiale melodico

`music/melodic/route.py` quantizza ciascun valore della forma normalizzata
con `floor(valore × span_degrees + 0,5)`. La configurazione usa otto punti
e `span_degrees: 6`, quindi otto gradi tra 0 e 6. Il motivo risultante
sostituisce `degrees` nei generatori elencati in `automatic_music.motif.generators`,
attualmente `motif`. Devono essere generatori di tipo `motif` registrati.

Il materiale è costante per la tappa e viene sviluppato dal
[generatore melodico](MELODIA.md). Il suo suono cambia anche con i contesti
armonici delle macrosezioni. Il GPX non impone nota per nota il profilo alla
melodia durante l'esecuzione.

## Contesto locale delle finestre

`prepare_trip_config` conserva l'analisi neutra in `trip_analysis`.
`cli/window_context.py` associa ogni finestra futura al tratto rappresentato;
`trip/local_context.py` riassume le finestre di pendenza già analizzate.
Il risultato è esposto in `decisions.coordinator.local_trip`.
Non modifica ancora i parametri dei generatori.

- **Allocated:** la distanza di una macrosezione è distribuita uniformemente
  fra le finestre assegnate. `Timeline.position` fornisce sezione e frazione
  interna, usate anche dalla progressione del runtime. Il report di analisi
  con `--timeline-session` usa la stessa funzione di contesto e include
  `timeline.window_contexts` nel risultato JSON.
- **Linear:** l'inizio sorgente è `tempo attivo corrente + anticipo in
  beat × 60 / BPM × speed`. La durata sorgente è `window_beats × 60 / BPM
  × speed`. È una proiezione con il BPM osservato corrente, mantenuto
  costante sull'intervallo futuro; i piani accettati non vengono riscritti
  se il BPM cambia. Senza BPM lo stato dichiara `tempo_unavailable`.

`parts` conserva separatamente ogni tratto registrato attraversato, con
estremi di distanza, tempo attivo e tempi sorgente se disponibili in
`TrackSegment`. La corrispondenza non interpola fra tratti interrotti.
Gli intervalli lineari che superano la fine del viaggio sono segnalati
da `truncated_at_finish`; quelli completamente esterni sono indisponibili.

| Misura locale | Calcolo |
|---|---|
| `slope_ratio` | Media delle pendenze smussate pesata per la distanza coperta |
| `mean_absolute_slope_ratio` | Stessa media sui valori assoluti |
| `slope_change_ratio` | Differenza dalla media del tratto immediatamente precedente, di pari lunghezza; disponibile soltanto con copertura completa nello stesso tratto registrato |
| `zone_persistence_m` | Distanza dall'inizio della zona confermata al punto medio dell'intervallo rappresentato |

Il contesto conserva copertura, zone e tratti attraversati, passo di
campionamento e finestra spaziale della pendenza. Zero e misura non
disponibile restano distinti. Senza analisi collegata, `profile` dichiara
`analysis_not_configured`. Non vengono introdotti descrittori locali di
velocità, fatica o volume audio.

## Override

Nel file `presets/direzione-viaggio.json`, dentro `automatic_music`:

```json
"override": {},
"stage_overrides": {
  "tappa_05": {
    "palette": "rolling",
    "root": 62,
    "scale": "dorian",
    "motif_degrees": [0, 1, 3, 2]
  }
}
```

Ogni campo è facoltativo. Per esempio, impostare soltanto `palette` conserva
l'evoluzione automatica al suo interno e il motivo del percorso. Impostare
`root` o `scale` li fissa per tutta la tappa; il materiale rimane automatico
se `motif_degrees` è omesso. Per tornare all'automatismo basta rimuovere il campo.
Le modifiche al file richiedono un nuovo avvio del processo Python.

`override` vale per tutte le tappe. `stage_overrides` usa il valore `Track.stage_id`,
visibile nello stato, e prevale sui campi generali. Per root e scala l'ordine è:

1. Contesto automatico della macrosezione.
2. Eventuali `root` e `scale` esplicite nell'assetto della famiglia.
3. Campi di `automatic_music.override`.
4. Campi di `automatic_music.stage_overrides.<stage_id>`.

Gli override armonici espliciti possono cambiare anche la compatibilità
fra sezioni: rappresentano una scelta dell'utente. I parametri dei singoli
generatori mantengono le precedenze esistenti di sezione, preset e controlli.

## Contratti e diagnostica

Il file di direzione richiede `analysis`, `grouping`, `families` e,
per l'automatismo, `automatic_music`. Quest'ultimo richiede:

| Campo | Vincoli |
|---|---|
| `palettes` | Lista non vuota; id distinti, soglie crescenti e prima soglia zero |
| `palettes[].states` | Contesti con id e intensità distinti; root MIDI 0…127 e scala registrata |
| `switch_margin` | Numero finito 0…1 |
| `motif.generators` | Identificativi distinti dei generatori destinatari |
| `motif.points` | Intero 2…32 |
| `motif.span_degrees` | Intero 1…12 |
| `override`, `stage_overrides` | Mappe facoltative con soli palette, root, scale e motif_degrees |

Senza `automatic_music` ogni famiglia continua a richiedere root e scala
esplicite. Le configurazioni manuali restano disponibili.

`cli.trip_direction.prepare_trip_config` restituisce una copia della
configurazione con sezioni e materiali risolti. `load_trip_sections` espone
le sole sezioni per report e chiamanti che non costruiscono generatori.
Director e Coordinator ricevono contesti musicali ordinari, senza metriche
geografiche o regole per strumenti specifici.

All'avvio vengono stampati tavolozza, misura che l'ha selezionata, motivo
e armonia di ciascuna macrosezione. Lo snapshot espone `trip_music`
(profilo, materiale generato ed effettivo, tavolozza e override),
`section.direction` e la direzione del piano in `decisions.coordinator`.
La vista terminale distingue scelte automatiche, di famiglia e override.

## Riscontro sui GPX disponibili

Con la configurazione corrente e senza override:

| Tappa | Pendenza assoluta media | Tavolozza | Motivo in gradi |
|---|---:|---|---|
| Levanto–La Spezia | 4,29% | `steep` | `[2, 6, 5, 6, 3, 2, 3, 0]` |
| Firenze–San Gimignano | 3,40% | `rolling` | `[3, 0, 2, 3, 5, 6, 2, 3]` |
| San Nicola–San Severo | 2,79% | `gentle` | `[2, 2, 4, 6, 4, 2, 1, 0]` |

I test verificano riproducibilità, indipendenza dal nome della tappa,
collegamento effettivo del materiale al generatore, contesti condivisi,
precedenze degli override, isteresi, validazione e modalità manuale.
