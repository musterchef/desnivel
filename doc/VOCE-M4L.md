# Dispositivo MIDI di voce

`Desnivel_Voice.amxd` è un effetto MIDI da collocare prima dello strumento su una traccia Live. Il dispositivo riceve frasi dal motore Python e le esegue sul trasporto di Live. La logica compositiva rimane in Python.

## Componenti

| Sorgente | Responsabilità |
|---|---|
| `m4l/desnivel_voice.maxpat` | Interfaccia, rete locale, lettura del trasporto e uscita MIDI |
| `m4l/desnivel_voice.js` | Identificazione dell'istanza, menu, controlli e collegamento con Python |
| `m4l/desnivel_transport_player.js` | Esecuzione dei piani in beat assoluti con oggetti `timepoint` |
| `src/desnivel/adapters/voice_device.py` | Validazione dei controlli e collegamento tra voci Python e dispositivi |
| `src/desnivel/cli/voice_device.py` | Server OSC locale e prova di esecuzione da file |
| `tools/build_voice_device.py` | Confezionamento dal template MIDI ufficiale di Live |

Il percorso delle note generate termina in `midiformat` e `midiout`. Il dispositivo non inoltra il MIDI in ingresso. Non carica strumenti o preset sonori.

## Costruzione

Dalla radice del repository, usando una cartella di output nuova:

```sh
.venv/bin/python tools/build_voice_device.py --output /tmp/desnivel-voice
```

Il builder usa il template `Max MIDI Effect.amxd` dell'installazione Live in `/Applications/Ableton Live 12 Suite.app`. `--template` permette di indicarne un altro percorso. Non modifica il template.

Per aggiornare direttamente la cartella installata:

```sh
.venv/bin/python tools/build_voice_device.py \
  --output "$HOME/Music/Ableton/User Library/MaxForLive/desnivel/Desnivel_Voice" \
  --update
```

`--update` riscrive `Desnivel_Voice.amxd` e i due script del dispositivo, mantenendo gli altri file della cartella. Dopo l'aggiornamento ricaricare il dispositivo in Live per usare la nuova versione.

La cartella generata contiene il device e i due script JavaScript. Conservare i tre file insieme: il device non è congelato con risorse incorporate. Il sorgente modificabile è `m4l/desnivel_voice.maxpat`.

## Interfaccia

- **Voce**: identificativo della parte registrata in Python, per esempio `voice_01`.
- **Receive**: porta UDP di questa istanza, inizialmente `9101`. Ogni istanza richiede una porta distinta.
- **Python**: porta del server locale, inizialmente `9006`.
- **Collega**: legge identificativo e porte e apre il collegamento. Se già collegato, rinnova la richiesta mantenendo identità e piani della stessa istanza.
- **Role**: menu dei ruoli supportati dal generatore collegato. `Follow section` segue il ruolo assegnato alla sezione; scegliendo un ruolo si passa alla modalità manuale. Il ruolo effettivo è mostrato in alto; per una parte esclusa dall’organico sono mostrati il prossimo ingresso configurato (`enters at ...%`) oppure `not in this section` se non sono previsti altri ingressi. Senza un collegamento ai ruoli della sessione, il menu mostra `No roles available`.
- **Preset**: preset compositivi dichiarati dal componente Python.
- **Manual**: switch del parametro selezionato nel menu, con indicatore **AUTO** o **MANUAL** confermato da Python. Modificare un valore attiva soltanto il suo flag. Spegnere lo switch restituisce quel parametro agli assetti delle sezioni, conservando gli altri valori manuali. Un preset rende manuali i valori che applica. Senza sessione collegata l'indicatore mostra `—`.
- **Parametro**, valore e cursore: modifica di uno dei controlli esposti da Python. Il cursore rispetta intervallo e vincolo intero; il campo numerico permette l’immissione precisa. I limiti sono mostrati accanto al cursore.
- I controlli binari mostrano uno switch al posto del cursore. Quelli senza effetto nel ruolo o nella modalità corrente riportano **[inattivo]** nel menu; la motivazione è nell'annotazione del controllo. Restano modificabili e conservano il valore.
- **Salva nuovo**: salva i valori effettivi della voce con il nome scritto nel campo accanto. **Aggiorna** sostituisce un preset utente già presente con quel nome. I preset base della configurazione sono protetti.
- **Presenza ×**: moltiplicatore manuale da 0 a 10, modificabile con il campo numerico o lo slider. 1 segue la presenza della sezione, 0 rende silenziose le prossime frasi. Accanto sono visibili **Auto** ed **Effettiva** in percentuale, aggiornate dalle risposte Python. Il controllo è separato dai preset del generatore; senza sessione collegata non è disponibile.
- **panic**: cancella i piani e spegne le note generate.

I menu sono riempiti dalla risposta Python. Il dispositivo non contiene nomi di strumenti, ruoli prestabiliti o parametri di un generatore specifico.

### Collegamento di tutte le voci dal terminale

Nel terminale interattivo di `ensemble`, premere **C** per inviare **Collega
tutte** mentre la sessione è accesa. La porta di ingresso predefinita è 9101;
si può scegliere un'altra porta Receive con `--connect-port 9102` all'avvio
di `ensemble`.

Con la sessione Python avviata e i device caricati in Live, dalla cartella
del progetto si può anche eseguire in un altro terminale:

```bash
.venv/bin/python -m desnivel.cli.connect_voices
```

Il comando invia `/desnivel/v1/voice/connect-all` a `127.0.0.1:9101`.
La Voice su quella porta lo distribuisce alle altre istanze tramite il
canale Max condiviso `desnivel_voice_connect_all`. Ogni istanza esegue lo
stesso percorso del tasto **Collega**, usando il proprio identificativo,
la propria porta Receive e la propria porta Python. Il comando ripetuto
mantiene identità e piani delle istanze già collegate.

Se nessuna Voice usa Receive 9101, indicare la porta di una delle istanze
caricate con `--port 9102`. Tutte le istanze devono usare il device aggiornato,
avere identificativi validi e porte Receive distinte. Il messaggio sul terminale
conferma l'invio UDP; lo stato dei collegamenti è visibile nella sessione Python
e nei device. La richiesta non modifica il trasporto di Live.

### Identità e preset utente

Il campo **Voce** è collegato a `pattr voice_identity`, un parametro Blob
`Stored Only` salvato da Live insieme alle porte. Per aggiornare istanze
create con il precedente parametro numerico, sostituire il device nel Set,
impostare identificativo e porte su ogni istanza e salvare il Live Set.

La sessione usa una libreria JSON accanto alla configurazione: con
`--config presets/organico.json`, il percorso predefinito è
`presets/organico.voice-presets.json`. `--voice-presets percorso.json`
permette di sceglierne un altro. Il file viene creato al primo salvataggio.
Contiene versione 1 e una mappa `voices`, indicizzata per identificativo
della voce e poi per nome del preset. Ogni preset conserva tutti i controlli
esposti dalla voce, con i valori effettivi al momento del salvataggio.

La libreria viene caricata all'avvio e condivisa dalle istanze collegate
alla stessa sessione. I preset sono disponibili anche in altri Live Set
avviati con la stessa configurazione e libreria. Il salvataggio è atomico,
non cambia le sezioni e non seleziona automaticamente il preset appena
creato: selezionarlo dal menu per applicarlo. Nomi duplicati richiedono
**Aggiorna**; controlli incompatibili con la configurazione vengono
segnalati all'avvio.

## Sessione continua

Per la composizione con Director, Coordinator e più parti usare il comando descritto in [SESSIONE-MULTIVOCE.md](SESSIONE-MULTIVOCE.md). Il ricevitore diagnostico seguente usa la stessa porta e va chiuso prima di avviare la sessione.

## Prima prova di esecuzione

Avviare il ricevitore con una frase già presente nel progetto:

```sh
.venv/bin/python -m desnivel.cli.voice_device \
  --voice voice_01 \
  --phrase presets/phrases/bass_sustained.json
```

1. Caricare il device prima dello strumento su una traccia MIDI.
2. Impostare `Voce` a `voice_01`, `Receive` a `9101` e `Python` a `9006`, quindi premere **Collega**.
3. Avviare il trasporto di Live.

La prova invia la frase una volta per avvio o discontinuità rilevata del trasporto, a un multiplo di quattro beat con almeno due beat di anticipo rispetto alla posizione ricevuta. Usa il file senza modificarne il contenuto musicale. Non pianifica una tappa GPX. In questa modalità il ruolo è non assegnato e i menu sono vuoti.

Senza `--phrase`, il comando verifica soltanto il collegamento. Più parti possono essere registrate ripetendo `--voice`; la prova da file ammette una sola parte.

## Collegamento al motore condiviso

`VoiceDeviceServer` riceve una mappa di identificativi a oggetti `DeviceVoice`. Ogni oggetto contiene i controlli esposti, i valori iniziali, i preset disponibili, il ruolo e la funzione `apply` che applica le modifiche al motore Python.

`Control` definisce minimo, massimo e l'eventuale vincolo intero. Ogni preset definisce tutti i controlli esposti dalla voce. Un controllo fuori intervallo è rifiutato; il nuovo stato viene confermato soltanto dopo il completamento di `apply`.

`Control.toggle` identifica uno switch con valori interi 0 e 1.
`ChoiceControl.choices` definisce coppie `[identificativo, etichetta]`;
il device mostra un menu e invia l'identificativo testuale. Gli indici
servono soltanto alla visualizzazione e non sono salvati nei preset.
Il menu sostituisce il valore numerico quando si sceglie un parametro
nominale, per esempio **Stile** sulle drums. Richiede il device ricostruito
con i sorgenti aggiornati.
`DeviceVoice.describe_controls(role, values)` può fornire etichette
(`label`) e motivi di inattività (`inactive_reason`) per le chiavi dei
controlli. Le regole sono definite dai generatori e ricalcolate a ogni
risposta di stato; il device mantiene chiavi e valori indipendenti dalle
etichette visualizzate.

`EnsembleSession.set_parameter(voice, name, value)` modifica un solo
override, conservando gli altri e i parametri guidati dalle sezioni.
`set_parameters(voice, values)` sostituisce l'insieme degli override,
come avviene selezionando un preset. La validazione precede ogni modifica.

`manual(voice, name)` legge la modalità del parametro.
`set_manual(voice, name, True, progress=...)` mantiene il suo valore
corrente; `False` elimina soltanto quel vincolo manuale.
`clear_parameters(voice)` elimina tutti gli override della voce.

Il ritorno ai valori di sezione avviene dalla prossima finestra da
pianificare, senza interpolazione. L'adattamento continuo al dialogo e il
rilascio graduale sono descritti nel
[contratto della direzione adattiva](proposte/DIREZIONE-ADATTIVA.md) e
restano da implementare. Ruolo, presenza, contesto armonico e memoria
compositiva continuano a funzionare in entrambe le modalità.

`DeviceVoice.for_session(session, voice, progress, **controls)` collega il dispositivo alla sessione: `progress` è una funzione del chiamante che restituisce la progressione corrente della tappa. Il collegamento espone i ruoli dichiarati dal generatore, legge il ruolo della sezione e applica la scelta manuale tramite `EnsembleSession.set_role`.

La scelta manuale del ruolo persiste tra sezioni nella stessa sessione Python; `Follow section` la elimina e ripristina il ruolo della sezione corrente. Non attiva voci escluse dall'organico, non modifica i parametri e non riscrive la configurazione JSON. Agisce sulle successive chiamate di pianificazione, senza sostituire le frasi già inviate. Ruoli non supportati vengono rifiutati prima dell'applicazione; il dispositivo torna a mostrare l'ultima scelta confermata da Python.

`server.bridge.destination(voice)` restituisce una funzione compatibile con le destinazioni di `EnsembleSession`: riceve beat iniziale e `Phrase` e invia un piano all'istanza collegata. Con `DeviceVoice.for_session` il ruolo viene letto dal Director a ogni risposta; nei collegamenti costruiti direttamente con `DeviceVoice` il chiamante ne gestisce lo stato. Il ciclo di pianificazione è gestito dal chiamante. Il server è bloccante: richieste di controllo e pianificazione vanno serializzate nello stesso thread, usando il callback `on_message` o governando esplicitamente il ciclo del server.

## Protocollo e arresto

I messaggi sono OSC con il JSON versione `1` codificato in UTF-8,
un argomento intero OSC per ciascun byte:

- dispositivo → Python: `/desnivel/v1/voice/control`;
- Python → dispositivo: `/desnivel/v1/voice/message`.

Il dispositivo usa `udpsend` e `udpreceive` nel formato ordinario dei
messaggi OSC. Gli script convertono gli argomenti numerici in JSON e
viceversa. Anche il passaggio dei piani dall'interfaccia al player usa byte
numerici. I payload JSON variabili non diventano simboli Max a ogni
aggiornamento del trasporto. Il server limita il JSON in uscita a 12.000
byte per mantenere il pacchetto OSC sotto il limite UDP.

Le richieste contengono voce, identificativo dell'istanza, seriale, porta di risposta e azione (`hello`, `transport`, `role`, `preset`, `parameter`, `manual`, `presence`, `save_preset`, `panic`). L’azione `role` contiene l’identificativo del ruolo manuale oppure `null` per seguire la sezione. Lo stato restituisce ruoli supportati, ruolo effettivo, ruolo della sezione, modalità (`section` o `manual`) e stato di attivazione della parte. La lettura del trasporto aggiunge beat, stato di riproduzione e contatore locale delle discontinuità. Le risposte distinguono stato, errore, piano e comando di trasporto.
`save_preset` contiene nome e flag `overwrite`; il salvataggio acquisisce
sul server i valori effettivi. Il device dichiara `transport_control` nelle
richieste; solo l'istanza scelta come sorgente del clock riceve le azioni
`pause`, `resume` e `restart`, applicate con `live.object` al `live_set`.
I comandi sono identificati da sessione Python e seriale, per scartare i duplicati.

L'azione `manual` contiene `parameter` e un `value` booleano. Lo stato di
ogni controllo contiene `manual`, oppure `null` senza sessione collegata.
Il flag non viene salvato nei preset: appartiene alla sessione Python.

L'azione `presence` contiene `value`, il moltiplicatore manuale da 0 a 10.
Lo stato della sessione include `presence` con `automatic`, `multiplier`
ed `effective`, anche per le voci fuori organico. Le risposte a `hello`
e agli aggiornamenti del trasporto mantengono aggiornati i valori del device.

Il dispositivo invia `hello` ogni secondo. Dopo oltre tre secondi senza conferma cancella i piani e spegne le note. Python rifiuta due istanze attive con la stessa voce o la stessa porta di ricezione; un collegamento scaduto può essere sostituito. I piani sono indirizzati anche all'identificativo dell'istanza.

Il player riutilizza gruppi di oggetti nativi per i timestamp degli eventi.
Ogni gruppo contiene `timepoint`, gate a singola esecuzione e memoria delle
coppie MIDI. Gli eventi allo stesso timestamp vengono emessi in ordine,
con note-off prima dei note-on. I gruppi scaduti vengono disarmati e
riutilizzati, mantenendo gli oggetti necessari ai note-off ancora futuri.
Il numero di gruppi cresce solo quando aumenta il picco di timestamp
contemporaneamente pianificati. Stop e Panic svuotano i piani e disarmano
i gruppi; la rimozione del dispositivo elimina anche gli oggetti conservati.
La ricompilazione del JavaScript rimuove gli oggetti dinamici residui.

Il player cancella i piani a Stop, arretramento del trasporto e Panic. Rifiuta piani tardivi e sovrapposizioni della stessa altezza all'interno della frase. Il passo temporale è un tick Max, pari a 1/480 di semiminima.

## Verifiche

I test Python verificano controlli, destinazioni separate, duplicati, conflitti tra istanze e collegamento con `EnsembleSession`. I test JavaScript simulano messaggi e player, compresi 1.000 aggiornamenti
del trasporto a byte e 1.000 finestre con numero di oggetti stabile dopo
il riscaldamento. Questi controlli non misurano il jitter audio in Live. I test del builder verificano contenitore e connessioni del sorgente.

La prova manuale in Live ha confermato l'invio della frase da file e la produzione di suono. La correzione di Connect ripetuto è verificata dal test JavaScript; la relativa prova manuale in Live resta da eseguire.

## Riferimenti tecnici

- [Cycling '74 — udpreceive](https://docs.cycling74.com/reference/udpreceive/): ricezione OSC e rinvio alla coda a bassa priorità.
- [Cycling '74 — timepoint](https://docs.cycling74.com/reference/timepoint/): esecuzione su trasporto e aggiornamento del timestamp.
- [Cycling '74 — udpsend](https://docs.cycling74.com/reference/udpsend/): trasmissione dei messaggi Max come pacchetti OSC compatibili.
- [Cycling '74 — textedit](https://docs.cycling74.com/reference/textedit/): ingresso dell'identificativo della parte.
- [Cycling '74 — pattr in Max for Live](https://docs.cycling74.com/userguide/pattr/): salvataggio dei campi Max nel Live Set tramite parametri espliciti.
- [Cycling '74 — Song](https://docs.cycling74.com/apiref/lom/song/): posizione e funzioni del trasporto del Live Set.
- [Cycling '74 — MIDI](https://docs.cycling74.com/userguide/midi/): formattazione e uscita dei messaggi MIDI.
- [Cycling '74 — Maxobj](https://docs.cycling74.com/apiref/js/maxobj/): proprietà `hidden` per cursore e switch e `setboxattr` per le annotazioni.
