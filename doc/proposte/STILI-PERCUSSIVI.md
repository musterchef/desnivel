# Stili percussivi

Stato: selezione nominale implementata con i profili House classica,
Boom bap e Breakbeat house. Configurazione e comportamento effettivi sono
descritti in [Selezione dello stile percussivo](../STILI-PERCUSSIVI.md).
Questo documento conserva il design del catalogo e la proposta ancora
non implementata della combinazione di influenze da 0 a 1.
Memoria dei gesti, relazioni fra voci e accettazione dei piani sono definite
nei [contratti per le relazioni musicali](RELAZIONI-MUSICALI.md).

## Obiettivo

Dare alla percussione un carattere ritmico riconoscibile, conservando
sviluppo nel tempo, relazione con le altre voci e controlli esistenti.
Il selettore **Stile** rappresenta la componente ritmica di un genere:
disposizione degli attacchi, accenti, suddivisioni e groove.
Il timbro rimane nello strumento e il BPM nel trasporto della sessione.

Un genere può usare più pattern e uno stesso pattern può apparire in
generi diversi, come mostrano gli esempi di
[Ableton Learning Music](https://learningmusic.ableton.com/make-beats/rock-and-house.html).
Il catalogo deve quindi descrivere profili circoscritti, per esempio
`house_classic`, evitando di presentare un singolo loop come definizione
completa di House o Hip-hop.

## Punto di partenza verificato nel codice

`music/percussion/development.py` contiene `PercussionPhraseGenerator`:

1. Legge `material`, `anchor_beats`, `development` e `interaction`.
2. Applica ripetizione, sottrazione, spostamento, accento o silenzio.
3. Allinea i sostegni alla sorgente configurata e omette le risposte troppo vicine agli attacchi melodici.
4. Combina il risultato con `standard_material` attraverso `conceptuality`.
5. Applica fattore di velocity, durate MIDI e limiti della frase.

Con `style: none`, il materiale di `organico.json` dura 32 beat e il groove
standard quattro. La posizione logica avanza fra richieste. Con uno stile
attivo, il suo vocabolario alimenta entrambi i rami e la guida ritmica;
casse e backbeat strutturali restano protetti dall'interazione. Il
registro e il device supportano scelte nominali tramite `ChoiceControl`.

Sostituire soltanto `standard_material` non soddisfa l'obiettivo: con
`conceptuality = 1` quel ramo non contribuisce al risultato. Inoltre una
cassa regolare può scomparire se la sorgente di sostegno non suona.

## Rappresentazione di uno stile

Si propone un piccolo catalogo di dati musicali, interpretato dal modulo
della percussione. Ogni profilo contiene soltanto informazioni usate dalla
generazione:

| Informazione | Funzione |
|---|---|
| Identificativo stabile e nome | Selezione, configurazione, preset e stato leggibile |
| Metro e lunghezza del ciclo | Interpretazione delle posizioni e della fase del materiale |
| Poche varianti coerenti | Vocabolario ritmico, con relazioni fra cassa, rullante e piatti |
| Attacchi strutturali e complementari | Identità del groove e materiale disponibile per trasformazioni e dialogo |
| Accenti relativi | Rapporti di velocity, prima di `velocity_ratio` |
| Suddivisione e timing | Posizioni dritte, swing o altre articolazioni specificate esplicitamente |
| Fonti e motivazione musicale | Riscontro dei caratteri scelti e riferimento per l'ascolto |

I profili usano ruoli percussivi come cassa, rullante e hi-hat, senza
numeri MIDI. La definizione della voce li associa alle `lanes` esistenti;
la mappa MIDI rimane unica. Non sono preset del generatore: selezionare
uno stile non deve sovrascrivere `variation`, `conceptuality` o gli altri
valori manuali.

Le varianti devono indicare un riferimento e le figure alternative che
lo sviluppo può usare. Non è previsto scegliere a caso un nuovo loop a
ogni finestra: il materiale mantiene la propria fase e la sequenza di
sviluppo conserva la responsabilità delle trasformazioni.

Per la prima implementazione si propongono tre profili in 4/4, con cicli di una o due
battute e almeno due varianti semplici per profilo:

| Profilo proposto | Caratteri da specificare e confrontare |
|---|---|
| House classica | Cassa regolare sui quattro movimenti, backbeat e hi-hat in levare |
| Boom bap anni Novanta | Relazione sincopata fra cassa e backbeat, accenti e swing documentato |
| Breakbeat house | Cassa spezzata, relazione con rullante/clap e articolazione dei piatti |

Questi tre profili sono disponibili nel catalogo iniziale per l'ascolto.
Le fonti propongono esempi concreti, non valori universali per tutti i
brani del genere. I primi due profili permettono inoltre di verificare
che la differenza non dipenda soltanto dal numero dei colpi.

Il metro è una proprietà del profilo percussivo, non una deduzione da
`window_beats`. Una finestra rimane un intervallo di pianificazione.
La verifica musicale iniziale usa Live in 4/4; non introduce cambi di metro
globali o adeguamenti automatici del BPM.

## Inserimento nel generatore

Ordine proposto, con distinzione fra attacchi strutturali e complementari:

```text
materiale corrente + profilo di stile
                 ↓
materiale ritmico, accenti e attacchi strutturali
                 ├── riferimento regolare
                 └── sviluppo → interazione con le altre voci
                                      ↓
                    combinazione con conceptuality
                                      ↓
                    velocity_ratio e gate_beats → Phrase
```

Lo stile deve orientare entrambi i rami. `conceptuality` conserva la
responsabilità di scegliere fra riferimento e materiale sviluppato;
non diventa un controllo dell'intensità del genere.

Gli attacchi strutturali del profilo selezionato mantengono posizione e
funzione anche quando la melodia occupa lo stesso istante o il basso è
silenzioso. L'interazione lavora sui complementi: può allinearli al basso
o diradarli per lasciare spazio alla melodia. `variation` agisce sui
complementi; `displacement_beats` resta l'ampiezza degli spostamenti
previsti dalla sequenza di sviluppo.

Il coordinamento definito prevede che con uno stile attivo alcune
figure diventano autonome dalle sorgenti, per conservarne l'identità.
La presenza della voce e l'operazione esplicita `silence` continuano a
poter sospendere l'intera parte. Sul ramo regolare il comportamento di
`silence` resta quello attuale: è un'operazione del ramo sviluppato.

Gli attacchi strutturali vanno identificati per evento e funzione, non
soltanto per beat: una cassa caratterizzante non deve proteggere anche
qualsiasi altro colpo che capita alla stessa posizione.
Swing e timing del profilo hanno una funzione distinta dallo spostamento
compositivo `displace`. I loro effetti devono essere tracciabili separatamente.

Con **Stile: nessuno** si percorre esattamente il comportamento attuale,
senza cambiare materiali, regole di interazione, fase o risultato MIDI.
Con uno stile selezionato si usa il suo vocabolario; non si rinomina il
materiale attuale assegnandogli soltanto un'etichetta.

## Controlli e integrazione

Per la selezione del genere si aggiunge il controllo **Stile**, con scelta nominale e
valore iniziale **nessuno**. Il catalogo usa identificativi testuali
stabili, mai indici dipendenti dall'ordine di un menu.

Il device richiede una scelta enumerata generica definita da Python.
Il JavaScript presenta le opzioni e trasmette l'identificativo; nomi e
regole dei generi restano nel modulo percussivo e nei suoi dati.
Il ruolo rimane `percussion`, distinto dallo stile. I controlli di adesione
ritmica delle altre voci appartengono ai loro generatori, secondo il
contratto di [coordinamento](COORDINAMENTO-RITMICO.md).

La scelta deve entrare nelle assegnazioni, negli override manuali e nei
preset, conservando le precedenze della sessione. L'aggiunta del controllo
richiede una gestione esplicita dei preset utente già salvati: oggi viene
richiesta la corrispondenza esatta delle chiavi. La proposta è aggiungere
`nessuno` ai preset compatibili precedenti, senza scartare altri campi o
riscrivere la libreria automaticamente.

Le modifiche si applicano alle finestre ancora da pianificare, mantenendo
la posizione logica e i periodi di sviluppo. Gli eventi di un ciclo che
attraversa più finestre vanno selezionati dalla stessa fase. Non si
riavvia il motivo al cambio di stile e non si modifica un piano già inviato.

## Influenze multiple: semantica proposta per il futuro

Un peso da 0 a 1 esprime quanto un profilo orienta le scelte musicali,
non il volume della batteria, una classificazione del brano o una quota
esatta di note appartenenti a un genere.

La rappresentazione musicale interna prevista è una mappa di pesi per
identificativo. La prima interfaccia nominale corrisponde a un unico
peso 1; **nessuno** corrisponde alla mappa vuota. L'interfaccia con più
pesi non viene implementata nella prima versione.

Indicando con `S` la somma dei pesi:

- Se `S = 0`, rimane soltanto il materiale corrente.
- Se `0 < S ≤ 1`, ogni peso conserva il valore impostato e al materiale
  corrente resta `1 − S`.
- Se `S > 1`, i pesi vengono divisi per `S`; il materiale corrente non
  contribuisce. Lo stato deve mostrare sia i pesi richiesti sia quelli risolti.

| Pesi richiesti | Contributi risolti |
|---|---|
| House 0,2 | Materiale corrente 0,8; House 0,2 |
| House 0,6; boom bap 0,3 | Materiale corrente 0,1; House 0,6; boom bap 0,3 |
| House 1; boom bap 1 | House 0,5; boom bap 0,5 |

Normalizzare sempre i soli generi sarebbe scorretto per questa semantica:
un unico peso 0,2 diventerebbe indistinguibile da 1.

Per combinare gli stili si propone di scegliere e combinare figure
coerenti: relazione cassa/rullante come gruppo, articolazione dei piatti
come altro gruppo. Non si sommano interi loop né si estraggono tutti i
singoli colpi indipendentemente. Un risultato può così avere appoggi di
uno stile e piatti di un altro nella stessa frase, senza essere soltanto
un'alternanza di battute etichettate con generi diversi.

La scelta dei gruppi e delle varianti deve essere riproducibile con seed,
posizione logica e pesi. Timing incompatibili e conflitti fra figure
richiedono regole di compatibilità esplicite: la definizione concreta del
miscelatore resta da definire e non è necessaria alla prima versione.

## Criteri di verifica

- Con **nessuno**, identità del risultato rispetto al generatore corrente,
  comprese le combinazioni dei controlli e i silenzi delle dipendenze.
- Stile riconoscibile a `conceptuality = 0` e a `1`, durante le frasi non
  sospese; presenza, `silence` e fine finestra continuano a essere rispettati.
- Stesso seed e stesse richieste producono lo stesso risultato; suddividere
  un ciclo fra finestre non ne riavvia fase, swing o figure caratteristiche.
- Nessun raddoppio involontario, sovrapposizione della stessa nota o
  superamento dei 128 attacchi; nessuna riduzione silenziosa del materiale.
- Selezione dello stile senza modifica degli altri parametri; salvataggio,
  ricarica e compatibilità esplicita dei preset precedenti.
- Ascolto A/B dello stesso tratto con kit, BPM e seed uguali, prima con
  ogni stile isolato e poi con l'interazione attiva. Secondo confronto ai
  tempi di riferimento, impostati manualmente, per valutare il feel.

La scelta finale dei profili e la taratura richiedono ascolto. Una fonte
testuale o la distanza fra due griglie non certificano il risultato musicale.

## Fonti esaminate e uso proposto

Le scelte architetturali e la semantica dei pesi sopra sono proposte per
Desnivel; non sono ricavate come prescrizioni dalle fonti.

| Fonte | Informazione utile e impiego |
|---|---|
| [LANDR — Drum programming](https://blog.landr.com/drum-programming/) | Raccolta iniziale di esempi per House, Techno, Trap, Hip-hop e DnB; distingue programmazione, dinamica, timbro e arrangiamento. Utile per orientare il confronto fra famiglie. |
| [Drum Patterns — presentazione](https://drum-patterns.com/about/) | Libreria condivisa di pattern e loop; le griglie, le categorie e le varianti osservate nel sito sono esempi da confrontare per costruire il vocabolario dei profili. Le etichette dei contributi non sono una definizione normativa dei generi. |
| [Roland — Creating beats for dance styles](https://www.roland.com/uk/blog/creating-beats-dance-styles-dj-808/) | Dimostrazioni e sequenze per stili dance, con dettagli su suoni e shuffle. Riferimento operativo per la House classica e per separare pattern e scelta del kit. |
| [Attack — Breakbeat House](https://www.attackmagazine.com/technique/beat-dissected/breakbeat-house-beats/) | Tutorial originale con costruzione del groove, parti percussive, accenti e indicazioni di swing. Riferimento per un profilo circoscritto e le sue varianti. |
| [BandLab — How to make a boom bap beat](https://blog.bandlab.com/how-to-make-a-boom-bap-beat-on-bandlab/) | Tutorial originale con progetto di riferimento, programmazione delle parti, dinamica e scostamenti dalla griglia. Base operativa per il profilo boom bap, da confrontare con altri esempi. |
| [Roland — Trap and lo-fi beats](https://articles.roland.com/trap-and-lo-fi-beats-with-zenbeats-and-roland-cloud/) | Confronto di due approcci produttivi con esempi dell'autore; utile per distinguere figurazioni, tempo e suoni prima di estendere il catalogo. |
| [Roger Linn — Swing e groove, intervista](https://www.attackmagazine.com/features/interview/roger-linn-swing-groove-magic-mpc-timing/) | Spiegazione diretta del timing alternato e della dinamica. Il suo swing usa 50% per il dritto: non va confuso con percentuali di altre macchine né con il futuro peso di stile. |
| [Ableton — Tempo and genre](https://learningmusic.ableton.com/make-beats/tempo-and-genre.html) | Il riconoscimento di genere dipende anche da tempo e suoni. I tempi tipici sono riferimenti d'ascolto, non vincoli o cambi automatici della sessione. |
| [Magenta — GrooVAE](https://magenta.tensorflow.org/groovae) | Distinzione fra disposizione delle parti, dinamica e microtiming. Utile come riferimento di analisi; non richiede di adottare il modello generativo. |
| [Magenta — Groove MIDI Dataset](https://magenta.tensorflow.org/datasets/groove) | Esecuzioni MIDI umane annotate per stile e tempo, utili per confrontare varianti e accenti. La mappatura dei suoni differisce in parte dal General MIDI e richiede conversione esplicita. Nessun dataset è stato importato. |

Prima di inserire un profilo operativo occorrono esempi completi verificati,
una descrizione dei tratti effettivamente modellati e un confronto all'ascolto.
La prima implementazione non richiede addestramento di modelli o raccolta automatica di pattern.


## Evoluzione e transizioni implementate

Il sistema sviluppa figure stilistiche su frasi di quattro battute e
interpola eventi e timing nel cambio di stile tramite `transition_beats`.
I pesi multipli sono stato interno della transizione, non controlli di
miscela indipendenti. Il comportamento disponibile è descritto in
[STILI-PERCUSSIVI.md](../STILI-PERCUSSIVI.md). La miscela manuale di più
generi rimane una proposta.
