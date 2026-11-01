# Contratti per le relazioni musicali

Stato: specifica generale con implementazione parziale. Il primo blocco
operativo comprende riferimento ritmico, gesti completi, memoria limitata,
relazioni storiche sul ritmo e preparazione separata dall'accettazione.
Campi e comportamenti effettivi sono documentati in
[Dialogo ritmico](../DIALOGO-MUSICALE.md). Trasformazioni generali,
collocazioni, vincoli obbligatori e altri aspetti musicali restano proposti.
Consolida il
coordinamento ritmico e il dialogo fra voci. La direzione musicale
confermata assegna alle drums il riferimento ritmico; la guida melodica
e gli scambi possono passare fra le voci.

## 1. Confini del sistema

I generatori conservano materiale, registro, articolazione, stato e regole
compositive propri. Il Coordinator ordina le dipendenze, consegna dati
musicali e verifica i risultati. Non compone note e non interpreta generi,
strumenti, dispositivi o misure geografiche.

Le relazioni combinano sorgente, collocazione temporale, materiale,
trasformazione e influenza. Call & Response, Imitation, Interlocking,
Unison, Layering e Counterpoint descrivono configurazioni musicali;
non diventano classi o modalità esclusive del Coordinator.

Il contratto ammette dipendenze ordinate nella stessa finestra e influenze
reciproche fra intervalli successivi. Non prevede un risolutore iterativo
di vincoli reciproci simultanei: tali configurazioni vengono rifiutate.

### Riscontro nel codice attuale

| Contratto presente | Limite da colmare |
|---|---|
| `PlanningRequest`: include riferimento ritmico e relazioni storiche risolte | Supporta soltanto l'aspetto ritmico e un frammento finale all'inizio della finestra |
| `Voice.stage/accept`, `VoicePlan` con gesti e stato successivo | I generatori devono rispettare la separazione fra preparazione e accettazione |
| `GestureSpan` e raccolta delle parti su più finestre | Mancano contesto d'origine, provenienza dettagliata e trasformazioni generali |
| Coordinator con storia limitata e selezione dell'ultimo gesto completo | Non gestisce collocazioni future o prenotazioni di turni |
| Runtime con reset della memoria e dei generatori | La storia riguarda i piani accettati, non l'audio eseguito |
| Contesto di sezione: indice, nome, root e scala | Non comprende accordi, relazioni o descrittori GPX locali |

## 2. Tempo e identità

Ogni intervallo musicale usa beat di semiminima, con inizio incluso e
fine esclusa. I beat devono essere finiti, con durata positiva. Le durate
e i ritardi non si esprimono in numero di chiamate o finestre.

| Campo proposto | Significato |
|---|---|
| `epoch` | Identifica una sequenza continua di pianificazione |
| `start`, `length_beats` | Intervallo sul trasporto, come nell'interfaccia esistente |
| `logical_start` | Posizione musicale rispetto all'origine dell'epoch |
| `plan_id` | Identità del piano accettato, indipendente dal seriale OSC |

Il runtime mantiene la corrispondenza fra beat logici e trasporto. Le
voci non la ricostruiscono dai tempi di esecuzione Python. Due richieste
dello stesso intervallo e stato devono produrre lo stesso risultato.
La finestra è un'unità di consegna, non una battuta né un gesto musicale.

## 3. Contesto condiviso e riferimento ritmico

Il contesto armonico conserva root e scala della sezione. Non vi si
aggiungono accordi presunti o interpretazioni implicite dei dati GPX.

Il produttore ritmico è indicato nella configurazione. Nella composizione
prevista è il modulo percussivo. Espone una preparazione indipendente
dalle frasi definitive delle altre voci.

| Campo di `RhythmReference` proposto | Vincolo |
|---|---|
| Intervallo ed epoch | Coincidono con la richiesta |
| Ciclo e fase | Lunghezza positiva; fase compresa nel ciclo |
| Posizioni di suddivisione | Ordinate, distinte e relative alla finestra; includono il timing del groove |
| Appoggi e pesi | Posizioni relative valide; pesi da 0 a 1 |

Il riferimento è immutabile. Non contiene altezze MIDI, nomi di pad o
generi; queste informazioni restano nel produttore. Lo stesso riferimento
viene consegnato a tutte le voci che lo utilizzano.

Preparazione ritmica e completamento delle drums usano lo stesso
materiale, seed e fase. Preparare non promuove lo stato del generatore.
Una pausa della parte drums non cancella il riferimento. Un produttore
inesistente è invece un errore se una relazione attiva lo richiede.

## 4. Gesto musicale e memoria

Un gesto è un'unità dichiarata dal generatore, con estensione temporale e
materiale riconoscibile. Può attraversare più finestre. La sua fine non
viene dedotta dall'ultimo messaggio o dalla fine della finestra.

| Campo di `Gesture` proposto | Contenuto |
|---|---|
| `id`, `voice`, `epoch` | Identità stabile e provenienza |
| `start`, `end` | Estremi in beat logici; fine nota e finita |
| Materiale | Note effettive con attacchi relativi al gesto |
| Contesto d'origine | Riferimento al contesto armonico in cui è stato composto |
| Completamento | Distingue gesto ancora in costruzione da gesto interamente determinato |
| Provenienza del piano | Piani che ne determinano il materiale |

La memoria conserva i risultati dopo presenza e validazione, non soltanto
le intenzioni originali dei generatori. Un gesto interamente silenziato
non costituisce una chiamata sonora. La storia descrive piani musicali
del motore; non certifica la produzione audio del dispositivo.

Le query dichiarano voce, intervallo o selettore e profondità massima in
beat. Il selettore iniziale `last_complete_gesture` cerca l'ultimo gesto
completo non vuoto entro quel limite. Non cerca indefinitamente nel passato.

Un gesto può essere completo nel piano prima di aver finito di suonare:
la pianificazione anticipata rimane consentita. Per una relazione storica,
la fine del materiale letto non deve superare l'inizio musicale della
risposta. Non è consentito leggere materiale futuro rispetto alla risposta.

Le dimensioni massime dei gesti e le profondità delle query sono dichiarate
e validate; la sessione deve poter conservare l'intero materiale richiesto.
I gesti ancora referenziati da risposte pendenti rimangono disponibili.
Un limite insufficiente produce un errore, non un taglio silenzioso.

## 5. Relazioni dichiarate e relazioni risolte

`RelationSpec` è la configurazione persistente. Una relazione risolta
seleziona materiale e intervallo concreti e rimane stabile per la durata
dell'intervento, anche quando questo attraversa più finestre.

| Campo di `RelationSpec` proposto | Significato |
|---|---|
| `id`, `target` | Identità della relazione e voce destinataria |
| `source` | Voce o riferimento ritmico esplicito |
| `scope` | `current` per la finestra corrente; `history` per materiale precedente |
| `selection` | Materiale selezionato; per la storia include selettore e limite temporale |
| `placement` | Collocazione: simultanea, dopo la sorgente o negli intervalli dichiarati; ritardo in beat |
| `aspects` | Aspetti utilizzati: ritmo, altezze, dinamica o registro |
| `transforms` | Sequenza ordinata di trasformazioni con unità esplicite |
| `strength` | Mappa aspetto → influenza da 0 a 1 |
| `requirement` | `preference` per una preferenza compositiva; `exact` per un obbligo esatto |
| `on_unavailable` | `independent`, `silence` oppure `error` |
| `boundary` | `continue_if_active` oppure `cancel_at_section` |

Le trasformazioni iniziali sono selezione di un frammento, trasposizione
e riscalamento temporale. Una trasposizione dichiara semitoni oppure gradi
di scala; la proiezione nella scala di destinazione è un'operazione
esplicita. Operazioni non implementate o non supportate vengono rifiutate.
L'inversione del profilo e altre trasformazioni possono aggiungersi con
un contratto proprio, senza nuove categorie del Coordinator.

La relazione risolta contiene identificativo della sorgente selezionata,
intervallo di destinazione, trasformazioni e motivazione dell'attivazione.
Non seleziona un nuovo gesto a ogni finestra. Se il materiale supera lo
spazio assegnato, deve esistere una trasformazione o una selezione esplicita;
il motore non lo tronca per farlo entrare.
Un gesto avvia al massimo un intervento per relazione. Una nuova ripresa
richiede una nuova attivazione esplicita, non la sola ripetizione della query.

### Preferenze e obblighi

Una preferenza orienta le scelte del generatore. Per ogni aspetto, i
contributi autonomi e relazionali sono valutati su punteggi da 0 a 1.
Con somma delle influenze `S ≤ 1`, il peso autonomo è `1 − S`; con `S > 1`
le influenze vengono normalizzate dividendo per `S` e il contributo
autonomo è zero. Aspetti diversi vengono trattati separatamente.
Forza zero non produce dipendenze o modifiche al materiale.

Un obbligo prescrive un risultato verificabile, per esempio stessi
attacchi e altezze nell'unisono. Non equivale a una preferenza con forza 1.
Un obbligo attivo ha forza 1; zero lo disattiva. Vincoli incompatibili
producono un errore riferito alle relazioni e alle voci coinvolte.
Nessuna forza autorizza violazioni di registro, durata o limiti del player.

I generatori dichiarano gli aspetti e le trasformazioni supportati. La
validazione avviene prima di modificare stato o inviare piani. Il Coordinator
non converte automaticamente altezze in dinamica o strumenti percussivi
in voci intonate.

## 6. Spazio temporale e causalità

Il piano delle interazioni assegna intervalli di intervento prima della
generazione coinvolta. Distingue preferenza di primo piano, intervalli
ammessi e obblighi di silenzio; soltanto questi ultimi impongono una pausa.
La presenza di una voce resta una decisione distinta.

Una risposta non deve limitarsi a trovare un buco occasionale. Il piano
può riservarle spazio e chiedere al chiamante di cedere il primo piano
o di tacere nell'intervallo dichiarato. Senza un confine del gesto
disponibile, `after_end` rimane pendente e non ne inventa la fine.

- Una sorgente `current` determina un arco sorgente → destinatario nel
  grafo della finestra. Tutti gli archi attivi devono essere aciclici.
- Una sorgente `history` è letta da uno snapshot immutabile all'inizio
  della pianificazione. Non crea un arco reciproco nella finestra corrente.
- Il riferimento ritmico già preparato non crea una dipendenza dalla
  frase finale del suo produttore.
- Le dipendenze tecniche già dichiarate dalle voci continuano a essere
  verificate; le nuove relazioni non le cancellano.
- Il ruolo di chiamante può passare fra voci in intervalli successivi.
  Il riferimento delle drums continua a governare il terreno ritmico.

L'ordine delle voci deriva dal grafo effettivo, non da una sequenza fissa
melodia → basso → tessitura. Il completamento delle drums può leggere le
altre frasi, purché queste dipendano dal riferimento preparato e non dalla
frase finale delle drums. Non ci sono iterazioni fino alla convergenza.

## 7. Richiesta, risultato e accettazione

Si conserva `PlanningRequest`, estendendolo con posizione logica,
riferimento ritmico opzionale, relazioni risolte e riferimenti storici
selezionati. Tutti gli ingressi sono di sola lettura. Una voce riceve
soltanto le sorgenti dichiarate, non accesso libero all'intera sessione.

Il nuovo risultato di generazione comprende `Phrase`, contributi ai gesti,
decisioni e stato successivo della voce. Lo stato rimane di proprietà del
generatore; il coordinamento non ne interpreta i campi. Il contesto e lo
stato iniziale bastano a riprodurre la richiesta, senza casualità globale.

Interfacce logiche proposte, espresse senza vincolare la rappresentazione
interna dello stato delle voci:

```text
prepare_reference(position, context, parameters, state)
    → riferimento ritmico + materiale preparato del produttore

compose(request, state, prepared_material)
    → frase + contributi ai gesti + decisioni + next_state
```

La prima interfaccia è richiesta soltanto al produttore del riferimento.
Il materiale preparato appartiene a quella voce e non viene interpretato
dal Coordinator. Le altre voci ricevono soltanto il riferimento musicale.

La sessione prepara il piano, valida tutte le frasi e tutti gli obblighi,
quindi accetta insieme risultati, memoria e stati successivi. Se la
preparazione fallisce, non avanza lo stato confermato. Una richiesta
ripetuta non consuma due volte gesti, turni o sequenze casuali.
Un intervallo accettato non viene rigenerato con parametri differenti:
richiede cancellazione esplicita, che è consentita soltanto per musica
ancora futura rispetto al trasporto osservato.

La consegna ai device è successiva all'accettazione musicale. Lo stato
distingue piano accettato, consegna effettuata dal trasporto e intervallo
trascorso sul clock osservato. L'invio UDP non costituisce conferma audio
né garantisce una consegna atomica a tutti i device.

La cancellazione di un piano invalida gesti e risposte future che ne
dipendono. I piani dipendenti già consegnati devono essere annullati dal
percorso di reset prima di ripianificare. Non si modifica musica trascorsa.
Per i piani ancora revocabili si conservano stati di ingresso e uscita:
la cancellazione ripristina l'ultimo stato valido oppure apre una nuova
epoch. Non lascia memoria o stato derivati da musica cancellata.
Stop, restart e discontinuità aprono una nuova epoch, svuotando memoria
relazionale e risposte pendenti; i controlli manuali restano separati.

## 8. Silenzi, confini e note lunghe

Sorgente assente, sorgente silenziosa e gesto ancora incompleto sono stati
distinti. Una sorgente di configurazione sconosciuta è sempre un errore.
`on_unavailable` riguarda l'indisponibilità musicale legittima: una sorgente
inattiva, nessun gesto nel limite di ricerca o un gesto scaduto.

Un gesto completo già in memoria può ricevere risposta mentre la sua
voce è ora silenziosa. La scelta `independent` continua il materiale
proprio del destinatario; `silence` rende silenzioso l'intervallo di
destinazione riservato alla relazione; `error` interrompe il piano.
La decisione applicata deve essere ispezionabile.
La politica `independent` richiede che il destinatario dichiari e implementi
materiale autonomo. Non può essere attivata sul basso attuale senza
aggiungere tale capacità: oggi una melodia vuota ne determina il silenzio.
Una politica non supportata è rifiutata dalla validazione.

Un cambio di sezione non azzera automaticamente memoria e fase.
`continue_if_active` completa l'intervento se il destinatario resta attivo;
`cancel_at_section` lo conclude al confine dichiarato. L'uscita dall'organico
cancella gli interventi pendenti della voce. Il nuovo contesto armonico
non riscrive i gesti storici: un loro adattamento richiede una trasformazione.

Il modello esecutivo iniziale conserva `Phrase` e il vincolo che ogni nota
termini nella finestra. I gesti possono attraversare finestre tramite note
distinte. Una nota da sostenere senza riattacco oltre il confine richiede
un'estensione esplicita del modello e del player: fino ad allora non è
supportata e non viene convertita automaticamente in note riarticolate.

## 9. GPX e organizzazione delle decisioni

Le misure del viaggio rimangono in `trip/`. L'interpretazione configurata
produce contesto musicale e attivazione delle relazioni: non passa
coordinate o pendenze al Coordinator come istruzioni compositive.

Ogni decisione usa il tratto del percorso associato all'intervallo musicale
da pianificare, non la posizione attualmente mostrata dal player. La
corrispondenza fra percorso e musica è un requisito separato, descritto
nel [piano del contesto locale](SEZIONI-GUIDATE-DAL-VIAGGIO.md).

Precedenza e rilascio manuale seguono il
[contratto approvato della direzione adattiva](DIREZIONE-ADATTIVA.md),
implementato per il controllo manuale: l'assetto fornisce la base, le strategie proposte adattano
i controlli dichiarati rispettando i vincoli espliciti, il flag `manual`
mantiene manuale soltanto il parametro interessato. Le relazioni risolte non
sovrascrivono i parametri di base: aggiungono indicazioni alla composizione.
I cambi di struttura entrano dal confine successivo del gesto coinvolto;
gli interventi già accettati mantengono il proprio stato risolto, salvo
cancellazione esplicita o uscita dall'organico.

Non si riducono tutte le misure a un unico indice di energia. Dato
non disponibile e valore zero rimangono distinti; le regole dichiarano
persistenza e transizione. Il GPX non sceglie implicitamente un genere.

## 10. Compatibilità e verifica

`groove_follow` è la vista utente di una relazione ritmica verso il
riferimento: non introduce un secondo calcolo di adesione. Il peso di
genere agisce invece nella produzione del riferimento, a monte delle voci.
Ruolo della voce, stile delle drums e relazione musicale restano distinti.

Il contratto non cambia implicitamente i parametri correnti. In particolare,
`rhythm_follow` del basso e `follow_source` della tessitura mantengono il
significato documentato fino a una migrazione esplicita. I valori iniziali
dei nuovi legami sono zero. Le configurazioni senza nuove relazioni devono
continuare a produrre il risultato precedente.

Le informazioni esposte dallo stato includono intervallo, sorgente e gesto
selezionati, trasformazioni, influenze risolte, indisponibilità, confini,
esito dei vincoli e provenienza delle indicazioni GPX. I dettagli della
memoria e dei punteggi non diventano automaticamente controlli del device.

Verifiche richieste per l'implementazione:

- Risposta a un gesto precedente mentre il chiamante tace; nessuna risposta a una chiamata interamente silenziata.
- Reciprocità fra intervalli successivi e rifiuto di un ciclo nella stessa finestra, prima di avanzare stato.
- Risultato identico dopo richiesta duplicata o tentativo di pianificazione fallito.
- Gesto attraversato da più finestre con identità e riferimento stabili.
- Sorgenti assenti, vuote, incomplete e scadute distinte e gestite secondo contratto.
- Registro incompatibile con un unisono obbligatorio segnalato, senza trasposizione implicita.
- Reset e cancellazione senza memoria riferita a piani invalidati.
- Stesso GPX, contesto, stato e seed riproducono la composizione.
- Nuovi legami a zero conservano il comportamento esistente.

Per chiamare una relazione Counterpoint occorrono criteri espliciti per
intervalli simultanei, movimento e dissonanze. Fino a quel collegamento,
il contratto abilita riferimenti e verifiche, non certifica contrappunto
con il solo nome della relazione.

## 11. Esempio completo di risposta imitativa

Esempio di contratto, non configurazione già caricabile dal sistema:

| Elemento | Valore |
|---|---|
| Chiamata | Gesto melodico nei beat logici `[0, 4)`, note MIDI 60, 62, 64 agli attacchi 0, 0,5, 1; durata di ogni nota 0,25 beat |
| Sorgente della risposta | Quel gesto completo, letto dalla storia e vincolato al suo identificativo |
| Destinatario | Basso, registro dichiarato 28–47 |
| Intervallo riservato | `[4, 8)`; il chiamante cede il primo piano secondo il piano delle interazioni |
| Collocazione | Un beat dopo la fine della chiamata |
| Trasformazioni | Durate e distanze fra attacchi ×2; trasposizione −24 semitoni |
| Materiale di riferimento ottenuto | Altezze 36, 38, 40 agli attacchi assoluti 5, 6, 7; durata di ogni nota 0,5 beat |
| Relazione | `preference`, influenze esplicite per ritmo e altezze; il generatore conserva i propri vincoli |
| Sorgente indisponibile | Politica dichiarata, senza ricerca di un altro chiamante |

Le posizioni sono beat, non indici di finestra. Se la consegna divide
l'intervento in più finestre, sorgente e trasformazioni restano identiche.
La versione `exact` deve riprodurre il materiale richiesto oppure dichiarare
l'incompatibilità; la versione `preference` compone in relazione a esso e
non promette quelle note esatte.
