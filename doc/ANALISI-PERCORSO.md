# Analisi delle zone del percorso

`desnivel.trip.analysis.analyze_track` analizza quota e distanza cumulata di un
`Track`. Il comando `desnivel.cli.analyze_trip` carica FIT o GPX tramite il loader
esistente, stampa le zone e può esportare l'analisi in JSON e come report HTML. Non genera musica
e non modifica le assegnazioni della sessione multivoce.

Il loader conserva soltanto i tratti osservati dopo la selezione del viaggio
e l'esclusione delle interruzioni. Le misure, le zone e la timeline usano
questi tratti; il report conserva anche i riferimenti ai dati originali.

## Sorgenti FIT e GPX

`trip.loader.load_track` seleziona il lettore dall'estensione e usa la stessa
pipeline per filtri GPS, derivazione e ricampionamento. Il FIT è letto con
`fitdecode`, dipendenza del progetto; CRC e decodifica vengono verificati.
Nei comandi che leggono una tappa, `--track` accetta `.fit` e `.gpx`;
`--gpx` rimane un alias dello stesso argomento.

Il lettore FIT consolida i messaggi `record` con lo stesso secondo UTC,
conservando l'ultimo valore presente per ciascun campo, e ordina i campioni
per timestamp originale. Registra i valori discordanti nello stesso secondo
e le inversioni nell'ordine dei messaggi. Non trasporta coordinate da un
secondo all'altro; i record senza posizione non diventano punti GPS.
`source_index` identifica il secondo consolidato, numerato da 1 nell'ordine
temporale, anche quando manca una posizione in quel secondo.

Gli eventi timer `start` e `stop` delimitano i tratti registrati. I campioni
fuori da questi intervalli sono esclusi prima del filtro GPS; i tratti
conservati non attraversano una pausa. Per impostazione predefinita il FIT
deve contenere almeno un intervallo chiuso: eventi mancanti, timer aperto o eventi non supportati
producono un errore. Start ripetuti e stop a timer già fermo vengono
registrati nella diagnostica. In `ensemble`, `--infer-fit-pauses` consente
la lettura di un FIT privo di eventi timer usando la stima GPS delle pause.
Il loader espone la stessa scelta con `infer_missing_fit_timer=True`.
L'opzione non accetta timer incompleti e non si applica al FIT usato come
`timing_reference`. La provenienza risulta `gps_inference`; durata timer e
intervalli restano assenti, mentre il riepilogo dichiarato viene conservato.
Il timer attivo indica registrazione non in pausa, non una verifica indipendente del movimento.

`Track.metadata.source_recording` conserva riepiloghi di sessione, eventi,
intervalli del timer e diagnostica. Il report distingue:

- `declared_timer_duration_s`: tempo attivo dichiarato dalle sessioni FIT;
- `timer_duration_s`: somma degli intervalli start/stop;
- `observed_duration_s`: durata dei tratti GPS utilizzabili;
- `unobserved_timer_duration_s`: tempo degli intervalli timer senza un tratto
  GPS utilizzabile dopo i controlli.

Queste durate non vengono riscalate per farle coincidere. Il tempo senza
osservazioni valide non viene ricostruito.

Quota e coordinate provengono dal formato scelto. Distanza osservata,
velocità, pendenza ed effort sono derivati dalle coordinate e dalle quote
conservate, con lo stesso metodo per FIT e GPX. I valori FIT di distanza,
velocità e accuratezza GPS rimangono disponibili nei canali
`recorded_distance_m`, `recorded_speed_kmh`, `gps_accuracy_m`; non sostituiscono
le metriche derivate. La distanza totale dichiarata nel FIT è mostrata
separatamente e può differire dalla distanza osservata. Le quote del FIT
e del GPX esportato possono differire: il loader non le mescola.

Per leggere un GPX usando le pause del FIT corrispondente, aggiungere
`--timing-reference percorso.fit`. Le coordinate e le quote rimangono quelle
del GPX; il FIT fornisce gli eventi timer. Il controllo richiede che il FIT
copra tutti gli orari del GPX, non identifica automaticamente il percorso
corrispondente. Senza riferimento, il GPX usa la stima delle soste descritta
di seguito. `selection_source` distingue `timer_events` da `gps_inference`.

```bash
cd /Users/marco/ogni-tanto-programmo/desnivel
.venv/bin/python -m desnivel.cli.analyze_trip \
  --gpx gpx/tappa05_Firenze_San_Gimignano.gpx \
  --config presets/analisi-percorso.json \
  --grouping presets/macrosezioni-percorso.json \
  --output output/analisi-percorso.json \
  --html output/analisi-percorso.html
```

## Metodo e configurazione

La configurazione JSON richiede quattro campi:

| Campo | Significato |
|---|---|
| `sample_distance_m` | Distanza fra i confini degli intervalli osservati. L'ultimo intervallo termina alla fine del percorso. |
| `slope_window_m` | Ampiezza della finestra centrata sul punto medio di ciascun intervallo. La pendenza è il dislivello fra gli estremi diviso per la distanza. La finestra viene accorciata ai bordi del percorso. |
| `min_zone_distance_m` | Estensione consecutiva nella stessa nuova fascia necessaria per confermare un cambio. |
| `bands` | Fasce ordinate con nome e limite inferiore `from_slope_ratio`, incluso. La prima parte da `null`, senza limite inferiore; l'ultima non ha limite superiore. |

I valori numerici devono essere positivi e finiti; le soglie delle fasce possono
essere negative e devono essere strettamente crescenti. Le pendenze sono frazioni:
`0.06` significa 6%. I nomi delle fasce sono dati di configurazione.

Il file `presets/analisi-percorso.json` contiene una prima taratura da revisionare:
intervalli di 100 m, osservazione di 300 m, persistenza di 300 m; fasce delimitate
da −6%, −1,5%, +1,5% e +6%. Questi valori non sono soglie ciclistiche validate.

La prima osservazione inizializza la zona. Ogni cambio successivo richiede la
persistenza configurata; una fascia diversa interrompe la sequenza candidata.
Quando il cambio è confermato, il suo confine viene posto all'inizio della
sequenza candidata. Si tratta quindi di un'analisi offline, che usa anche dati
successivi al punto classificato. La prima zona può essere più corta del minimo.

I cambi brevi, compresa una coda finale non confermata, rimangono nella zona
precedente. Per questo il nome della zona può differire dalla classificazione
della sua pendenza media. Il report espone entrambe le misure e la concordanza:
la frazione di distanza le cui osservazioni appartengono alla fascia assegnata.
La concordanza descrive l'effetto del raggruppamento, non l'affidabilità del GPS.

## Risultato e dati richiesti

Il JSON conserva configurazione, sorgente, distanza osservata totale e tre elenchi:

- `zones`: tipo, confini in metri, avanzamento sulla distanza totale, dislivello
  netto, pendenza media e concordanza. Le zone coprono l'intero percorso.
- `windows`: confini dell'intervallo, quota al centro, pendenza osservata,
  fascia locale prima della conferma e indice della zona assegnata.
- `profile`: quota ai confini e ai centri degli intervalli, interpolata sul
  `Track`, con distanza in metri dall'inizio del percorso.

Quota e distanza devono essere complete, finite e allineate ai campioni del
`Track`; la distanza deve essere non decrescente con estensione positiva.
L'assenza di quota produce un errore. Il loader interpola le lacune parziali
di quota e applica la mediana già prevista nella configurazione GPX.
A distanza identica viene conservata l'ultima quota; le soste non hanno
estensione in questa analisi per distanza.

Finestre troppo piccole per distinguere numericamente i loro estremi ed
estensioni, pendenze o dislivelli non rappresentabili producono un errore.
Il confine finale compare una sola volta anche con passi decimali.

L'analisi descrive il profilo altimetrico: non identifica fatica fisiologica,
scollinamenti come eventi separati o scelte musicali.

## Selezione del viaggio osservato

`loader/_travel.py` identifica le interruzioni prima della derivazione
dei canali e del ricampionamento. I criteri comuni a tutte le tappe sono
in `trip/config.py`, nella classe `GpxConfig`:

| Campo | Valore iniziale | Significato |
|---|---:|---|
| `recording_gap_s` | 30 | Massimo intervallo fra osservazioni consecutive elaborabili insieme |
| `stop_min_duration_s` | 300 | Durata minima di una sequenza di coordinate quasi ferme esclusa come sosta prolungata |
| `stop_radius_m` | 3 | Raggio rispetto al punto iniziale della sequenza quasi ferma |
| `pause_min_gap_s` | 8 | Durata minima di un intervallo rado candidato a pausa |
| `pause_gap_factor` | 3 | Rapporto minimo fra intervallo candidato e cadenza tipica; deve essere maggiore di 1 |
| `pause_max_speed_kmh` | 5 | Velocità media massima fra gli estremi dell'intervallo rado candidato |

`recording_gap_s` si applica a entrambi i formati. I criteri `stop_*` e `pause_*`
si applicano al GPX senza riferimento FIT; con eventi timer la selezione
delle pause usa gli eventi registrati.

`loader/_stops.py` stima la cadenza tipica dal quartile inferiore degli
intervalli continui validi. Un intervallo è candidato a pausa se dura almeno
`max(pause_min_gap_s, cadenza × pause_gap_factor)` e la velocità media fra i
suoi estremi non supera `pause_max_speed_kmh`. La sola velocità bassa con
campionamento regolare non determina una pausa. Questo criterio è distinto
dalla sosta prolungata entro il raggio spaziale e dalle lacune oltre
`recording_gap_s`. Il registro usa `sampling_pause`, `stationary` e
`recording_gap` rispettivamente.

`travel_selection.pause_inference` conserva cadenza stimata, soglia effettiva
e parametri; con riferimento timer è vuoto. La taratura è comune alle tappe:
il loader GPX non legge FIT per scegliere i propri parametri durante il
caricamento senza riferimento.

Tempi non validi, punti mancanti e confini dei segmenti GPX interrompono
anch'essi la continuità. Il limite temporale è configurabile per sorgenti
con diversa cadenza di registrazione. Una lacuna non viene classificata
automaticamente come sosta. La regola spaziale della sosta è un criterio
operativo configurato, non una misura certa dell'attività del ciclista.
Movimento lento che esce dal raggio prima della durata minima rimane nei
tratti osservati quando non presenta interruzioni di campionamento candidate
a pausa. Le pause più brevi della soglia e il rumore GPS possono ancora
produrre differenze rispetto agli eventi timer.

### Confronto delle pause stimate con i FIT

```sh
.venv/bin/python -m desnivel.cli.validate_pauses \
  --gpx-dir gpx \
  --fit-dir fit \
  --output-dir output/confronto-pause
```

Il comando associa le sorgenti tramite l'identificativo della tappa nei nomi
dei file, verifica la presenza di orari comuni e applica filtro GPS e
riconoscimento delle pause al solo GPX. `trip.pause_validation.compare_pauses`
confronta la selezione risultante con gli intervalli timer FIT.

`confronto-pause.html` mostra i risultati per tappa e gli intervalli
discordanti; `confronto-pause.json` conserva gli stessi dati, i parametri e
gli SHA-256 delle sorgenti. Sono distinti tempo escluso con timer attivo e
tempo conservato con timer fermo. Entrano nel confronto solo intervalli
GPS validi entro `recording_gap_s`, interamente attivi o interamente in
pausa secondo il riferimento. Lacune, intervalli con misure non valide,
copertura mancante e confini misti vengono conteggiati separatamente come
tempo non confrontato.

`--baseline percorso.json` aggiunge un confronto precedente. Richiede gli
stessi file, le stesse tappe e la stessa durata confrontabile. Le tappe senza
FIT sono elencate senza attribuire loro una misura di accuratezza. Il timer
è il riferimento della registrazione, non una misura indipendente del
movimento fisico; il confronto non dimostra la natura delle lacune GPS.

I tratti conservati sono derivati e ricampionati separatamente. Nei
periodi esclusi non vengono prodotti campioni uniformi, metriche di
movimento o classificazioni del terreno. Non viene aggiunta la distanza
fra l'ultimo punto di un tratto e il primo del successivo. Un GPX senza
alcun tratto osservato con spostamento produce un errore esplicito.

`Track.segments` conserva slice dei campioni e riferimenti ai punti e ai
tempi sorgente. `Track.t` misura il tempo attivo concatenato dei tratti,
con entrambi gli estremi conservati allo stesso tempo attivo nelle
giunzioni. `Track.metadata.travel_selection` contiene criteri, durata
sorgente, durata osservata e registro delle interruzioni.

L'analisi altimetrica viene eseguita indipendentemente per ogni tratto:
non interpola quote né calcola pendenze attraverso le interruzioni.
Il report mantiene le linee del profilo separate e mostra tempo sorgente
e tempo elaborato. Le metriche non combinano quote dei due lati della
giunzione. La selezione per famiglie può riunire zone successive della
stessa famiglia sull'asse della distanza osservata; non attribuisce
un terreno al tratto escluso.

Il replay lineare usa il tempo attivo, mentre l'allocazione in beat/km
usa la sola distanza osservata. Nessuna delle due modalità assegna tempo
musicale ai periodi esclusi. I GPX originali e i registri di revisione
restano disponibili; annotazioni geografiche, comprese le gallerie,
richiedono una distinta interpretazione musicale.

## Ispezione dei punti GPX originali

Il comando singolo e quello per tutte le tappe aggiungono `source_quality`
e `source_filter` al JSON e una sezione dedicata nel report. Il calcolo è separato dal
rilevamento delle zone: `trip/quality.py` legge gli array originali del
parser, prima di interpolazione e filtraggio del loader.

La velocità di ciascun intervallo è distanza geodetica fra le coordinate
dei due punti divisa per la differenza degli orari, convertita in km/h.
Coordinate non valide, tempi mancanti o non crescenti, confini di segmento
e punti scartati intermedi rendono la velocità non disponibile. Una sosta
con tempi validi produce invece velocità zero.

Il risultato conserva conteggi di disponibilità, mediana e percentile 95
delle velocità disponibili, senza filtrare i valori elevati. I dieci
intervalli più veloci includono estremi, coordinate, quote e orari UTC
originali, numeri dei punti nel GPX e punti adiacenti. Il report permette
di selezionarli e osservare lo schema locale delle coordinate e la tabella
dei punti. L'ordinamento serve alla verifica e non classifica gli
intervalli come errori.

La distanza sorgente è cumulata senza correggere i salti, includendo
anche eventuali collegamenti fra segmenti. Esclude dal totale i soli
intervalli con coordinate non valide, che non hanno una distanza
calcolabile. Non rappresenta una distanza corretta del viaggio. Questa
ispezione conserva i valori originali; il registro `source_filter` descrive
separatamente le esclusioni effettivamente applicate al caricamento.

## Esclusione delle deviazioni della posizione

`loader/_filter.py` viene eseguito da `load_track` prima della derivazione
dei canali. Il GPX originale non viene riscritto. La configurazione è
in `trip/config.py`, nella classe `GpxConfig`:

| Campo | Valore iniziale | Significato |
|---|---:|---|
| `max_speed_kmh` | 70 | Limite superiore delle velocità utilizzabili |
| `spike_max_removed_points` | 2 | Massimo numero di punti consecutivi escludibili in una riconnessione |
| `spike_max_gap_s` | 60 | Massimo tempo originale fra gli adiacenti conservati |
| `spike_min_detour_ratio` | 0,5 | Riduzione minima del percorso locale rispetto alla distanza diretta fra gli adiacenti |

Un intervallo oltre il limite avvia la verifica locale. Il filtro considera
l'esclusione di brevi gruppi che comprendano uno dei suoi estremi, senza
rimuovere primo o ultimo punto. Accetta una riconnessione soltanto con
coordinate e tempi validi, ordine temporale crescente e continuità nello
stesso segmento. La velocità ricalcolata sugli adiacenti deve rispettare
il limite e la riduzione della deviazione deve raggiungere la soglia.
Coordinate e orari dei punti conservati rimangono invariati.

Le proposte sono ordinate per numero crescente di punti da escludere,
poi per riduzione decrescente della deviazione. I tratti già utilizzati
da una riconnessione non vengono ulteriormente erosi da altre esclusioni.
Il filtro registra numeri originali dei punti, estremi conservati,
distanza prima e dopo, tempo originale e velocità ricalcolata.

Quando non può verificare una riconnessione, il filtro conserva i punti
e registra il tratto come non risolto. La successiva selezione del viaggio
stabilisce se l'intervallo sia osservato o costituisca un'interruzione.
Negli intervalli osservati non risolti, velocità, pendenza di movimento e stima di sforzo
diventano non disponibili, anziché zero o valori limitati artificialmente
a 70 km/h. Anche intervalli con tempi invalidi, confini di segmento o punti
intermedi mancanti sono esclusi dalle misure di movimento.

Il ricampionamento di velocità, pendenza di movimento e sforzo conserva
i valori per intervallo originale e i buchi di disponibilità. L'esportazione
delle metriche omette distanza d'intervallo, velocità, pendenza e sforzo
per le finestre che intersecano un tratto non risolto, impedendo che il
picco venga ricostruito dalla distanza cumulata. Quota e distanza totale
rimangono misure separate. `Track.metadata` conserva registro del filtro
e intervalli non disponibili.

La distanza cumulata viene ricalcolata all'interno dei tratti conservati. Per questo
l'analisi altimetrica e l'allocazione possono cambiare confini e durate
senza modifiche all'algoritmo di rilevamento. Le distanze dei tratti non
risolti restano incluse: il totale non è una ricostruzione certificata del
percorso. I collegamenti fra tratti separati sono esclusi dalla distanza.
Il limite di velocità e i criteri locali sono regole configurate
di esclusione, non una prova che ogni punto escluso sia errato.

## Segmenti da verificare con chi ha percorso la tappa

`source_quality.review_segments` raccoglie segnalazioni sui punti originali.
I criteri di revisione sono separati dal filtro di esclusione e non
modificano punti, metriche o assegnazioni musicali:

- velocità oltre il limite del filtro, attualmente 70 km/h;
- intervallo fra campioni superiore a 30 secondi, con più di 100 metri
  fra le coordinate estreme;
- spostamento superiore a 50 metri dopo almeno 30 secondi di coordinate
  comprese entro 10 metri dalla posizione precedente al salto;
- coordinate o tempi non validi, confini di segmento e punti intermedi
  mancanti.

Le condizioni sono definite in `trip/quality.py`, in `REVIEW_SETTINGS`,
e riportate nel risultato. `inspect_source` accetta impostazioni di
revisione esplicite. Gli indizi separati da non più di 60 secondi nello
stesso segmento sono raggruppati. Ogni gruppo conserva ID basato sui
numeri originali dei punti, motivi, estremi, picco, intervalli segnalati
e contesto fino a 60 secondi prima e dopo. Se gli orari non sono
utilizzabili, il contesto usa i punti adiacenti e dichiara tale modalità.

Una sosta reale può soddisfare i criteri: queste segnalazioni richiedono
verifica e non identificano automaticamente gallerie o perdita di segnale.
L'assenza di segnalazioni non certifica l'accuratezza del GPX.

## Macrosezioni del percorso

Il modulo `desnivel.trip.sections.group_zones` riceve l'analisi e una
configurazione distinta di famiglie. Raggruppa soltanto zone consecutive
della stessa famiglia, con confini adiacenti; mantiene i dati originali
dell'analisi. Il comando attiva questo passaggio con `--grouping`.

`presets/macrosezioni-percorso.json` configura:

```json
{
  "families": {
    "ascent": ["climb", "steep_climb"],
    "descent": ["descent", "steep_descent"],
    "level": ["level"]
  }
}
```

Ogni fascia definita nella configurazione di analisi deve appartenere
esattamente a una famiglia. Assegnazioni mancanti, duplicate o riferite a
fasce sconosciute producono un errore. Nomi e appartenenze delle famiglie
sono configurabili; il raggruppamento non conosce significati musicali.

Un tratto `level` interrompe una `ascent` con questa configurazione, anche
se breve. Non sono previste tolleranze per assorbire interruzioni. Una
famiglia può comparire più volte lungo il percorso in macrosezioni distinte.

Il risultato viene aggiunto dal comando nel campo `grouping`, che contiene
la configurazione utilizzata e l'elenco `sections`. Ogni macrosezione espone
indice, famiglia (`kind`), confini in metri, avanzamento sulla distanza
totale, dislivello netto, pendenza media e `zone_indices`: gli indici delle
zone originali incluse. Gli indici nel JSON partono da zero; report e tabella
nel terminale li mostrano a partire da uno.

Senza `--grouping` vengono prodotte soltanto le zone dell'analisi.

## Report visuale

Aprire `output/analisi-percorso.html` nel browser. Il file incorpora dati, stile
e JavaScript; funziona localmente senza server o risorse esterne. Le cartelle
di output vengono create dal comando se assenti. `--html` e `--output` sono
indipendenti e, quando usati insieme, devono indicare file distinti.

Il modulo `desnivel.reports.trip.render_trip_report` riceve il risultato
di `analyze_track` e restituisce l'HTML. Le risorse di presentazione sono
separate in `trip.html`, `trip.css` e `trip.js`, incluse nel pacchetto Python.
Il renderer non legge il GPX e non ricalcola zone o soglie.

I due grafici condividono la distanza: quota con sfondi delle zone confermate
e pendenza osservata con soglie tratteggiate prese dalla configurazione.
La fascia sotto il profilo mostra la classificazione locale; un tratteggio
segnala dove differisce dalla zona assegnata. La legenda usa i nomi delle
fasce configurate, anche quando vengono rinominate o cambiano di numero.

Il puntatore mostra i dettagli dell'intervallo osservato. I campi «Da km» e
«A km» selezionano una porzione; i pulsanti delle zone nella tabella la
inquadrano con un piccolo margine. «Tutto il percorso» ripristina la vista
completa. Lo zoom modifica soltanto la vista; per modificare l'analisi occorre
cambiare il JSON dei criteri e rieseguire il comando.

Quando il risultato contiene `grouping`, il report aggiunge una fascia delle
macrosezioni sopra il profilo, una legenda delle famiglie e una tabella
dedicata. Selezionare una macrosezione ingrandisce il tratto ed evidenzia le
sue zone originali nella tabella di dettaglio. Il puntatore mostra insieme
macrosezione, zona e fascia osservata. La configurazione delle famiglie è
consultabile accanto ai criteri di analisi. Il report visualizza il
raggruppamento ricevuto senza ricalcolarlo nel browser.

L'opzione `--timeline-session presets/organico.json` aggiunge al report
l'[anteprima della timeline musicale in beat](TIMELINE.md), utilizzando le
stesse macrosezioni. Richiede `--grouping` e non modifica zone o profilo.

## Pianure tra salite o discese: confronto locale

Con `--grouping`, l'opzione `--pause-context ascent level` aggiunge una
misura delle macrosezioni `level` immediatamente precedute e seguite da
`ascent`. Ripetendo l'opzione con `--pause-context descent level` si
misurano anche le pianure tra due discese nello stesso report. Le pianure
tra una salita e una discesa non corrispondono a nessuna delle due terne.
I due nomi sono argomenti espliciti e devono appartenere alle
famiglie configurate; il calcolo è disponibile anche per altre coppie.

`trip.sections.measure_section_bridges(sections, flank_kind=..., middle_kind=...)`
legge le macrosezioni originali e restituisce, per ogni terna:

- gli indici delle tre macrosezioni;
- le loro lunghezze in metri;
- il riferimento locale `2 × prima × dopo / (prima + dopo)`;
- il rapporto `lunghezza intermedia / riferimento locale`.

I risultati sono esportati nella lista `section_context`, un elemento per
ogni coppia richiesta, nel JSON e incorporati
nell'HTML. Il report mostra una tabella con la famiglia dei tratti adiacenti: selezionare una riga inquadra i tre
tratti nel profilo. Anche i rapporti superiori al 100% sono mostrati. Se non
ci sono terne corrispondenti, il report indica zero sezioni.

Non viene applicata una soglia né effettuato un nuovo raggruppamento.
Zone, macrosezioni, timeline e ascolto mantengono il comportamento corrente.
Il confronto serve a valutare una futura soglia per le pause interne.

```sh
.venv/bin/python -m desnivel.cli.analyze_trip \
  --gpx gpx/tappa05_Firenze_San_Gimignano.gpx \
  --config presets/analisi-percorso.json \
  --grouping presets/macrosezioni-percorso.json \
  --pause-context ascent level \
  --pause-context descent level \
  --timeline-session presets/organico.json \
  --output output/analisi-percorso.json \
  --html output/analisi-percorso.html
```

## Report di tutte le tappe

Il comando `cli.analyze_trips` analizza i file `.fit` e `.gpx` presenti direttamente
nella cartella indicata, ordinati per identificativo di tappa. Se una tappa
è presente in entrambi i formati preferisce il FIT. Più file dello stesso
formato preferito per la stessa tappa producono un errore. Non cerca nei
sottodirettori. `--track-dir` e `--gpx-dir` sono alias. Riutilizza la stessa funzione
`cli.analyze_trip.analyze_trip` del comando singolo, con identiche
configurazioni e misure.

```sh
.venv/bin/python -m desnivel.cli.analyze_trips \
  --track-dir fit \
  --config presets/analisi-percorso.json \
  --grouping presets/macrosezioni-percorso.json \
  --pause-context ascent level \
  --pause-context descent level \
  --timeline-session presets/organico.json \
  --output-dir output/tappe-fit
```

La cartella di uscita contiene:

- `index.html`: selettore della tappa, report incorporato e collegamento per
  aprire il report completo in un'altra scheda;
- `report-<nome sorgente>.html`: report autonomo di ciascuna tappa;
- `report-<nome sorgente>.json`: dati della stessa analisi.
- `segmenti-da-verificare.html`: riepilogo di tutte le tappe con segnalazioni,
  orari italiani (`Europe/Rome`), coordinate, collegamenti alla mappa e ID
  utilizzabili per comunicare annotazioni;
- `segmenti-da-verificare.json`: criteri e segmenti della stessa revisione.

Aprire `output/tappe-fit/index.html` nel browser. La selezione cambia il report
visualizzato; non avvia una sessione musicale. Le pagine si leggono da file
locale senza server o connessione a Internet. Per aggiornare le analisi dopo
una modifica ai parametri, rilanciare il comando e ricaricare la pagina.
La generazione sovrascrive i file corrispondenti alle tappe presenti; non
elimina eventuali report di tappe rimosse dalla cartella sorgente.
La generazione aggiorna anche i due file della revisione. Le annotazioni
mostrate come esempio nella pagina non vengono salvate dal report.

## Importazione dei dati Strava per il confronto

`cli.import_strava` scarica una copia locale del dettaglio di un'attività e
dei suoi stream. L'importazione non modifica il GPX, il filtro del loader,
le analisi o la generazione musicale. Lo snapshot costituisce l'ingresso
per la verifica successiva; il comando non produce il report di confronto.

La creazione dell'applicazione API richiede un abbonamento Strava attivo,
come indicato nella [guida ufficiale](https://developers.strava.com/docs/getting-started/).
Il comando non è utilizzabile senza un'applicazione registrata. Il flusso
è verificato con test simulati; l'acquisizione dall'account non è ancora
stata eseguita.

Prima del primo utilizzo, registrare un'applicazione personale su
[Strava API](https://www.strava.com/settings/api), impostando
**Authorization Callback Domain** a `127.0.0.1`. Client ID e Client Secret
vanno inseriti nel terminale quando richiesti, non nel codice o nei preset.

Eseguire dalla cartella del progetto:

```sh
.venv/bin/python -m desnivel.cli.import_strava \
  --gpx gpx/tappa06_Orvieto_Bagnoregio_Lago_di_Bolsena.gpx
```

Il comando stampa un link di autorizzazione da aprire nel browser e attende
fino a cinque minuti. Richiede `activity:read_all`, permesso di sola lettura
che comprende anche le attività private. Il callback ascolta su
`127.0.0.1` con porta assegnata dal sistema e verifica lo stato della
richiesta prima di scambiare il codice temporaneo.

Dopo l'autorizzazione mostra le attività temporalmente sovrapposte al GPX
e chiede di scegliere il loro ID. `--activity-id <numero>` permette di
indicarlo direttamente; anche in questo caso verifica la sovrapposizione
temporale. Questa verifica identifica candidati: non dimostra ancora che
coordinate e campioni coincidano.

La destinazione predefinita è `output/strava/<nome GPX>.json`; `--output`
consente di cambiarla. Un file già presente non viene sovrascritto.
Lo snapshot contiene:

- dettaglio dell'attività, compresi `start_date`, `moving_time` ed `elapsed_time`;
- stream necessari `time`, `moving` e `latlng`;
- stream `distance`, `altitude`, `velocity_smooth` e `grade_smooth`, quando restituiti;
- data di acquisizione UTC, percorso e SHA-256 del GPX associato.

Se manca uno stream necessario, oppure le serie hanno lunghezze differenti,
l'importazione si interrompe con errore. Le credenziali e i token restano
in memoria e non sono salvati nello snapshot: una nuova importazione
richiede nuovamente l'autorizzazione. I dati già scaricati si possono leggere
senza collegamento a Strava.

Riferimenti: [autorizzazione Strava](https://developers.strava.com/docs/authentication/)
e [stream delle attività](https://developers.strava.com/docs/reference/#api-Streams-getActivityStreams).
