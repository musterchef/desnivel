# Contratto delle percussioni

Stato: contratto approvato. Centralizzazione e consolidamento della
configurazione implementati; generazione a regole ancora da implementare. Il comportamento disponibile è descritto in
[Stili percussivi](../STILI-PERCUSSIVI.md). Il design precedente, comprese
fonti e proposte conservate, è in [archivio](../archivio/STILI-PERCUSSIVI.md).

## Obiettivo

Un solo catalogo per il materiale percussivo, una sola mappa per la
destinazione attuale, una configurazione operativa della sessione.
La composizione deve poter produrre nuove figure applicando regole
musicali, usando i pattern di riferimento per verificare lo stile.

## Stato verificato

- Il catalogo conserva i materiali `spaced_impacts`, `spaced_dialogue`,
  `regular_pulse_eighths`, `regular_pulse_offbeats` e i tre profili stilistici.
- La CLI risolve i riferimenti senza caricare definizioni di colpi dai JSON.
- La mappa MIDI è in `adapters/percussion.py`; l'avvio usa `organico.json`.
- Il motore continua a sviluppare materiale precomposto. Il compositore
  a regole descritto nelle sezioni successive non è ancora disponibile.

## 1. Unica fonte per ciascuna responsabilità

Catalogo, mappa e collegamento CLI della tabella sono presenti. La
conversione finale degli eventi in `Phrase` è ancora eseguita dal motore
esistente; il trasferimento al confine adattatore accompagna il compositore a regole.

| Sede | Responsabilità |
|---|---|
| `music/percussion/catalog.py` | Identificativi dei ruoli percussivi, materiali di riferimento e profili stilistici. Un solo catalogo Python, senza numeri MIDI o nomi di device |
| `music/percussion/` | Generazione, memoria musicale, dialogo e transizioni. Legge il catalogo, senza ridefinirne i dati in altri moduli |
| `adapters/percussion.py` | Unica mappa dei ruoli verso i pad della destinazione attuale e conversione degli eventi musicali in `Phrase` |
| `presets/organico.json` | Voci, dipendenze, destinazioni, valori iniziali e riferimenti ai materiali necessari durante la migrazione. Nessuna lista di colpi o copia della mappa MIDI |
| `presets/direzione-viaggio.json` | Politiche musicali delle sezioni e collegamento ai dati del percorso. Nessuna sequenza di colpi |

`styles.py` deve importare le definizioni dal catalogo; non deve conservarne
una seconda copia. La CLI collega generatore e adattatore. Director,
Coordinator, device comune e modelli generici non acquisiscono nomi o
regole delle percussioni.

`dialogo.json` è ritirato dall'uso operativo; prove e riferimenti sono migrati. I materiali musicalmente diversi vengono
conservati nel catalogo con identificativi univoci. Le modalità della
tessitura e i valori delle drums restano regolabili dai controlli esistenti.
Non si aggiungono file JSON per genere, kit o variante, né un sistema di
ereditarietà fra configurazioni. I file di analisi del percorso conservano
la propria responsabilità separata.

## 2. Centralizzazione: risultato musicale invariato

Intervento implementato, verificato confrontando eventi, guida e dialogo
multivoce prima e dopo la centralizzazione. La generazione a regole resta
il passaggio successivo.

- Trasferire nel catalogo tutti i materiali e le figure attuali.
- Assegnare identificativi distinti ai due `regular_pulse`.
- Conservare ruoli, intensità, posizioni, ancore e sequenze di sviluppo.
- Risolvere la mappa dei pad una sola volta nell'adattatore, mantenendo
  esattamente le destinazioni MIDI attuali.
- Sostituire le definizioni incorporate nei JSON con riferimenti al catalogo.
- Verificare l'identità degli eventi prima/dopo per entrambe le configurazioni,
  compresi variazione, silenzi delle sorgenti e transizioni.
- Rifiutare riferimenti o ruoli sconosciuti con errore esplicito.

La configurazione operativa viene consolidata dopo il confronto delle due
configurazioni originali; l'eliminazione della seconda configurazione non
comporta l'eliminazione dei suoi materiali o delle prove utili.

## 3. Contratto della generazione a regole

### Ingressi

Il generatore riceve posizione logica, durata richiesta, fase musicale,
stile, controlli esistenti, contesto della sezione, frasi dipendenti e
memoria accettata. Utilizza le interfacce di pianificazione già esistenti.
Non legge GPX, JSON o stato del device durante la composizione.

### Regole dello stile

Il profilo definisce vincoli e preferenze verificabili:

- appoggi caratterizzanti per ruolo, distinguendo obblighi e preferenze;
- suddivisioni ammesse e quantità compatibili con i ruoli;
- relazioni fra cassa, backbeat e accompagnamento;
- rapporti di accento e regole di timing;
- possibilità di risposta, variazione e chiusura della frase.

Per esempio, la cassa sui quattro movimenti è un vincolo coerente della
House classica. La costruzione dei complementi e delle loro relazioni
resta una decisione del generatore.

Le regole devono produrre combinazioni di attacchi non limitate alle
figure scritte nel catalogo. I pattern di riferimento servono al confronto
musicale e ai test: il generatore a regole non li sceglie come frasi da
riprodurre e non vi ricorre come ripiego.

### Eventi e pianificazione

Ogni evento musicale descrive posizione in beat, ruolo percussivo,
intensità e durata. La conversione verso i pad avviene nel confine
adattatore prima della consegna della `Phrase` al coordinamento.

Il generatore prepara un intervallo musicale completo anche quando viene
richiesta soltanto una sua porzione. Fase, seed e memoria determinano
scelte riproducibili. Le porzioni della stessa battuta non vengono composte
indipendentemente.

Le scelte riguardano relazioni fra parti e figure coerenti. Il sorteggio
indipendente di ogni colpo non costituisce la strategia compositiva.
Riprese e silenzi musicali rimangono possibili.

### Dialogo

1. Le drums preparano gli appoggi strutturali della guida condivisa.
2. Le altre voci compongono ricevendo la guida e le influenze disponibili.
3. Le drums completano i complementi usando le frasi delle altre voci.
4. La memoria del risultato accettato influenza le scelte successive.

I complementi possono adattarsi al basso e lasciare spazio alla melodia.
Gli appoggi già comunicati non vengono spostati retroattivamente in risposta
alla stessa finestra. Presenza e sospensioni musicali esplicite possono
silenziare la voce; la guida può restare disponibile secondo il contratto
multivoce attuale. Preparazione e tentativi falliti non avanzano la memoria.

## 4. Controlli

| Controllo | Responsabilità |
|---|---|
| Stile | Vincoli e preferenze musicali applicati alla generazione |
| Variazione 0–1 | Libertà rispetto alla figura base derivata dalle regole: a zero è stabile nello stesso contesto; a uno usa tutto lo sviluppo consentito |
| Transizione in beat | Durata del passaggio fra i profili, mantenendo fase e continuità |
| `displacement_beats` | Ampiezza degli spostamenti consentiti, distinta dalla probabilità di usarli |
| `support_tolerance_beats`, `answer_clearance_beats` | Distanze musicali per sostegno e risposta |
| `velocity_ratio`, `gate_beats`, `seed` | Dinamica finale, durata MIDI e riproducibilità |

Nessun controllo aggiunto per compensare doppioni interni. Un controllo
conservato deve avere un effetto verificabile e risultare inattivo quando
non applicabile.

Nella centralizzazione, **Nessuno** mantiene il comportamento attuale.
Nel generatore a regole significherà assenza di vincoli stilistici specifici:
si applicheranno le regole ritmiche generali dello stesso motore, senza
un secondo percorso basato su sequenze precomposte.

## 5. Collegamento al GPX proposto

L'intensità musicale normalizzata della sezione esiste già come
`section.direction.target_intensity`, da 0 a 1. La proposta iniziale è
usarla come valore automatico di Variazione per la voce percussiva.
È una scelta compositiva esplicita: maggiore intensità autorizza maggiore
sviluppo, senza imporre BPM, genere o casualità aggiuntivi.

La traduzione appartiene al collegamento fra direzione del viaggio e voce,
non al Coordinator generico. Un valore di sezione esplicitamente assegnato
prevale sul calcolo automatico; l'override manuale prevale su entrambi.
L'origine del valore deve risultare nello stato. Con sezioni manuali si
usano i valori configurati. Questa mappatura non è attualmente implementata.

La gestione automatica e il rilascio degli interventi utente seguono il
[contratto della direzione adattiva](DIREZIONE-ADATTIVA.md), implementato
per il controllo manuale. Il flag `manual` riguarda un singolo parametro;
gli altri mantengono la propria modalità. Le strategie adattive restano
da implementare; lo stile rimane una scelta esplicita.

## 6. Transizioni e influenze multiple

La generazione interpola preferenze compatibili e conserva appoggi comuni.
I conflitti vengono risolti musicalmente per ruoli e frase; non si sommano
due loop completi. Si mantiene il metro 4/4 del banco di prova attuale.
Un cambio durante una transizione riparte dallo stato musicale raggiunto.

La miscela manuale di generi rimane un'estensione futura. Un peso indica
influenza stilistica sulle scelte, non volume o percentuale esatta di colpi.
La semantica proposta resta:

- somma zero: regole generali senza stile specifico;
- somma fino a uno: i pesi conservano il proprio valore; la quota residua
  appartiene alle regole generali;
- somma superiore a uno: normalizzazione dei pesi alla somma uno.

House 0,2 lascia quindi 0,8 alle regole generali; House 1 e Boom bap 1
risolvono in 0,5 ciascuno. Non si aggiungono ora controlli per questa estensione.

## 7. Verifiche richieste

- Centralizzazione: stesso risultato musicale e stessa mappa dei pad,
  senza definizioni duplicate nei JSON e nei moduli.
- Generazione a regole: capacità di comporre figure assenti dal catalogo;
  modificare le sole figure di riferimento non cambia l'algoritmo compositivo.
- Differenze stilistiche spiegabili con regole esplicite e confronto
  all'ascolto, mantenendo kit, BPM e seed costanti.
- Variazione 0/intermedia/1 e influenza della sezione verificabili sulle scelte.
- Dialogo in entrambe le direzioni, senza cicli nella stessa finestra o
  alterazioni dei piani già accettati.
- Fase invariata al cambio di stile e fra finestre; nessun doppio avanzamento
  dopo tentativi scartati. I confronti fra partizioni usano gli stessi input musicali.
- Coincidenze gestite, durate valide e limite di 128 attacchi rispettato;
  nessuna soppressione silenziosa per aggirare errori o limiti.

## Ordine degli interventi

1. Contratto approvato.
2. Materiale e mappa centralizzati, identità musicale verificata.
3. Avvio consolidato su `organico.json`, guide e prove aggiornate.
4. Definire i profili di regole dei tre stili e implementare il compositore,
   il collegamento al GPX proposto e le transizioni sulle regole.
5. Verificare all'ascolto prima di ampliare generi o controlli.
