# Direzione adattiva delle voci

Stato: contesto locale, osservazione, risolutore, politiche delle quattro
voci e rilascio graduale implementati. Il compositore percussivo a regole
rimane da implementare; i coefficienti richiedono taratura all'ascolto.

Il [device attuale](../../../../VOCE-M4L.md) mostra auto/manual per parametro,
valore applicato e obiettivo. Le formule e i tempi effettivi sono in
[Direzione musicale](../../../../DIREZIONE-MUSICALE.md#adattamento-dei-parametri).

## Responsabilità

Il viaggio orienta la forma e il contesto musicale. Ogni voce adatta i
propri parametri al contesto e al materiale recente delle altre voci,
conservando regole compositive e memoria proprie.

Il Coordinator organizza le strategie attraverso interfacce generiche,
ordina le dipendenze e accetta insieme parametri, frasi e stati successivi.
Le regole specifiche e la selezione dei parametri adattabili appartengono
ai moduli delle voci. La traduzione delle misure del viaggio rimane
separata, secondo il [piano del contesto locale](../../media/in-corso/SEZIONI-GUIDATE-DAL-VIAGGIO.md).
Il device mostra lo stato e raccoglie le scelte manuali.

| Voce | Responsabilità della strategia |
|---|---|
| Drums | Produrre la guida ritmica; adattare sviluppo e complementi al contesto e alle proposte delle altre voci |
| Basso | Sostenere gli appoggi delle drums; regolare densità, sincopi e movimento rispetto allo spazio melodico |
| Melodia | Conservare continuità e riconoscibilità; adattare attività e dinamica al contesto e allo spazio disponibile |
| Tessitura | Fornire sostegno armonico nel registro scelto; adattare la dinamica lasciando spazio alla melodia |

Responsabilità e controlli automatici sono applicati dalle politiche dei
moduli delle voci. Griglia, durata dei periodi e ulteriori automatismi
rimangono distinti da questo primo insieme.

## Adattamento automatico

- Ogni strategia dichiara quali controlli esistenti adatta e con quali
  limiti. Non si automatizza indistintamente ogni parametro.
- Stile, seed e modalità della tessitura restano scelte esplicite
  dell'utente o della configurazione. L'adattamento non li cambia.
- Le strategie osservano lo stesso passato musicale accettato: attacchi,
  durate, silenzi, registri e accenti. Non analizzano l'audio né presumono
  che un piano inviato sia stato effettivamente suonato.
- Le osservazioni che determinano i parametri precedono la composizione
  della finestra. Non dipendono dall'ordine con cui le voci vengono generate.
- Le dipendenze della finestra corrente continuano a fornire materiale
  alla composizione. Le drums preparano la guida; le altre voci compongono;
  le drums adattano i complementi. Il risultato influenza le finestre
  successive. Gli appoggi già comunicati restano validi.
- I valori cambiano con continuità e persistenza; i cambi strutturali
  rispettano i confini musicali. La reazione delle voci non deve produrre
  oscillazioni continue dei controlli né riavviare le frasi.
- Una preparazione fallita non avanza parametri o memoria. Ripetere una
  richiesta accettata non provoca un nuovo adattamento.

L'assetto di sezione fornisce la base. Le politiche propongono obiettivi
per i soli controlli dichiarati; il valore manuale ha precedenza. I numeri
negli assetti non costituiscono blocchi dell'automazione. Lo stato espone
base, obiettivo, valore applicato, sorgente e motivo.

## Controllo manuale per parametro

Ogni parametro esposto dalla voce ha un flag booleano `manual`,
inizialmente `false`. Nel device lo switch **manual** e l'indicatore
**auto/manual** si riferiscono al parametro selezionato nel menu.

| Evento | Effetto |
|---|---|
| `manual = false` | Il parametro segue la configurazione e, se previsto, la strategia adattiva |
| Modifica utente di un parametro | Dopo la validazione, applica il valore e porta soltanto il suo flag a `true` |
| Attivazione esplicita di `manual` | Mantiene il valore effettivo corrente del parametro selezionato |
| Altre modifiche con `manual = true` | Aggiorna il valore manuale del parametro |
| `manual = false` dopo un intervento | Rilascia soltanto quel parametro e riprende l'automazione dal contesto corrente |
| Aggiornamento proveniente dal motore | Aggiorna la visualizzazione senza attivare `manual` |

Gli altri parametri continuano a seguire la propria modalità. Una
velocity manuale non blocca attività, sviluppo o adesione ritmica.
La scelta di un preset rende manuali i valori che applica; ciascuno può
essere restituito separatamente all'automazione. La sincronizzazione del
device e il salvataggio di un preset non cambiano le modalità. Un valore
rifiutato dalla validazione non cambia né valore né flag.

Per i controlli gestiti dalle politiche, il ritorno in automatico parte
dal valore manuale accettato e converge verso l'obiettivo corrente.
Gli altri controlli tornano alla configurazione. Stile, seed e modalità
della tessitura non ricevono adattamento continuo.

La voce continua a generare, seguire il contesto armonico e usare le
relazioni musicali anche con parametri manuali. I flag non congelano le
note, non escludono la voce dall'organico e non fermano il viaggio.
Ruolo e presenza conservano i propri controlli e le proprie precedenze.

Le modifiche si applicano dalla prima finestra ancora da pianificare,
rispettando i confini previsti dal controllo. Non riscrivono piani già
accettati. I flag sono indipendenti per parametro e per voce e rimangono
invariati al cambio di sezione e al riavvolgimento.

## Stato e verifiche

Per ogni voce, rendere ispezionabili modalità, valori effettivi, obiettivi
automatici e motivo dell'adattamento, con intervallo musicale e sorgenti
usate. Il device mostra il flag e i valori effettivi; i dettagli delle
decisioni appartengono allo stato della sessione.

Verificare prima dell'integrazione:

- adattamento riproducibile con gli stessi ingressi, seed e memoria;
- reazioni in entrambe le direzioni senza cicli nella stessa finestra;
- attivazione manuale atomica del solo parametro modificato;
- indipendenza fra parametri e fra voci;
- rilascio graduale verso il contesto corrente, senza reset della frase;
- aggiornamenti automatici incapaci di attivare il flag;
- conservazione degli altri valori manuali e dei controlli di ruolo e presenza;
- nessun avanzamento dopo un errore o una richiesta ripetuta.

Per le drums, l'adattamento accompagna il
[compositore a regole](../../../musica/media/in-corso/STILI-PERCUSSIVI.md). Il solo aggiornamento dei
parametri del motore attuale continua a trasformare materiale precomposto.
Le risposte che richiedono materiale passato durante il silenzio della
sorgente richiedono anche il relativo supporto compositivo e di memoria.

## Piano di implementazione proposto

Stato: fasi 1–3 implementate. Il compositore a regole della fase 4 rimane
da realizzare. La fase 5 comprende verifiche automatiche disponibili e
confronto d'ascolto ancora da completare.

### 1. Contesto locale e osservazione musicale

Implementazione disponibile: [contesto delle finestre](../../../../DIREZIONE-MUSICALE.md#contesto-locale-delle-finestre)
e [osservazione condivisa](../../../../DIALOGO-MUSICALE.md#osservazione-musicale-condivisa).
I valori sono ispezionabili nello stato e alimentano le politiche adattive.

- Riutilizzare le finestre di pendenza smussata di `trip/analysis.py`,
  conservandone unità, scala spaziale, copertura e interruzioni.
  Primo ingresso: pendenza locale, suo cambiamento e persistenza.
  Velocità e regolarità del movimento richiedono le verifiche di
  provenienza previste nel piano del contesto locale e restano successive.
- Associare ogni finestra futura da comporre al suo intervallo sorgente.
  In modalità allocata, ripartire uniformemente la distanza all'interno
  dello span della macrosezione. In modalità lineare, usare l'intervallo
  temporale sorgente rappresentato dal piano, dichiarando il rapporto
  fra beat, BPM e velocità di replay. Le soste escluse non rientrano nella
  corrispondenza. Report e runtime devono usare la stessa funzione.
- Osservare inizialmente gli ultimi 16 beat accettati precedenti al piano:
  attacchi per beat, quota temporale con almeno una nota e registro per
  voce. Registrare anche quanta storia è disponibile. Una nota lunga
  occupa tempo senza equivalere a molti attacchi; sovrapposizioni non
  contano due volte nell'occupazione.
- La storia osservabile include le porzioni accettate dei gesti ancora
  incompleti. Riutilizzare gli eventi già registrati dalla pianificazione;
  i gesti completi conservano la responsabilità di fornire materiale alle
  relazioni. Nessuna seconda analisi audio o nuova dipendenza simultanea.
- All'avvio non attribuire silenzio a una storia assente. Misure mancanti
  o non valide restano riconoscibili; la politica applicata è dichiarata
  nello stato, senza sostituirle implicitamente con zero.

Consegna: report per finestra con tratto sorgente, misure locali e
osservazioni musicali, prima di attivare modifiche ai controlli.

### 2. Risoluzione dei valori e continuità

La sessione fornisce assetto, override e modalità per parametro. Il
Coordinator invoca le politiche registrate dalle voci sullo stesso
contesto e passato accettato, prima di preparare la guida ritmica.
Ogni politica restituisce obiettivi, motivazioni e stato successivo.
Una risoluzione comune applica limiti, tempi di transizione e override.
La preparazione rimane distinta dall'accettazione.

Precedenza implementata: impostazioni iniziali e assetto di
sezione come base, adattamento automatico, valore manuale del singolo
parametro. I numeri già presenti negli assetti non diventano blocchi
dell'automazione. Questa scelta precisa la precedente distinzione aperta
fra valori iniziali e vincoli: non richiede un secondo sistema di blocchi
nei JSON. Le regole riutilizzano `direzione-viaggio.json`; le formule
specifiche rimangono nei moduli delle voci.

Tempi iniziali implementati: transizioni di 8 beat per la dinamica e 16 beat
per attività e densità. Il calcolo dipende dai beat trascorsi, non dal
numero di messaggi OSC. Le decisioni discrete rispettano la frase o il
ciclo del generatore. Limiti, soglie di persistenza e intervalli automatici
dei singoli controlli sono dichiarati nelle politiche e da tarare all’ascolto.
Per limitare gli inseguimenti reciproci, rivalutare l’obiettivo di attività
melodica al confine del suo periodo; il basso può rivalutare il sostegno
ogni battuta. La Variazione delle drums rispetta il confine del proprio
ciclo. Questa differenza di cadenza va verificata insieme ai pesi delle
reazioni, non sostituisce il controllo delle oscillazioni.

Rilasciare un parametro manuale avvia la transizione dal valore mantenuto
verso l'obiettivo corrente. Gli altri override restano validi. Richieste
ripetute e tentativi falliti non avanzano interpolazione, memoria o seed.
La cache deve riconoscere la stessa richiesta prima di ricalcolare
l'adattamento dal nuovo stato; i piani già accettati restano immutati.

### 3. Primo insieme di politiche musicali

| Voce | Controlli iniziali | Regola implementata |
|---|---|---|
| Melodia | `activity`, `velocity` | Il terreno orienta la dinamica; un accompagnamento già fitto riduce l'attività rispetto alla base, lasciando intatta la continuità del motivo |
| Basso | `density`, `syncopation` | Una melodia ricca di attacchi favorisce pochi sostegni; pause persistenti consentono più movimento, conservando il rapporto con la guida |
| Tessitura | `velocity` | La base dinamica segue il contesto; la presenza melodica nel suo registro richiede alleggerimento, mentre lo spazio persistente permette di tornare alla base |
| Drums | `velocity_ratio`, `variation` | Il terreno orienta la dinamica; cambiamenti persistenti e spazio nelle altre parti orientano lo sviluppo, rispettando lo stile e gli appoggi |

Le regole della tabella sono scelte compositive implementate nelle politiche. Non tutte le voci aumentano insieme
la propria attività per una salita più ripida. Il dialogo già presente
continua a operare nella composizione delle note.

Il basso usa la capacità ritmica recente per limitare l’obiettivo di densità: un valore automatico che cambia senza
cambiare le possibilità musicali non costituisce una risposta utile.
Per la tessitura la velocity indica una dinamica MIDI, non una misura
del volume audio o una garanzia di separazione timbrica.

`step_beats`, durata delle frasi, registri, stile, seed e `follow_source`
rimangono configurati o manuali in questo primo insieme. Cambiare griglia
o durata della frase richiede un contratto di continuità specifico.
Ulteriori automatismi su sviluppo e adesione ritmica vanno introdotti
soltanto dopo aver verificato quelli iniziali, evitando che due controlli
compensino lo stesso fenomeno.

### 4. Composizione percussiva a regole

Realizzare il compositore previsto dal contratto delle percussioni usando
gli stessi ingressi e lo stesso risolutore dei parametri. La dinamica può
essere collegata al motore esistente; l'automazione di Variazione su quel
motore mantiene il limite delle trasformazioni di materiale precomposto.
Il completamento richiede figure costruite secondo le regole dello stile.

La mappatura operativa distingue intensità locale per la dinamica e
cambiamenti persistenti e spazio musicale per lo sviluppo. Il compositore
a regole dovrà riutilizzare gli stessi obiettivi risolti. Preparazione della
guida, complementi e transizioni stilistiche non modificano retroattivamente
gli appoggi già comunicati.

### 5. Stato visibile e verifica musicale

- Mostrare per parametro base, obiettivo automatico, valore applicato,
  modalità e motivo. Il device conserva campo numerico, slider e switch;
  i dettagli appartengono allo stato della sessione.
- Associare i valori al relativo piano e intervallo: la pianificazione
  anticipata non deve presentare un obiettivo futuro come valore già
  applicato nell'intervallo in ascolto. L'aggiornamento grafico non invia
  modifiche manuali al motore.
- Confrontare stesso percorso, seed, BPM e suoni con adattamento attivo e
  disattivo, includendo salite variabili, discese, pianura e interruzioni.
- Verificare silenzio, storia iniziale incompleta, tutti i parametri in
  manuale e modalità miste. Un aumento del basso non deve innescare un
  continuo alternarsi di densità con la melodia.
- Verificare note effettive, continuità delle frasi, cache, reset e mancato
  avanzamento dopo errori. Valutare separatamente suono e numeri dei controlli.

Ordine operativo: contesto e osservazione → risolutore con manuale e
stato → politiche delle voci → completamento delle drums → ascolto e
taratura complessiva. Ogni fase comprende le proprie verifiche prima di
passare alla successiva.
