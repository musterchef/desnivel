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

Dalla radice del repository:

```sh
.venv/bin/python -m desnivel.cli.ensemble \
  --gpx gpx/tappa05_Firenze_San_Gimignano.gpx \
  --config presets/organico.json \
  --speed 50
```

Per verificare configurazione e generazione delle sezioni senza aprire porte o inviare note, aggiungere `--dry-run`.

La configurazione fornita abilita guida delle drums e influenze reciproche. Il [riferimento del dialogo ritmico](DIALOGO-MUSICALE.md)
descrive adesione delle voci, memoria, configurazione e diagnostica.

`--track` accetta FIT e GPX; `--gpx` resta un alias. Per una prova con FIT:

```sh
.venv/bin/python -m desnivel.cli.ensemble \
  --track fit/Da_Piazza_Castello_al_Castel_lo_tappa_6_Orvieto_Bagnoregio_Lago_di_Bolsena.fit \
  --config presets/organico.json \
  --direction presets/direzione-viaggio.json \
  --timing allocated
```

Se la sorgente è GPX, `--timing-reference percorso.fit` permette di usare
gli eventi timer del FIT corrispondente mantenendo coordinate e quota del GPX.
Dettagli e provenienza dei canali in
[ANALISI-PERCORSO.md](ANALISI-PERCORSO.md#sorgenti-fit-e-gpx).

Per usare le macrosezioni del percorso e i relativi assetti musicali:

```sh
.venv/bin/python -m desnivel.cli.ensemble \
  --gpx gpx/tappa05_Firenze_San_Gimignano.gpx \
  --config presets/organico.json \
  --direction presets/direzione-viaggio.json \
  --speed 50
```

Il campo `direction` delle configurazioni fornite carica la direzione GPX
all'avvio; `--direction` può sostituirla. Confini e assetti derivano dalle
macrosezioni, mentre il profilo sceglie tavolozza e motivo. Per usare le
sezioni manuali aggiungere `--manual-sections`. Criteri e override in
[Direzione musicale dal percorso](DIREZIONE-MUSICALE.md).

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

Al termine del viaggio la sessione spegne le note e mostra `finished`. Ctrl+C chiude il server e scrive lo stato `closed`. Un errore di generazione porta allo stato `error`; il restart permette un nuovo tentativo dall'inizio.

### Pausa e restart

Il tasto **C** nel terminale interattivo invia **Collega tutte** ai device
Voice. Usa la porta Receive 9101, configurabile con `--connect-port`,
senza modificare il trasporto o lo stato del viaggio.

Nel terminale interattivo, **Spazio** mette in pausa o riprende viaggio e
trasporto di Live; **R** ricomincia la tappa e riporta Live al beat zero.
Non occorre premere Invio. Alla chiusura si ripristina la modalità di ingresso
del terminale. Con ingresso rediretto, i tasti non sono attivi.
Gli stessi comandi sono disponibili nel viewer.

Il controllo di Live richiede il device aggiornato, dotato di
`transport_control`, e il collegamento della voce configurata in
`transport_voice`. Python invia il comando solo a quell'istanza del device,
che controlla il trasporto globale del Live Set. Gli altri device ricevono
la cancellazione dei propri piani. Le notifiche di trasporto ricevute da
Live non generano altri comandi di trasporto. Le richieste ripetute di pausa
sono ignorate quando la sessione è già in pausa; i device scartano comandi
duplicati per sessione e seriale.

La ripresa usa `continue_playing`; il restart usa `stop_playing`, imposta
`current_song_time` a zero e riprende. La pausa cancella i piani e spegne
le note di tutte le voci raggiungibili. Nel replay lineare conserva i secondi
raggiunti; nella timeline allocata conserva la prima finestra non conclusa,
che viene ripetuta alla ripresa. Il restart azzera posizione, timeline e
memoria dei generatori, mantenendo i valori manuali e la libreria dei preset.
A fine tappa, terminale e viewer propongono di ricominciare; non avviene una
ripartenza automatica. Un comando non disponibile viene segnalato senza
interrompere la sessione.

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

`presets/direzione-viaggio.json` contiene tre campi:

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

`voice_03` usa il generatore `sustained_texture` con `degree: 0` e
`octave: 1`: in modalità indipendente produce la nota MIDI 69 nel contesto
fornito. Lo switch **Segui sorgente** (`follow_source`) seleziona invece un
sostegno dalla frase di `voice_01`, letta come dipendenza facoltativa.
La durata è quella della finestra e la nota viene riarticolata nella
finestra seguente. Registro e dinamica sono configurabili; `soft` e
`present` impostano velocity 40 e 65. Vedi [Tessitura sostenuta](TESSITURA.md).

I parametri non specificati usano le impostazioni del generatore; le
regolazioni manuali hanno precedenza. Gli assetti vengono copiati per ogni
macrosezione: tornando alla stessa famiglia si riprendono i valori configurati,
senza accumulare modifiche della macrosezione precedente. Il cambio entra
nella prossima finestra ancora da pianificare, senza cancellare lo stato dei
generatori. Non viene applicata un'interpolazione graduale dei parametri.

Le fasce interne non modificano l'assetto: `climb` e `steep_climb` nella
stessa `ascent` mantengono contesto e parametri di sezione identici. La
generazione continua a sviluppare le frasi secondo il proprio algoritmo.
I controlli della prova agiscono su note e ritmo, non sui parametri timbrici
degli strumenti in Live.

## Generatori disponibili nel registro

### `motif`

Implementato in `music/melodic/generator.py`. Riceve un motivo di gradi non negativi (`degrees`) e il contesto di tonica e scala della sezione. Espone registro, ritmo, articolazione, velocity, sviluppo, attività, lunghezza del periodo e seed.

- `melody`: con `development > 0` sviluppa il motivo su più finestre con presentazione, elaborazione, contrasto e conclusione. Con valore `0` ripete il motivo su passi regolari.
- `bass_line`: articola il motivo letterale nel registro assegnato.
- `sustained_texture`: produce una sola nota, dal primo grado configurato, sostenuta per tutta la finestra.

Il generatore controlla il registro MIDI e limita gli eventi per finestra. Le regole e i controlli sono descritti in [MELODIA.md](MELODIA.md).

### `sustained_texture`

Implementato in `music/texture/generator.py`. Supporta il ruolo omonimo
con una nota per finestra, guidata dal grado di sezione oppure dalla frase
di una dipendenza. Espone `octave`, `velocity` e lo switch `follow_source`.
La prova assegna a `voice_03` la sorgente facoltativa `voice_01`.
Le regole sono descritte in [TESSITURA.md](TESSITURA.md).

### `responsive_line`

Collega il generatore presente in `music/bass/` attraverso `music/bass/voice.py`. Supporta `bass_line` e richiede una sola dipendenza: la frase da accompagnare. Conserva l'ultima altezza fra finestre contigue e cancella tale continuità quando il runtime riparte dalla pianificazione.

I controlli esposti sono `density`, `syncopation`, `rhythm_follow`, `melody_follow`, `mobility`, `variation` e `articulation`. Le altre impostazioni del generatore, incluso il registro, si configurano in `settings` o nei parametri di sezione; `strategy` è solo iniziale. Le regole compositive sono descritte in [BASSO.md](BASSO.md).

### `percussion_phrase`

La prova usa `music/percussion/development.py`, con il ruolo `percussion`.
Legge la frase di `voice_01` e, quando attiva, quella di `voice_02`.
Il materiale di 32 beat attraversa le finestre di pianificazione e segue
una sequenza configurata di ripetizioni, sottrazioni, spostamenti, accenti
e sospensioni. Alcuni attacchi sono protetti dalle trasformazioni locali.
I colpi di sostegno si allineano agli attacchi vicini della seconda
sorgente; le risposte lasciano spazio agli attacchi della prima. La plancia
espone operazione, posizione logica, sorgenti effettive, sostegni e risposte omesse. Cambiare
famiglia del terreno conserva la posizione; Stop e reset la azzerano.

Le famiglie regolano soltanto il rapporto di velocity della voce. I
controlli di sviluppo e i preset sono descritti nel
[riferimento di configurazione](CONFIGURAZIONE.md#parametri-del-generatore-percussion_phrase).
La mappa in `adapters/percussion.py` copre i 16 pad MIDI 36…51 del 909 Core Kit
della prova, con entrambe le casse assegnate al sostegno. Il timbro dipende dai suoni caricati su quei pad. Le note MIDI e le
regole ritmiche risiedono rispettivamente nell’adattatore e nel catalogo
della voce;
Director, Coordinator e dispositivo usano le interfacce comuni.

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

Una parte può essere collegata al server ma esclusa dall'organico della sezione. In `presets/organico.json`, `voice_02` entra al 30% della distanza: prima di quel punto la vista indica il motivo dell'attesa e la soglia d'ingresso. La selezione manuale del ruolo non modifica questa attivazione.

Lo stato dei piani descrive ciò che Python ha inviato, non una conferma audio dello strumento. La scrittura JSON è separata dal motore.

## Mappa del viaggio

Aggiungere `--view-port 8765` al comando della sessione e aprire
<http://127.0.0.1:8765/> nel browser. Per esempio:

```sh
.venv/bin/python -m desnivel.cli.ensemble \
  --track gpx/tappa05_Firenze_San_Gimignano.gpx \
  --config presets/organico.json \
  --direction presets/direzione-viaggio.json \
  --timing allocated \
  --view-port 8765
```

La pagina mostra percorso completo, tratto attraversato, posizione geografica,
distanza raggiunta e restante, percentuale, tempo del viaggio e sezione attuale.
**Intero percorso** adatta la mappa alla traccia; **Segui posizione** mantiene
il punto corrente al centro. Trascinare la mappa disattiva l'inseguimento.
Il collegamento sulle coordinate apre la posizione su OpenStreetMap.

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
`position.js` calcola posizione e tratto attraversato; `view.js` aggiorna la
pagina ogni 250 ms, dopo la conclusione della richiesta precedente.
Le interfacce HTTP in sola lettura sono `/api/route` (versione, tappa e segmenti
di punti `[secondi attivi, latitudine, longitudine]`) e `/api/state`
(`session`, snapshot completo, e `age_s`, età del file in secondi).

`POST /api/control` accetta `{"action":"pause"}`, `resume` o `restart`
solo dalla stessa origine della pagina. La risposta `202` conferma
l'accodamento; l'esito è mostrato nello snapshot successivo.
**Pausa/Riprendi** e **Ricomincia tappa** sono disponibili durante il
viaggio. A fine tappa compare la domanda con il pulsante **Sì, ricomincia**.

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

I test automatici coprono pianificazione ripetuta, passaggi di sezione, Stop,
ripartenza, discontinuità, dispositivi mancanti, ruoli, controlli e scrittura
dello stato. La configurazione fornita è verificata anche con `--dry-run`
sul GPX Firenze–San Gimignano. La prova in Live ha confermato l'esecuzione
delle parti melodica e di accompagnamento; Marco ha inoltre confermato
l'ascolto di atmosfera e drums nella prova a quattro voci. Configurazione
e comportamenti musicali costituiscono un banco di prova da affinare.


### Dimensioni della vista terminale

La plancia adatta le righe alla larghezza del terminale. Se il contenuto
supera l'altezza disponibile, mantiene stato, collegamenti delle voci,
riepilogo del piano, errori e comandi, mostrando i dettagli che entrano.
Un messaggio segnala la riduzione. Allargando la finestra i dettagli
riappaiono; lo snapshot JSON conserva sempre lo stato completo. L'output
reindirizzato a file mantiene la vista integrale.
