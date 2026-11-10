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
Alimenta le politiche adattive dei generatori nella sessione guidata dal GPX.

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

## Adattamento dei parametri

`EnsembleRuntime` abilita l'adattamento quando dispone dell'analisi del
percorso oppure di una sorgente di contesto con interprete musicale.
Senza entrambi, i parametri seguono assetti e override ordinari. Il costruttore
`EnsembleRuntime(..., adaptive=False)` permette il confronto tecnico con
stesso percorso, timeline, seed e suoni.

Il [meteo storico](CONTESTO-AMBIENTALE.md#meteo-storico) aggiunge contributi
alla dinamica di melodia, tessitura e drums, allo sviluppo melodico e alla
variazione percussiva. Può attivare le politiche anche nelle sezioni manuali;
in assenza del profilo non viene applicato il contributo del terreno.
Le formule seguenti descrivono terreno e osservazione musicale; i
coefficienti ambientali sono nel riferimento del meteo.

`cli.trip_direction.adaptive_context` interpreta il profilo locale:

- `intensity` (**I**): pendenza assoluta media divisa per 0,08, limitata a 0…1;
- `change` (**C**): valore assoluto del cambiamento di pendenza diviso per
  0,04, limitato a 0…1;
- `persistence` (**P**): persistenza della zona divisa per la finestra
  spaziale della pendenza, limitata a 0…1.

Queste normalizzazioni sono scelte compositive. Un ingresso indisponibile
rimane `null`: non applica il relativo contributo locale. Le osservazioni
musicali disponibili continuano a influenzare le politiche; il motivo
dell'indisponibilità resta nello stato.

Ogni modulo di voce propone obiettivi leggendo la stessa osservazione dei
16 beat accettati precedenti. Director e Coordinator non contengono nomi
di parametri o formule specifiche degli strumenti. `music/automation.py`
risolve transizioni e precedenza del manuale prima della guida ritmica.

| Voce | Obiettivi automatici |
|---|---|
| Melodia | `velocity`: base + `16 × (I − 0,5)`. `activity`: base + `0,18 × (I − 0,5) − 0,16 × pressione`; pressione = `min(1, 0,65 × attacchi/beat del basso + 0,35 × attacchi/beat delle drums / 4)` |
| Basso | `density`: base + `0,18 − 0,42 × busy`, limitata dalla capacità ritmica recente. `syncopation`: base + `0,16 − 0,24 × busy`; `busy = min(1, attacchi/beat melodici / 1,5)`. Senza storia melodica mantiene le basi, rispettando il limite di capacità |
| Tessitura | `velocity`: base × `(1 + 0,3 × (I − 0,5)) × (1 − 0,2 × pressione)`. La pressione è la massima occupazione melodica pesata per la quota del registro melodico che interseca l'ottava della tessitura |
| Drums | `velocity_ratio`: base × `(1 + 0,2 × (I − 0,5))`. `variation`: base + `0,22 × C × P + 0,12 × (0,5 − crowd)`; `crowd = min(1, 0,65 × attacchi/beat melodici / 1,5 + 0,35 × attacchi/beat del basso)` |

Senza storia musicale, i contributi relativi allo spazio restano assenti.
Gli obiettivi rispettano i limiti dei controlli; le velocity sono intere.
La capacità del basso deriva dall'ultimo piano, oppure dalla spaziatura
iniziale se manca un piano utile. Non rappresenta un obbligo di aggiungere
note. L'attività melodica non è automatizzata con `development = 0`.
Quando il motivo assume il ruolo di tessitura usa la relativa politica.

La dinamica converge in 8 beat; attività, densità, sincopi e variazione
in 16. L'attività melodica rivaluta l'obiettivo ogni
`phrase_windows × window_beats` dalla fase logica della sessione; il basso
ogni 4 beat; Variazione segue il ciclo della guida percussiva. Un cambio
di ruolo o assetto permette una nuova valutazione. Una differenza fino a
1 per la velocity o 0,01 per i controlli continui non riavvia la transizione.
La prima finestra parte dai valori base. Le traiettorie dipendono dai beat,
mentre i valori applicati restano costanti nella singola finestra composta.

Un valore manuale prevale soltanto sul suo parametro. Rilasciarlo riparte
dal valore manuale accettato e converge verso l'obiettivo automatico;
gli altri override restano attivi. Stile, seed, registri, griglia, durata
dei periodi e `follow_source` conservano configurazione o scelta manuale.
Non vengono aggiunti controlli musicali ai device.

Gli stati dei parametri vengono accettati insieme alle frasi: fallimenti,
richieste ripetute e reset rispettano la stessa gestione della memoria.
Il riferimento delle drums e la frase finale usano gli stessi valori.
Gli appoggi comunicati non vengono modificati in risposta alle altre voci
della stessa finestra.

`decisions.coordinator.automation` espone per parametro `base`, `target`,
`effective`, `source`, `reason` e `transition_beats`. `adaptive_context`
conserva le indicazioni musicali usate. Nel device il campo numerico e lo
slider seguono il piano arrivato al beat del trasporto; la freccia `→`
mostra l'obiettivo. L'annotazione contiene base, obiettivo, valore applicato
e motivo. I valori di un piano ancora futuro non sostituiscono quelli
della finestra in ascolto; le modifiche manuali restano richieste per le
prossime finestre da comporre.

Le drums sviluppano ancora figure precomposte: l'adattamento modifica
realmente i loro controlli, senza costituire il compositore a regole
previsto dal [contratto percussivo](proposte/musica/media/in-corso/STILI-PERCUSSIVI.md).

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

## Sorgenti musicali esterne

`music/sources.py` definisce `MusicalSource`: ruolo, frase prevista, numero
di note già sostenute al confine (`carry_in`) e motivo di indisponibilità.
Una frase vuota è silenzio previsto; `phrase=None` indica dati indisponibili.

`MusicCoordinator.plan(external_sources=...)` espone queste sorgenti in
`PlanningRequest.external_sources` e nell'adattamento per ruolo. Densità,
registro e occupazione delle previsioni sono distinti dalle osservazioni
della storia accettata. Le sorgenti esterne non vengono inviate al player
delle voci Python. `MusicDirector.decision_at(external_sources=...)`
riporta ruolo e disponibilità, mantenendo la scelta armonica dal GPX.

Snake è collegato attraverso il proprio adattatore: [lettura e validità
delle previsioni](SNAKE.md#snake-come-sorgente-musicale).
