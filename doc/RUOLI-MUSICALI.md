# Voci e contesto musicale

Il progetto rappresenta le voci attraverso generatori, ruoli supportati e dipendenze. Le assegnazioni delle sezioni indicano il ruolo richiesto e i parametri da passare al generatore.

## Voce e dipendenze

In [`music/coordinator.py`](../src/desnivel/music/coordinator.py), `Voice` contiene:

| Campo | Contenuto |
|---|---|
| `generate` | Funzione che riceve un `PlanningRequest` e restituisce una `Phrase` |
| `dependencies` | Tupla degli identificativi delle parti richieste dal generatore |
| `optional_dependencies` | Parti lette se attive nella sezione o fornite come sorgenti; se attive partecipano all’ordinamento delle dipendenze |
| `supported_roles` | Tupla dei ruoli dichiarati dal generatore |
| `stage`, `accept` | Preparazione di `VoicePlan` e applicazione dello stato già validato; richieste per il dialogo |
| `prepare_reference` | Preparazione facoltativa di un riferimento ritmico e del materiale privato del produttore |
| `rhythmic_roles` | Ruoli compatibili con le influenze ritmiche; tupla vuota senza supporto |

Gli identificativi sono le chiavi della mappa passata a `MusicCoordinator`. Il Coordinator li usa per risolvere le dipendenze e raccogliere i risultati.

`MusicCoordinator.plan` verifica che le sorgenti fornite non coincidano con le voci da generare e che coprano la durata richiesta. Verifica dipendenze mancanti o cicliche prima di chiamare i generatori. Le dipendenze facoltative inattive non vengono richieste; quelle attive
partecipano al controllo dei cicli. Quindi esegue i generatori nell’ordine
delle dipendenze e controlla la durata di ciascuna frase restituita. La
decisione registra le sole sorgenti effettivamente passate al generatore.

## Ingressi dei generatori

Ogni generatore riceve un `PlanningRequest` con questi campi:

| Campo | Contenuto |
|---|---|
| `start` | Beat iniziale della finestra, finito e non negativo |
| `length_beats` | Durata della finestra in beat, finita e positiva |
| `context` | `MusicalContext` fornito dal chiamante, oppure `None` |
| `dependencies` | Mappa delle frasi delle sole dipendenze dichiarate dalla voce |
| `role` | Ruolo assegnato alla voce, oppure `None` nelle chiamate senza assegnazioni |
| `parameters` | Mappa di sola lettura dei parametri assegnati alla voce |
| `logical_start`, `epoch` | Posizione dall'origine e identità della sequenza di pianificazione; posizione `None` senza dialogo |
| `rhythm` | Riferimento ritmico immutabile, oppure `None` |
| `relations` | Influenze storiche risolte per la voce e il ruolo correnti |
| `prepared_material` | Materiale privato consegnato soltanto alla voce produttrice della guida |
| `participating` | Ammissione della finestra secondo presenza e politiche di silenzio delle relazioni; non garantisce note o esecuzione audio |

Il Coordinator passa lo stesso intervallo e contesto a tutte le voci. La mappa delle dipendenze consegnata al generatore è di sola lettura. Il risultato di `plan` contiene le frasi delle voci registrate, identificate dalle rispettive chiavi.

Il [dialogo ritmico](DIALOGO-MUSICALE.md) documenta preparazione, accettazione,
memoria dei gesti, politiche di indisponibilità e reset. Le relazioni
storiche non aggiungono archi al grafo delle dipendenze correnti.

## Contesto di sezione

In [`music/director.py`](../src/desnivel/music/director.py), `MusicDirector.context_at` seleziona la sezione dalla progressione del viaggio e restituisce un `MusicalContext`:

| Campo | Contenuto |
|---|---|
| `section_index` | Indice della sezione nella configurazione |
| `name` | Nome della sezione |
| `root` | Altezza di riferimento intera |
| `scale` | Identificativo della scala presente in `SCALES` |

[`music/journey.py`](../src/desnivel/music/journey.py) usa il Director per selezionare il contesto e produrre cambi di pattern dai dati del viaggio. Il Coordinator riceve il contesto come argomento del chiamante; non seleziona le sezioni.

## Materiale musicale

In [`music/patterns.py`](../src/desnivel/music/patterns.py), `Pattern` contiene note e gate.

In [`music/phrases.py`](../src/desnivel/music/phrases.py), `Phrase` contiene una durata in beat e una tupla di `Note`. Ogni nota specifica attacco relativo, altezza MIDI, durata e velocity. Un beat corrisponde a una semiminima; tutte le note devono terminare entro la frase.

## Assegnazioni manuali e destinazioni

`MusicDirector.assignments_at(progress)` restituisce le assegnazioni della sezione corrente come mappa di `Assignment`: ogni assegnazione contiene `role` e `parameters`. Le sezioni non ereditano le assegnazioni precedenti.

Il Coordinator, quando riceve le assegnazioni, pianifica solo le voci elencate e verifica il supporto del ruolo prima di invocare i generatori. Passa ruolo e parametri senza interpretarli; le regole compositive sono responsabilità del generatore. Le chiamate senza assegnazioni mantengono la pianificazione di tutte le voci registrate.

[`music/session.py`](../src/desnivel/music/session.py) contiene `EnsembleSession`, che collega una configurazione manuale a generatori Python e funzioni di destinazione registrati dal chiamante. `from_file` legge la configurazione JSON. La configurazione contiene:

- `selection_mode`: `manual`.
- `voices`: mappa degli identificativi delle voci; ogni voce indica `generator`, `destination` ed eventuali `dependencies`.
- `sections`: sezioni con `name`, `from_progress`, `root`, `scale` e `assignments`. Ogni assegnazione indica `role` ed eventuali `parameters`.

La sessione mantiene per ogni voce il ruolo della sua prima assegnazione. Se una configurazione assegna ruoli diversi nelle sezioni successive, usa il primo ruolo e segnala voce, sezione e ruolo sostituito; il file originale non viene modificato. I parametri e le dipendenze delle sezioni sono verificati con il ruolo effettivo: parametri incompatibili producono un errore.

`plan(progress, start, length_beats)` produce le frasi senza inviarle; `send(start, phrases)` le consegna alle destinazioni associate. Ogni funzione di destinazione riceve beat iniziale e frase e gestisce il proprio adattamento e trasporto.

Il chiamante fornisce progressione della tappa e posizione musicale. Questa interfaccia Python non carica preset sonori negli strumenti e non crea controlli Max for Live.

## Scelta manuale del ruolo

`EnsembleSession.set_role(voice, role)` verifica il supporto del ruolo da parte del generatore e comunica la scelta al Director. Passando `None` si ripristina il ruolo configurato. `MusicDirector.assignments_at` applica le scelte manuali soltanto alle voci attive nella sezione; `section_assignments_at` espone le assegnazioni normalizzate.

`EnsembleSession.role_state(voice, progress)` restituisce ruoli supportati, modalità, ruolo configurato, ruolo effettivo e attivazione. Nella sessione Live la scelta è consentita prima del primo Play; dopo il Play resta bloccata anche in pausa, fino al riavvio a zero. La scelta non modifica la configurazione JSON. I parametri della parte restano separati dal ruolo.
