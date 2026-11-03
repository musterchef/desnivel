# Sessione multivoce Python

Il comando `desnivel.cli.ensemble` esegue nello stesso processo il replay FIT/GPX, il Music Director, il Music Coordinator, i generatori e il server dei dispositivi di voce. La configurazione seleziona esplicitamente generatori, ruoli, parametri e organico delle sezioni.

Il loader usa gli eventi timer del FIT, oppure stima le soste dal GPX,
ed esclude le interruzioni prima di ricampionare
il viaggio. Il replay lineare usa il tempo dei tratti osservati; la
timeline allocata usa la loro distanza. I periodi esclusi non ricevono
durata musicale. I criteri e i riferimenti ai dati originali sono descritti
in [ANALISI-PERCORSO.md](ANALISI-PERCORSO.md#selezione-del-viaggio-osservato).

## Avvio

Chiudere con Ctrl+C il ricevitore diagnostico `desnivel.cli.voice_device`, che usa la stessa porta.

Per scegliere la tappa, aprire `comandi/09 - Sessione multitappa.command`
oppure, dalla radice del repository:

```sh
.venv/bin/python -m desnivel.cli.launch_stage
```

Il launcher usa `organico.json`, timeline allocata e mappa sulla porta 8765.
Accetta `01`–`12` e `07bis`; sorgenti e requisiti della variante sono in
[Comandi](COMANDI.md#sessione-multivoce-con-scelta-della-tappa).

**N** nel terminale apre la preparazione guidata di Snake, prima del Play.
La guida controlla periodicamente il componente; **Invio** verifica subito
e **Esc** annulla. L’avvio base conserva le quattro voci e apre il servizio
Snake soltanto su richiesta. Ruoli, modalità autonoma/coordinata e
istruzioni in [Snake](SNAKE.md#componente-multiruolo).

Per scegliere direttamente sorgente e modalità:

```sh
.venv/bin/python -m desnivel.cli.ensemble \
  --track gpx/tappa05_Firenze_San_Gimignano.gpx \
  --config presets/organico.json \
  --timing allocated --view-port 8765
```

`--track` accetta FIT e GPX; `--gpx` è un alias. `--timing linear --speed 50`
usa invece il replay accelerato. `--dry-run` verifica configurazione e
sezioni senza aprire porte o inviare note; riusa il meteo disponibile
senza scaricarlo.

Il campo `direction` della configurazione carica la direzione del percorso.
`--direction altro.json` la sostituisce; `--manual-sections` usa le sezioni
manuali e richiede timing lineare. Per un GPX, `--timing-reference percorso.fit`
usa gli eventi timer del FIT corrispondente: [lettura e criteri](ANALISI-PERCORSO.md#sorgenti-fit-e-gpx).

Nella configurazione fornita:

| Parte | Configurazione in Live |
|---|---|
| `voice_01` | `Desnivel_Voice` prima del synth, Receive `9101`, Python `9006` |
| `voice_02` | `Desnivel_Voice` prima dello strumento della seconda parte, Receive `9102`, Python `9006` |
| `voice_03` | `Desnivel_Voice` prima dello strumento atmosferico, Receive `9103`, Python `9006` |
| `voice_04` | `Desnivel_Voice` prima del Drum Rack, Receive `9104`, Python `9006` |

Impostare l'identificativo in **Voce** e premere **Collega** sulle istanze,
quindi avviare il trasporto di Live. La prova usa il 909 Core Kit con i
16 pad sulle note MIDI 36…51. La mappa completa è definita in
`adapters/percussion.py` e descritta nel riferimento di configurazione. Lo strumento atmosferico riceve una nota
sostenuta monofonica per finestra: il suono si sceglie nello strumento Live.
Tutte le voci attive devono essere collegate, altrimenti la sessione attende
in `waiting_for_devices`.

Il dispositivo descritto in [VOCE-M4L.md](VOCE-M4L.md) invia la posizione
musicale ogni 125 ms oltre al messaggio periodico di collegamento. Le nuove
voci usano lo stesso dispositivo; i menu vengono forniti da Python.

`voice_01` è la sorgente del trasporto scelta dal campo `transport_voice`. Questo assegna la lettura del clock, non un privilegio compositivo. Il dispositivo continua a comunicare il trasporto anche quando la parte è inattiva nell'organico.

## Replay e pianificazione

In modalità `--timing linear` (predefinita), il viaggio avanza in secondi, moltiplicati per `--speed`, quando la sessione sta suonando. La distanza cumulativa interpolata del GPX determina la progressione usata per selezionare le sezioni. Il GPX controlla il contesto e l'organico delle sezioni; questo comando non applica la mappatura velocità/sforzo ai gate di `journey.compose`.

Con `--timing allocated` il runtime usa la timeline in beat configurata in
`organico.json`, richiede una direzione configurata o esplicita e non accetta `--speed`. Le macrosezioni
ricevono tutte le finestre assegnate; la sessione termina dopo la conclusione
dell’ultima. Alla ripresa dopo un’interruzione viene ripetuta per intero la
prima finestra non conclusa. Comandi e dettagli in [TIMELINE.md](TIMELINE.md).

Live fornisce beat e stato Play/Stop. Stop spegne le note, cancella i piani e mette in pausa il viaggio. Play lo riprende dal punto raggiunto. Salti all'indietro e discontinuità comunicate dal dispositivo cancellano e ripianificano le note senza riportare il viaggio a una posizione ricavata dalle battute.

`window_beats` indica la durata delle frasi; `lead_beats` l'anticipo minimo rispetto al beat ricevuto. Le frasi iniziano a multipli della finestra. Ogni intervallo viene pianificato una volta: cambi di ruolo e parametri si applicano alle finestre ancora da pianificare.

Il cambio di sezione modifica le assegnazioni alla successiva pianificazione. Alle parti uscenti viene inviata una frase vuota per la nuova finestra, lasciando terminare quella precedente. Se manca una parte attiva o la sorgente del trasporto perde il collegamento, la sessione cancella i piani dei dispositivi raggiungibili e attende, sospendendo il replay. I dispositivi non raggiungibili eseguono il proprio Panic per mancata conferma.

Al termine del viaggio la sessione spegne le note e mostra `finished`. Ctrl+C chiude il server e scrive lo stato `closed`. Un errore di generazione porta allo stato `error`; il restart riporta a zero; un successivo Play permette un nuovo tentativo.

### Pausa e restart

Il tasto **C** nel terminale interattivo invia **Collega tutte** ai device
Voice. Usa la porta Receive 9101, configurabile con `--connect-port`,
senza modificare il trasporto o lo stato del viaggio.

Il meteo viene caricato automaticamente dalla cache della tappa oppure
acquisito al primo avvio; `--weather-context` permette di scegliere un file
esplicito. Il tasto **M** attiva o disattiva il suo contributo musicale.
Il cambiamento riguarda le prossime finestre da
pianificare; i piani già inviati si completano. Device e dashboard mostrano
lo stato corrente e gli eventuali cambi in coda. `--without-weather`
permette di iniziare con il contributo disattivato.

Nel terminale interattivo, **Spazio** mette in pausa o riprende viaggio e
trasporto di Live; **R** azzera viaggio e timeline, riporta Live al beat zero e lascia il
trasporto fermo fino al prossimo Play.
Non occorre premere Invio. Alla chiusura si ripristina la modalità di ingresso
del terminale. Con ingresso rediretto, i tasti non sono attivi.
Gli stessi comandi sono disponibili nel viewer.

Pausa, ripresa e restart richiedono il device con `transport_control`
e il collegamento della voce `transport_voice`. I comandi agiscono sul
trasporto globale di Live; pausa e restart cancellano i piani delle voci
raggiungibili e spengono le note.

La pausa conserva la posizione: in modalità allocata, alla ripresa viene
ripetuta la prima finestra non conclusa. Il restart azzera viaggio,
timeline e memoria dei generatori, mantenendo valori manuali e preset;
lascia Live fermo al beat zero. La ripartenza richiede Play o il comando
di ripresa. Un comando non disponibile viene segnalato senza interrompere
la sessione. Protocollo e gestione dei duplicati sono in
[Voce M4L](VOCE-M4L.md#protocollo-e-arresto).

## Configurazione

Il [riferimento dei campi e dei parametri](CONFIGURAZIONE.md) riporta unità,
limiti e precedenze. L'[indice dei preset](../presets/README.md) distingue
i file per responsabilità e comando che li utilizza.

`presets/organico.json` contiene:

- `transport_voice`, `window_beats`, `lead_beats`;
- `generators`: definizioni dei generatori con tipo, impostazioni e preset;
- `voices`: identificativo, nome descrittivo, generatore, destinazione e dipendenze;
- `sections`: nome, progressione iniziale, altezza di riferimento, scala e assegnazioni delle parti.

Ogni voce riceve una propria istanza del generatore, anche quando più voci fanno riferimento alla stessa definizione. Le implementazioni concrete vengono collegate da `cli/generators.py`; Director e Coordinator lavorano con le interfacce musicali comuni.

I preset dei generatori sono insiemi di parametri. Le modifiche manuali persistono tra sezioni. Il menu **Role** permette di seguire la sezione o mantenere un ruolo manuale tra quelli supportati dal generatore. Il ruolo manuale non attiva una voce esclusa dall'organico.

### Direzione dalle macrosezioni

`presets/direzione-viaggio.json` contiene:

| Campo | Contenuto |
|---|---|
| `analysis` | Percorso del JSON dei criteri di analisi |
| `grouping` | Percorso del JSON delle famiglie di macrosezioni |
| `families` | Assegnazioni per ciascuna famiglia; root e scala esplicite oppure risolte automaticamente |
| `automatic_music` | Tavolozze selezionate dal profilo, materiale melodico e override |

I due percorsi sono relativi al file di direzione. Ogni famiglia del
raggruppamento richiede un assetto musicale; famiglie mancanti o aggiuntive
producono un errore. Ruoli, parametri e dipendenze delle sezioni prodotte
sono verificati tramite la validazione della sessione esistente.

`cli/trip_direction.py` collega analisi, raggruppamento e assetti musicali,
producendo le sezioni che il Director già accetta. Il Director seleziona il
contesto e le assegnazioni; il Coordinator continua a pianificare le voci
secondo le loro dipendenze. Il campo `selection_mode: manual` di `organico.json`
indica che le voci sono assegnate esplicitamente, anche quando i confini
delle sezioni derivano dal viaggio.

La configurazione d'ascolto fornita mantiene le quattro voci in tutte le
macrosezioni. Le voci intonate condividono root e scala selezionate dalla
direzione automatica del percorso; la percussione usa le note di `lanes`.
Le famiglie conservano i seguenti parametri musicali, modificabili nel JSON:

| Famiglia | `voice_01`: attività / passo in beat / articolazione / velocity | `voice_02`: densità / sincopazione / articolazione |
|---|---|---|
| `level` | 0,4 / 1,5 / 0,9 / 75 | 0,5 / 0,05 / 0,9 |
| `ascent` | 0,55 / 1 / 0,8 / 88 | 0,8 / 0,1 / 0,85 |
| `descent` | 0,85 / 0,5 / 0,65 / 82 | 1,2 / 0,35 / 0,65 |

| Famiglia | `voice_03`: ruolo / velocity | `voice_04`: rapporto velocity |
|---|---|---|
| `level` | `sustained_texture` / 45 | 0,75 |
| `ascent` | `sustained_texture` / 55 | 0,85 |
| `descent` | `sustained_texture` / 48 | 0,9 |

`voice_03` usa `sustained_texture`, con `degree: 0` e `octave: 1`:
in modalità indipendente sostiene la root della sezione un'ottava sopra.
`follow_source` sceglie invece una classe di altezza dalla frase melodica.
La nota viene riarticolata a ogni finestra: [regole della tessitura](TESSITURA.md).

Le tabelle indicano i valori base delle famiglie. Le politiche adattive
calcolano gli obiettivi e le transizioni dei controlli gestiti; i valori
manuali hanno precedenza. Gli altri parametri seguono l'assetto configurato.
Il cambio di macrosezione conserva lo stato compositivo dei generatori.
Le fasce interne alimentano il contesto locale anche quando appartengono
alla stessa famiglia. Formule e tempi sono in
[Direzione musicale](DIREZIONE-MUSICALE.md#adattamento-dei-parametri).

## Generatori disponibili nel registro

`cli/generators.py` costruisce un'istanza per voce. I controlli e i vincoli
completi sono nel [riferimento della configurazione](CONFIGURAZIONE.md).

| Tipo | Comportamento e riferimento |
|---|---|
| `motif` | Sviluppa un motivo in gradi nel contesto armonico; supporta `melody`, `bass_line` e `sustained_texture`. [Melodia](MELODIA.md) |
| `responsive_line` | Compone il basso dalla frase di una dipendenza obbligatoria, mantenendo continuità fra finestre. [Basso](BASSO.md) |
| `sustained_texture` | Una nota per finestra dal grado di sezione o da una dipendenza; nella prova legge facoltativamente `voice_01`. [Tessitura](TESSITURA.md) |
| `percussion_phrase` | Sviluppa materiale precomposto e stili, con sostegni al basso e risposte alla melodia. [Stili percussivi](STILI-PERCUSSIVI.md) e [dialogo](DIALOGO-MUSICALE.md) |

La destinazione percussiva della prova usa i 16 pad MIDI 36…51 del 909 Core
Kit, definiti in `adapters/percussion.py`. Il timbro di tutte le voci si
sceglie negli strumenti Live.

## Stato globale

La vista del terminale si aggiorna ogni secondo anche durante Play, mostrando posizione, beat, sezione, collegamenti, ruoli e controlli. In un terminale interattivo ridisegna la vista nello stesso spazio; quando l’output è rediretto scrive un nuovo blocco ogni secondo. Lo snapshot completo è scritto atomicamente, al massimo ogni 250 ms, in:

```text
/tmp/desnivel-session/state.json
```

`--status-file` cambia il percorso. Lo snapshot contiene:

| Campo | Contenuto |
|---|---|
| `state`, `error` | Stato della sessione ed eventuale errore di esecuzione |
| `trip` | Tappa, secondi raggiunti, durata, distanza, progressione e velocità di replay |
| `section` | Contesto della sezione alla posizione corrente del viaggio |
| `transport` | Sorgente, ultimo Play/Stop ricevuto, beat e contatore delle discontinuità |
| `planning` | Ultimo inizio pianificato, relativa sezione e durata della finestra |
| `voices` | Nomi, generatori, dipendenze, collegamenti, ruoli, controlli, motivo dell’esclusione dall’organico, prossimo ingresso configurato e ultimo piano inviato |
| `decisions` | Selezione attuale del Director e dettaglio dell’ultimo piano inviato dal Coordinator |

Il Director espone l'intervallo di progressione che seleziona la sezione e le assegnazioni con origine `section` o `manual`. Il Coordinator registra l'ordine effettivo delle chiamate, le dipendenze, il ruolo e i parametri passati a ciascun generatore e le note restituite. Il terminale mostra un riepilogo delle note come `altezza MIDI@beat relativo`; lo snapshot conserva l'elenco completo con durata e velocity. Dopo Stop o cancellazione dei piani, il dettaglio del piano viene svuotato.

Con `--direction`, `section.trip` descrive la macrosezione corrente: indice,
famiglia, confini, zone originali incluse e misure del raggruppamento.
`decisions.coordinator.trip` identifica la macrosezione dell'ultimo piano
inviato. Il terminale mostra separatamente posizione corrente e assetto del
piano; quest'ultimo può appartenere alla macrosezione precedente finché non
viene pianificata una nuova finestra. Nella modalità manuale questi campi
valgono `null`.

Una parte collegata può essere esclusa dall’organico della sezione: la vista indica il motivo e il prossimo ingresso previsto. La selezione manuale del ruolo non la attiva. Nella direzione fornita tutte e quattro le voci partecipano alle macrosezioni; l’ingresso del basso al 30% riguarda soltanto le sezioni manuali di `organico.json`.

Lo stato dei piani descrive ciò che Python ha inviato, non una conferma audio dello strumento. La scrittura JSON è separata dal motore.

`decisions.coordinator.local_trip` descrive il tratto rappresentato dalla
finestra futura e le relative misure di pendenza;
`decisions.coordinator.observation` riassume gli ultimi 16 beat accettati
per voce. La vista terminale mostra il tratto pianificato e i beat di
storia disponibili quando lo spazio lo consente. Definizioni e limiti
sono in [Direzione musicale](DIREZIONE-MUSICALE.md) e
[Dialogo ritmico](DIALOGO-MUSICALE.md). Questi ingressi alimentano le politiche adattive dei controlli nella
sessione guidata dal GPX, rispettando il manuale per parametro.

### Dimensioni della vista terminale

La plancia adatta le righe alla larghezza del terminale. Se il contenuto
supera l'altezza disponibile, mantiene stato, collegamenti delle voci,
riepilogo del piano, errori e comandi, mostrando i dettagli che entrano.
Un messaggio segnala la riduzione. Allargando la finestra i dettagli
riappaiono; lo snapshot JSON conserva sempre lo stato completo. L'output
reindirizzato a file mantiene la vista integrale.

## Registrazione audio e MIDI in Live

Usare il terminale in cui è in esecuzione la sessione Python:

| Tasto | Operazione |
|---|---|
| `C` | Collega le Voice |
| `1` | Prepara le tracce audio REC |
| `2` | Prepara le tracce MIDI REC |
| `3` | Prepara entrambe |
| `G` | Riporta viaggio e trasporto a zero; dopo la conferma di Live, avvia la registrazione in Arrangement |
| `S` | Ferma la registrazione |

Attendere lo stato **REC pronta** dopo la preparazione, poi premere `G`.
La dashboard offre le stesse operazioni con selettore e pulsanti REC.
Il terminale della sessione e la dashboard mostrano l’esito confermato dal device.

Da un secondo terminale, con il viewer attivo, gli stessi comandi REC sono
disponibili tramite `desnivel.cli.recording`:

```sh
.venv/bin/python -m desnivel.cli.recording both
.venv/bin/python -m desnivel.cli.recording start
.venv/bin/python -m desnivel.cli.recording stop
```

Attendere la preparazione prima di `start`. `audio` e `midi` selezionano
una sola modalità; `--view-port` cambia la porta HTTP predefinita 8765.

La preparazione ferma Live e riporta il viaggio a zero. Individua le tracce
con un solo `Desnivel_Voice` al livello principale della catena, riconosciuto
dal nome del device. I nomi delle sorgenti devono essere univoci.

| Destinazione | Contenuto | Ingresso |
|---|---|---|
| `<sorgente>_AUDIO_REC` | Traccia audio senza device | Sorgente, `Post Mixer`: effetti, volume e pan inclusi; ritorni esclusi |
| `<sorgente>_MIDI_REC` | Copia della traccia con strumenti ed effetti; `Desnivel_Voice` e clip copiate rimossi | Sorgente, `Post FX`: MIDI dopo gli effetti MIDI, prima dello strumento |

Gli eventuali effetti MIDI conservati nella copia agiscono anche durante
la riproduzione del MIDI registrato. Le tracce REC compatibili già esistenti
vengono riutilizzate senza cancellarne le clip o aggiornare la catena.
Un nome occupato da una traccia incompatibile interrompe la preparazione.
Un errore di creazione o routing elimina soltanto le nuove tracce create
dall’operazione fallita.

Il monitor delle destinazioni è impostato su `Off`. Durante la registrazione
sono armate soltanto le destinazioni selezionate; loop, punch, quantizzazione
MIDI in registrazione e overdub Arrangement vengono temporaneamente disattivati.
Stop ripristina armamenti e impostazioni precedenti.
Il count-in di Live deve essere su **None** nel menu accanto al metronomo,
alla voce **Count-In**. Spegnere il metronomo o impostare la quantizzazione
globale su None non cambia il count-in.
Le destinazioni restano disarmate dopo la preparazione: `G` le arma prima
di avviare REC. Un errore nei controlli preliminari impedisce anche l’armamento.
La fine della tappa richiede
automaticamente l’arresto della registrazione.

`adapters/live_recording.py` governa richieste e conferme; la voce del
trasporto esegue le operazioni con `m4l/desnivel_recording.js`.
La capability `recording_control` identifica i device aggiornati;
`recording` nello snapshot contiene stato, modalità, destinazioni ed errore.
I timeout non fanno partire la registrazione e vengono segnalati.

## Mappa del viaggio

Con `--view-port 8765`, aprire <http://127.0.0.1:8765/> nel browser.
Il launcher multitappa abilita già questa opzione.

La pagina mostra percorso completo, tratto attraversato, posizione geografica,
distanza raggiunta e restante, percentuale, tempo del viaggio e sezione attuale.
**Intero percorso** adatta la mappa alla traccia; **Segui posizione** mantiene
il punto corrente al centro. Trascinare la mappa disattiva l'inseguimento.
Il collegamento sulle coordinate apre la posizione su OpenStreetMap.

Il pannello musicale distingue il piano corrente secondo il beat di Live
dal prossimo piano già inviato: mostra sezione, root MIDI, scala e tratto
del percorso. Le schede delle voci indicano collegamento, ruolo e numero
di note della frase corrente, organico attuale, presenza e parametri.
I valori effettivi sono affiancati dagli obiettivi automatici con `→`;
ogni parametro indica `auto` o `manual`. La configurazione completa
è espandibile. I riepiloghi diagnostici marcati «ultimo piano inviato»
possono riferirsi alla finestra futura.

Il runtime conserva i piani inviati non ancora conclusi per esporre
`planning.current` e `planning.upcoming` nello snapshot. Stop e reset
svuotano tale stato insieme alla pianificazione; la lettura della dashboard
non genera frasi e non cambia i parametri. L’esecuzione indicata segue
il clock, senza misurare l’uscita audio degli strumenti.

Il selettore **Skin** nell'intestazione cambia l'aspetto della pagina:
**Atlante** usa la cartografia chiara, **Notturna** applica colori scuri ai
tasselli e mette in risalto percorso attraversato e posizione. Il trattamento
è applicato nel browser agli stessi tasselli OpenStreetMap; non richiede
un altro servizio cartografico. La scelta vale per la pagina aperta e torna
ad Atlante al caricamento. Il cambio conserva posizione, zoom e inseguimento.

La posizione segue i secondi attivi dello snapshot, anche in modalità
`allocated`, dove il runtime li ricava dalla distanza raggiunta nella timeline.
La vista interpola le coordinate solo all'interno dei tratti osservati e
mantiene separate le interruzioni. Stop e attese conservano la posizione;
un mancato aggiornamento per oltre tre secondi viene segnalato nella pagina.

`viewer/route.py` prepara una volta la geometria dalla stessa traccia caricata
dalla sessione. `viewer/server.py` serve le risorse, legge lo snapshot e
accoda i comandi in un thread HTTP separato. Il ciclo CLI consuma la coda
e applica i comandi nello stesso thread della pianificazione musicale.
`position.js` calcola posizione e tratto attraversato; `music.js` presenta
piani e voci; `view.js` aggiorna la
pagina ogni 250 ms, dopo la conclusione della richiesta precedente.
Le interfacce HTTP in sola lettura sono `/api/route` (versione, tappa e segmenti
di punti `[secondi attivi, latitudine, longitudine]`) e `/api/state`
(`session`, snapshot completo, e `age_s`, età del file in secondi).

`POST /api/control` accetta un oggetto `{"action":"<azione>"}` soltanto
dalla stessa origine. Le azioni sono `pause`, `resume`, `restart`,
`record_audio`, `record_midi`, `record_both`, `record_start` e `record_stop`. La risposta `202` conferma
l'accodamento; l'esito è mostrato nello snapshot successivo.
**Pausa/Riprendi** e **Riporta a zero** sono disponibili durante il
viaggio. A fine tappa compare la domanda con il pulsante **Sì, riporta a zero**;
la ripartenza richiede un successivo Play.

Il server ascolta solo su `127.0.0.1` e si chiude con la sessione. La porta HTTP
deve essere libera e distinta da quella OSC. Per sessioni contemporanee usare
porte e percorsi `--status-file` distinti. Senza `--view-port` il server HTTP
non viene avviato; `--dry-run` non lo avvia.

La cartografia usa i tasselli standard di OpenStreetMap e la libreria
[Leaflet 1.9.4](https://leafletjs.com/examples/quick-start/) caricata da unpkg:
richiedono una connessione Internet. Il browser richiede soltanto i tasselli
dell'area visibile, con attribuzione e cache ordinarie, secondo la
[politica del servizio](https://operations.osmfoundation.org/policies/tiles/).
Se i tasselli non sono disponibili, geometria e posizione restano visibili
quando Leaflet è già caricato. La pagina segnala anche l'assenza della libreria.

## Verifiche

I test coprono pianificazione, cambi di sezione, trasporto, dispositivi
mancanti, ruoli, controlli, snapshot, registrazione e dashboard.
`--dry-run` verifica configurazione e generazione delle sezioni; non
riproduce il trasporto o l'audio di Live. Le prove d'ascolto servono a
valutare suoni e corrispondenze compositive.
