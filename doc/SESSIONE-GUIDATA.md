# Sessione guidata

Il launcher `comandi/09 - Sessione multitappa.command` mostra le sessioni
salvate in `output/sessioni/`. Scegliere un numero per caricarne una oppure
`0` per crearne una nuova, assegnandole un nome. **A: apri file…** apre
il dialogo macOS per scegliere una configurazione `.json` in qualsiasi
cartella. Annullando il dialogo si torna al menu. Le nuove sessioni partono
senza voci dalla base `presets/sessione.json`; **V** le salva in
`output/sessioni/<nome>.json`. I nomi già presenti vengono rifiutati durante
la creazione. Il file `output/sessione.json`, se presente, compare anch'esso
nel menu e conserva il proprio percorso.

Il nome della sessione attiva è visibile nel pannello. Ogni configurazione
ha la propria libreria `<nome>.voice-presets.json`, salvo l'uso esplicito
di `--voice-presets`. Questi file di preset non compaiono nel menu delle sessioni.

Per una nuova sessione si sceglie la tappa. Il viaggio mantiene direzione GPX,
timeline allocata e mappa sulla porta 8765. La scelta `99` apre il selettore
di un file FIT o GPX. **Salva sessione** e **V** conservano anche il file del
viaggio, l'eventuale FIT di riferimento per le pause e la scelta di stimare
le pause nei FIT senza eventi timer. Riaprendo la sessione, il launcher
riutilizza il viaggio salvato senza richiederlo. Le sessioni prive di questo
riferimento chiedono la tappa; un successivo salvataggio la conserva.
Per passare a un'altra sessione, chiudere il launcher
con Ctrl+C e riaprirlo. Un percorso esplicito evita il menu:

```sh
.venv/bin/python -m desnivel.cli.launch_stage --config "output/sessioni/ambient.json"
```

Per sostituire il viaggio della sessione, usare `--tappa 01` oppure
`--tappa 99` per aprire il selettore FIT/GPX. La sostituzione viene conservata
quando si salva la sessione. Se il file salvato è stato spostato, il launcher
segnala il percorso mancante e richiede una selezione esplicita con `--tappa`.

La configurazione può contenere un numero variabile di voci. Una sessione
vuota resta in preparazione; la prima voce associata diventa la sorgente
del trasporto. Non è previsto un massimo di quattro voci. Le risorse di
Live, del processo Python e delle porte UDP limitano la capacità effettiva.

## Pannello web locale

Dopo l'avvio dal launcher, aprire <http://127.0.0.1:8765/session/>.
Il pannello mostra la sessione attiva, le tracce rilevate e il loro collegamento.
**Associa una traccia** avvia la stessa procedura del terminale: scelta della
destinazione, nome, voce musicale, comportamento ed eventuali sorgenti.
**Ricollega una voce** sostituisce la destinazione; **Salva sessione** scrive
nel file della configurazione attiva. Sono presenti anche trasporto,
preparazione REC e registrazione audio/MIDI. **Cosa sta suonando** mostra
il piano corrente, quello successivo e il riepilogo meteo.
**Viaggio** apre la mappa. Entrambe le pagine condividono i colori e le
skin Atlante e Notturna, selezionabili nell'intestazione.

La scelta iniziale della configurazione e del viaggio resta nel launcher,
con menu e dialoghi macOS. Per usare il pannello senza tastiera e rendering
del terminale durante l'esecuzione:

```sh
.venv/bin/python -m desnivel.cli.launch_stage \
  --config output/sessioni/ambient.json --tappa 01 --no-terminal
```

`--view-port` cambia la porta HTTP. Il comando diretto `desnivel.cli.ensemble`
avvia il server web soltanto quando riceve questa opzione; il launcher la
imposta a 8765. `Ctrl+C` termina il processo anche con `--no-terminal`.

Il pannello usa HTML, CSS e JavaScript locali senza dipendenze aggiuntive.
Legge lo snapshot e accoda comandi al processo Python, che valida e applica
ogni modifica nello stesso ciclo della pianificazione. Se lo stato non viene
aggiornato per tre secondi, il pannello disabilita i controlli. La chiusura
della pagina lascia attiva la sessione.

## Preparazione in Live

Usare i device costruiti dalle sorgenti correnti del progetto:

```sh
.venv/bin/python tools/build_voice_device.py --output output/desnivel-voice --update
.venv/bin/python tools/build_snake_control.py --output output/sessione-snake-control
```

Entrambi i builder accettano `--update` per aggiornare una cartella esistente.
I file `.amxd` e le relative
dipendenze JavaScript devono restare nella stessa cartella. Ricaricare i
device in Live dopo la ricostruzione.

Per una voce Python, preparare una traccia MIDI con
`Desnivel_Voice → strumento`. Per Snake, preparare
`Snake con Length → Desnivel_Snake_Control → strumento`.
La creazione della traccia e l'inserimento dei device avvengono in Live.

I controlli annunciano la propria presenza anche prima dell'associazione.
L'inventario considera i controlli al livello principale delle normali
tracce di Live. Le tracce senza controllo Desnivel, comprese le copie REC,
non entrano nel conteggio. Più controlli sulla stessa traccia, identità
copiate e porte Receive duplicate sono segnalati come conflitti.

## Comandi

La schermata di preparazione mostra le tracce rilevate, il loro stato e
la domanda corrente. I parametri musicali completi sono nella vista
**D: dettagli**. Il terminale usa uno schermo dedicato e ripristina quello
precedente all'uscita.

| Tasto | Azione |
|---|---|
| **A** | Associa una traccia disponibile e crea la voce |
| **B** | Sceglie una voce esistente da ricollegare |
| **T** | Ripete la ricerca dei controlli nel set aperto |
| **V** | Salva la configurazione |
| **D** | Mostra o nasconde i dettagli musicali e diagnostici |
| **Esc** | Annulla la domanda corrente e torna alla preparazione |

Durante la procedura si scrive il numero della scelta e si preme Invio.
Nomi e posizioni delle tracce sono mostrati nella tabella; le scelte di
sorgente usano i nomi delle voci. L'identificativo tecnico resta disponibile
nella vista dettagli e nei comandi testuali.

Premere `:` per aprire un comando testuale, quindi Invio:

| Comando | Effetto |
|---|---|
| `tracce` | Mostra tracce rilevate, associazioni, assenze e conflitti |
| `aggiungi traccia` | Guida nella scelta della destinazione e nella creazione della voce |
| `associa <id voce>` | Sostituisce la destinazione di una voce esistente con un controllo compatibile |
| `rimuovi <id voce>` | Rimuove voce e associazione dalla configurazione |
| `trasporto <id voce>` | Sceglie il controllo che fornisce il trasporto di Live |
| `ritmo <id voce>` | Sceglie un generatore capace di fornire il riferimento ritmico |
| `ritmo nessuna` | Rimuove il riferimento ritmico, se i parametri delle voci lo consentono |
| `salva` | Scrive la configurazione nel file indicato da `--config` |

La procedura di aggiunta propone le tracce disponibili con nome e posizione
in Live. La scelta `0` mostra come prepararne una nuova e continua ad
attendere gli annunci. Poi richiede il nome della voce e le sole scelte
musicali pertinenti nell'ordine **voce → comportamento → eventuali sorgenti**.

| Voce | Comportamenti |
|---|---|
| melodia | sviluppo di un motivo |
| basso | autonomo oppure in relazione a una voce |
| nota sostenuta | segue l'armonia della sezione oppure una voce |
| drums | pattern autonomo oppure in relazione ad altre voci |

Il comportamento viene chiesto soltanto quando esistono più alternative.
Le modalità in relazione ad altre voci vengono proposte quando è presente
almeno una voce Python utilizzabile come sorgente. Le sorgenti si scelgono
nel passaggio successivo. Il comportamento seleziona il generatore esistente;
ogni istanza conserva stato e parametri indipendenti. La nota sostenuta usa
il generatore di tessitura, che produce una nota lunga per finestra musicale.

Un controllo Snake propone melodia, basso o nota sostenuta, con comportamento
autonomo oppure in relazione a una voce Python.
Snake può essere l'unica traccia della sessione e fornire il trasporto.
`N` apre la stessa procedura di aggiunta nelle sessioni guidate.

Aggiunta, associazione, rimozione e scelta delle sorgenti richiedono Live
fermo e nessuna operazione REC in corso. Una modifica viene validata prima
di sostituire la sessione; conserva avanzamento del viaggio e controlli
manuali delle voci mantenute, e invalida i piani musicali precedenti.
Le tracce REC devono essere preparate nuovamente dopo una modifica.
La rimozione è rifiutata se la voce è ancora una dipendenza, una sorgente
Snake, un riferimento ritmico o parte di una relazione musicale.
La rimozione dalla configurazione non cancella tracce in Live.

## Controlli già presenti nel set

Il rilevamento richiede le sorgenti correnti del controllo, comprese la
patch `.amxd` e le dipendenze JavaScript. Per aggiornare le copie nella
User Library standard di Ableton:

```sh
.venv/bin/python tools/build_voice_device.py \
  --output "$HOME/Music/Ableton/User Library/MaxForLive/desnivel/Desnivel_Voice" --update
.venv/bin/python tools/build_snake_control.py \
  --output "$HOME/Music/Ableton/User Library/MaxForLive/desnivel/Desnivel_Snake_Control" --update
```

Ricaricare i controlli nelle tracce dopo l'aggiornamento. Le istanze già
aperte conservano la patch caricata; il comando di costruzione aggiorna
il file nella cartella indicata.

La sessione richiede il collegamento anche ai controlli preesistenti tramite
la porta `--connect-port`. Se un controllo risponde senza annunciare i dati
della traccia, la schermata lo mostra come **controllo da aggiornare**, con
l'identificativo della voce salvata nel device. In questo stato non viene
proposta un'associazione: servono aggiornamento e ricaricamento del controllo.
**T** ripete la ricerca. Un controllo che invia l'inventario viene mostrato
con il nome effettivo della traccia.

## Identità, collegamento e salvataggio

Il device conserva un'identità separata dall'identificativo della voce.
Un valore iniziale vuoto o numerico non è un'identità valida: il controllo
genera e memorizza un nuovo identificativo alla prima inizializzazione in Live.
Nome e posizione della traccia servono alla visualizzazione: rinomina e
riordino non cambiano l'associazione. Salvare il Live Set per conservare
l'identità del controllo. Un controllo duplicato con la stessa identità
va rimosso dalla copia e inserito nuovamente.

Il rilevamento usa OSC locale sulla porta Python 9006. Le porte Receive
predefinite vengono assegnate in base all’istanza Live; le altre porte
impostate vengono conservate. Eventuali collisioni sono visibili nell'inventario e si risolvono cambiando Receive.
Il terminale imposta voce e porta Python quando associa il controllo.
Le associazioni salvate vengono riproposte ai device presenti; un device
assente resta indicato come tale, senza sostituzioni automatiche.

La configurazione distingue:

- `voices` e `generators`: voci Python e istanze dei generatori;
- `arrangement`: ruoli applicati alle macrosezioni prodotte dalla direzione;
- `transport_voice` e l'eventuale `rhythm_voice`: sorgenti con responsabilità distinte;
- `live_bindings`: associazioni fra identificativi delle voci e identità dei controlli;
- `journey`: file del viaggio, eventuale `timing_reference` e `infer_fit_pauses`;
- l'eventuale `snake`: ricetta musicale, percorsi e componenti dell'adattatore;
- l'eventuale `component_names`: nomi leggibili dei componenti esterni.

`salva` conserva questa configurazione e le associazioni. I controlli manuali
modificati durante l'esecuzione restano stato della sessione; i preset utente
si salvano tramite i controlli già disponibili nei device.

I percorsi in `journey` sono relativi alla cartella della configurazione.
Il comando diretto `desnivel.cli.ensemble --config <file>` usa questo
riferimento quando `--track` è omesso. Una traccia esplicita lo sostituisce;
cambiando file, il precedente riferimento timer non viene riutilizzato.

## Organico di esempio

La configurazione `presets/organico.json` mantiene il banco a quattro voci:

```sh
.venv/bin/python -m desnivel.cli.launch_stage --config presets/organico.json
```

Questo percorso conserva i comandi di collegamento e la preparazione Snake
dedicata descritti in [Sessione multivoce](SESSIONE-MULTIVOCE.md) e
[Snake](SNAKE.md). La creazione guidata delle voci usa le configurazioni
con `arrangement`, come la nuova sessione del launcher.
