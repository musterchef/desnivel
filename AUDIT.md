# Audit tecnico e musicale di Desnivel

Audit basato sul codice e sulla working tree esaminata; include le modifiche locali già presenti, senza attribuirle al commit corrente. Non sono state modificate altre parti del repository.

## A. Stato attuale

### Architettura e flusso

1. [load_track](src/desnivel/trip/loader/track_loader.py#L18) carica GPX o FIT, filtra anomalie e interruzioni, separa i tratti osservati e deriva i canali. [analyze_track](src/desnivel/trip/analysis.py#L73) calcola il profilo e le zone; [group_zones](src/desnivel/trip/sections.py#L38) accorpa le zone contigue nelle macrosezioni configurate.
2. [prepare_trip_config](src/desnivel/cli/trip_direction.py#L125) risolve direzione e arrangiamento. L'opzione automatica ricava un motivo dalla forma altimetrica normalizzata, sceglie una tavolozza secondo la pendenza assoluta media e seleziona contesti per sezione in base all'intensità locale. La configurazione può invece fissare direttamente radici, scale e assegnazioni.
3. [EnsembleRuntime](src/desnivel/cli/ensemble_runtime.py#L19) pianifica finestre beat-quantizzate. La modalità allocated distribuisce il budget musicale sulle distanze delle macrosezioni tramite [allocate_timeline](src/desnivel/music/timeline.py#L108); la modalità linear proietta il replay usando tempo, BPM e velocità in [WindowContext.linear](src/desnivel/cli/window_context.py#L55). Il BPM serve al collegamento col trasporto/replay, non è imposto dai generatori.
4. [MusicDirector](src/desnivel/music/director.py#L20) seleziona contesto e assegnazioni per sezione; [EnsembleSession](src/desnivel/music/session.py#L34) collega generatori e destinazioni. [Phrase](src/desnivel/music/phrases.py#L24) è l'output in beat, indipendente dal player.
5. [MusicCoordinator.plan](src/desnivel/music/coordinator.py#L114) verifica le dipendenze, ordina le voci, prepara i piani e accetta gli stati solo dopo la generazione. Le dipendenze della finestra corrente formano un DAG; le dipendenze facoltative attendono le voci attive.

### Generazione e coordinamento

- Esiste già un contratto compositivo comune, [Generator](src/desnivel/music/session.py#L20), basato su funzioni e capacità opzionali, non su una gerarchia di classi. [Voice](src/desnivel/music/coordinator.py#L41) associa tali capacità a dipendenze e ruoli; `EnsembleSession` le trasferisce al coordinatore. È una base semplice da estendere; l'ereditarietà non è giustificata.
- Le voci concrete hanno responsabilità distinte: [MotifGenerator.stage](src/desnivel/music/melodic/generator.py#L59) sviluppa la melodia, delega il ruolo `harmony` a `TextureGenerator` e mantiene `bass_line` come motivo letterale; [BassVoice.stage](src/desnivel/music/bass/voice.py#L42) ricava un accompagnamento da una frase sorgente; [TextureGenerator.stage](src/desnivel/music/texture/generator.py#L122) realizza sostegno o accordi; percussioni esplicite e sviluppate hanno generatori separati.
- L'interazione generale oggi consiste in dipendenze e osservazioni condivise; le relazioni dichiarative sono invece limitate alla storia ritmica (`scope=history`, `aspects=['rhythm']`) in [RhythmRelation](src/desnivel/music/interactions.py#L35). Il produttore ritmico prepara un riferimento prima delle voci; le relazioni leggono solo gesti completi di finestre accettate. Le influenze sono direzionali, ma si possono configurare in entrambe le direzioni senza leggere la finestra in corso. Questo preserva causalità e riproducibilità.
- La generazione è beat-agnostica rispetto al BPM, non priva di griglie o figure: passo melodico e griglia del basso sono parametri in beat; i pattern e gli stili percussivi hanno cicli espliciti. Sono scelte locali ai generatori, non un ritmo imposto all'intero ensemble.

### Valutazione sintetica

- **Solido:** confini chiari tra dati del viaggio, direzione, frasi, generazione, coordinamento e destinazioni; validazione degli input; timeline condivisa; fasi `stage`/`accept`; seed locali e test di riproducibilità. Le prove coprono anche retry, reset, cicli nelle dipendenze e assenza di letture della storia nella stessa finestra.
- **Musica:** scale e radici governano le altezze; la tessitura costruisce triadi per gradi di scala; basso e percussioni considerano densità, accenti e materiale delle altre voci. Lo sviluppo melodico mantiene cellule e variazioni, ma il codice non può dimostrare che registri, cadenze, densità e combinazioni siano convincenti all'ascolto.
- **Limite dimostrato del dialogo:** esistono adattamento da osservazioni, riferimento ritmico e relazioni storiche, non un protocollo generale per scambiare segnali musicali arbitrari o negoziare influenze simultanee. Non è un difetto dell'implementazione attuale.
- **Ruoli del generatore melodico:** `melody`, `harmony` e `bass_line` hanno comportamenti differenti. Il riuso è esplicito, non prova da solo un errore architetturale; conservarlo finché non produce frizione concreta.

## B. Criticità

| ID | Priorità | Componente | Problema ed evidenza | Impatto |
|---|---|---|---|---|
| C1 | P1 | Regressione dell'ensemble / test melodici | **Verificato nella working tree:** `pytest` termina con 944 passati e 8 falliti. Tutti gli 8 casi di [test_whole_ensemble_dialogue_for_current_arrangement](tests/music/percussion/test_catalog.py#L106) hanno digest diversi dagli attesi in `SESSIONS_EXPECTED`; i test di identità del solo generatore percussivo passano. [development.py](src/desnivel/music/melodic/development.py#L83) è modificato localmente e la nuova generazione cambia le frasi, quindi l'intenzionalità della differenza non si deduce dal test. | Suite rossa e nessuna distinzione automatica tra variazione melodica deliberata e regressione dell'ensemble. Non dimostra da sola un peggioramento musicale. |
| C2 | P2 | Interpretazione GPX → musica | **Rischio da validare, non difetto dimostrato:** la direzione automatica usa soglie e normalizzazioni fisse per pendenza, cambiamento e persistenza in [adaptive_context](src/desnivel/cli/trip_direction.py#L14), e una scala di intensità locale per scegliere i contesti in [_resolve](src/desnivel/cli/trip_direction.py#L37). I test verificano ripetibilità e confini/configurazione, non l'effetto percettivo su ascoltatori. | Relazioni deterministiche e ispezionabili, ma non è provato che le differenze tra percorsi producano contrasti musicali proporzionati o non meccanici. La sola lettura del codice non consente un giudizio artistico. |

Non emergono difetti tecnici dimostrati nella ripartizione della timeline o nella causalità delle relazioni attuali; non si assegnano criticità a queste aree.

## C. Piano di intervento

| Task | Priorità / criticità | Obiettivo, componenti e modifiche | Dipendenze e rischi | Verifica di completamento |
|---|---|---|---|---|
| T1 — qualificare la nuova uscita dell'ensemble | P1 / C1 | Esaminare le differenze introdotte dalla generazione melodica corrente in [development.py](src/desnivel/music/melodic/development.py#L83), confrontando frasi e decisioni per i due arrangiamenti e i quattro stili percussivi del test. Se il cambiamento è voluto, aggiornare i digest solo dopo aver approvato l'uscita; affiancare asserzioni semantiche mirate ai digest, senza sostituire i test di identità percussiva. | Nessuna dipendenza tecnica. Il rischio è accettare digest nuovi senza verificare la variazione musicale; richiede una decisione d'ascolto, non un algoritmo di scoring artistico. | Gli 8 casi ensemble esprimono l'uscita approvata; rimangono verificabili invarianti melodiche e percussive; la suite completa termina senza fallimenti. |
| T2 — validare la mappatura dei percorsi | P2 / C2 | Usare percorsi riproducibili già disponibili e le decisioni serializzate da [_resolve](src/desnivel/cli/trip_direction.py#L37): verificare come forma, pendenza e intensità locale cambiano motivo, tavolozza, contesto e parametri. Ascoltare le frasi risultanti prima di modificare soglie o coefficienti; intervenire solo su una relazione che risulti poco leggibile o musicalmente sproporzionata. | Indipendente da T1. Il giudizio d'ascolto dipende da configurazione, destinazioni e contesto esecutivo; non introdurre metriche numeriche di qualità artistica. | Le decisioni sono riproducibili e tracciabili fino ai dati di percorso; una revisione d'ascolto documenta se i contrasti hanno l'effetto atteso. In assenza di evidenza contraria, non cambiare la mappatura. |

## D. Evoluzioni progettuali

Queste sono capacità future, non correzioni necessarie per rendere corretto il comportamento attuale.

### Contratto comune dei generatori

- **Valore:** rendere uniforme la composizione di nuove famiglie di generatori senza accoppiarle ai device.
- **Soluzione:** continuare con composizione e capacità esplicite di [Generator](src/desnivel/music/session.py#L20), non introdurre una classe base né uniformare artificialmente tutte le voci. Mantenere in `Voice` le dipendenze specifiche dell'istanza. Se il passaggio campo-per-campo tra `Generator` e `Voice` diventa fonte concreta di divergenze, ridurre quella duplicazione mantenendo separati contratto del generatore e binding della sessione.
- **Validazione:** aggiungere una voce di prova senza modifiche al coordinatore o agli adattatori; verificare ruoli, validazione, determinismo, staging e compatibilità con dipendenze opzionali.

### Interazioni estendibili tra generatori

- **Valore:** permettere in futuro dialogo non solo ritmico, ma anche su materiale, registro, densità o altri aspetti musicali, mantenendo autonomia delle voci.
- **Soluzione:** non generalizzare ora `RhythmRelation` senza un secondo caso d'uso concreto. Quando serve, introdurre un contesto immutabile di segnali dichiarati e una regola di lettura/trasformazione specifica della voce; tenere il meccanismo di scambio distinto dalle regole melodiche o armoniche. Riutilizzare i confini esistenti: dipendenze della finestra corrente ordinate in DAG; osservazioni e gesti storici solo da piani accettati; decisioni preparate prima dell'accettazione. Influenze bidirezionali simultanee vanno modellate come scambio causale tra finestre o fasi esplicite, non come mutua lettura e riscrittura dello stesso piano. Rendere espliciti ambito temporale e granularità quando un caso reale li richiede.
- **Rischi da prevenire:** dipendenze cicliche intra-finestra, ricalcoli non deterministici, crescita incontrollata dei feedback e confusione fra dati osservati e materiale pianificato. Non introdurre iterazioni convergenti o gerarchie di priorità senza un'esigenza dimostrata.
- **Validazione:** testare ordine e causalità, retry identici, reset, seed, influenza assente e influenze reciproche ritardate; ascoltare una sessione riproducibile per verificare che il dialogo produca risposta senza cancellare l'identità delle voci.

### Evoluzione musicale

Non è implementata una forma globale o un arco di tensione/risoluzione indipendente dalle sezioni configurate. Lo sviluppo melodico locale, la memoria delle osservazioni e le trasformazioni percussive danno continuità, ma non costituiscono un modello di forma comune. Aggiungerlo solo se un arrangiamento reale richiede transizioni o memoria più lunghe di quelle attuali; validare con gli stessi percorsi e ascolti comparativi, senza imporre una forma fissa a tutti i generatori.

## E. Componenti da mantenere

- La separazione fra loader/metriche del viaggio, direzione musicale, frasi, generatori, coordinatore, adattatori e trasporto.
- `Phrase` come unità beat-agnostica rispetto al tempo reale e la timeline allocata per distanza, con estensione/minimi dichiarati e confini di sezione verificabili.
- Pianificazione `stage`/`accept`, dipendenze DAG, osservazione delle sole finestre concluse e relazioni ritmiche storiche: sono meccanismi causali e testati.
- Seed locali, controlli con validazione, ruolo esplicito di configurazioni e preset, e distinzione tra pattern percussivi deliberati e pulsazione generale del sistema.
- I tre ruoli ammessi da `MotifGenerator`: l'armonia delega alla tessitura, mentre basso e melodia hanno percorsi distinti. Non eliminare ruoli né cambiare organici per risolvere la sola osservazione di responsabilità condivisa.
- Le relazioni GPX configurabili e ispezionabili. Finché T2 non mostra un problema d'ascolto, conservare soglie e coefficienti esistenti.
