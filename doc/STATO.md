# Stato del progetto

## Sessione principale

La sessione operativa è `desnivel.cli.ensemble`, configurata da
`presets/organico.json`. Snake, il player del basso e gli altri comandi
di composizione restano banchi di prova separati.

| Componente | Stato effettivo |
|---|---|
| Direzione GPX | Tavolozza, motivo, armonia e assetti per macrosezione disponibili |
| Parametri dei device | Modalità auto/manual per parametro; in auto seguono i valori configurati della sezione |
| Dialogo musicale | Guida delle drums, dipendenze fra frasi e influenze ritmiche storiche disponibili |
| Contesto locale | Tratto rappresentato dalla finestra, pendenza, cambiamento e persistenza disponibili nello stato |
| Osservazione musicale | Ultimi 16 beat accettati: attacchi, occupazione, registro e copertura per voce |
| Adattamento continuo dei parametri | Da implementare: risolutore, politiche delle voci e transizioni, compreso il rilascio graduale dal manuale |
| Drums | Sviluppo di materiale precomposto, quattro figure per stile e transizioni disponibili; compositore a regole da implementare |

Contesto locale e osservazione non modificano ancora i parametri.
Variazione delle drums può restare fissa mentre cambiano le figure,
le trasformazioni e le risposte alle altre voci.
Il lavoro successivo è descritto nella
[direzione adattiva](proposte/DIREZIONE-ADATTIVA.md); le pulizie individuate
sono nella [revisione dei controlli](proposte/REVISIONE-CONTROLLI.md).

## Funzionalità operative

### 1. Dati del viaggio e telemetria
- Lettura dei file GPX con interpolazione e calcolo continuo delle metriche (distanza, quota, pendenza, velocità, stima di sforzo).
- Ricampionamento dei dati a 10 Hz e pubblicazione OSC delle metriche ogni secondo del viaggio. La frequenza di pubblicazione è configurabile.
- Replay accelerato del viaggio per l'ascolto in tempo reale.

### 2. Generazione melodica (Snake)
- Generazione di pattern melodici in base all'avanzamento del viaggio e alla combinazione di velocità e sforzo.
- Transizioni tra sezioni della tappa con modulazione di scale e altezze di riferimento.
- Controllo in tempo reale dei parametri di Snake in Ableton Live tramite bridge Max for Live.
- Telemetria e previsione dello stato del sequencer (`/snake/state`) per la sincronizzazione delle altre voci.

### 3. Generatore del basso
- Composizione autonoma di linee di basso a partire dalla melodia (sostegno, dialogo o contrappunto ritmico).
- Sincronizzazione con il trasporto di Ableton Live tramite player dedicato a eventi programmati (`timepoint`).
- Tre assetti sonori calibrati: `sobrio` (appoggio minimale), `dialogo` (risposte negli spazi) e `ritmico` (slap e accenti sui levare).
- Aggiornamento dinamico dei parametri durante l'esecuzione tramite messaggi OSC (`/desnivel/v1/bass/control`) con transizioni fluide interpolate su finestre temporali.

### 4. Sessione multivoce condivisa
- Avvio unico con `desnivel.cli.ensemble`: replay GPX, selezione del contesto delle sezioni, coordinamento dei generatori e invio delle frasi alle destinazioni.
- Organico e ruoli configurati per sezione; selezione manuale del ruolo e ritorno a `Follow section` dal dispositivo comune `Desnivel_Voice`.
- Generazione melodica da cellule del motivo, con ripresa, trasformazioni e continuità fra periodi; respirazioni e chiusure sulla tonica distanziate di 2–4 periodi partecipanti. Motivo letterale disponibile per il confronto. [Generazione melodica](MELODIA.md).
- Collegamento delle parti al trasporto di Live e controlli compositivi esposti dal motore Python.
- Presenza per frase della sezione e moltiplicatore manuale per voce, separati dalla densità e dalla velocity.
- Controlli pertinenti al ruolo e alla modalità segnalati dal generatore; etichette e switch visualizzati dal device comune senza regole specifiche degli strumenti.
- Le modifiche ai singoli controlli mantengono manuale soltanto il parametro scelto; gli altri continuano a seguire le sezioni. La selezione di un preset applica invece l'intero insieme dei valori.
- Tessitura sostenuta in `music/texture/`, con registro, velocity e switch `follow_source`: sostegno del grado di sezione oppure scelta da una frase sorgente. La voce Atmosphere legge facoltativamente la melodia; in modalità coordinata ne segue anche i silenzi.
- Percussione con materiale, trasformazioni e interazione con le frasi di melodia e basso; unico controllo continuo **Variazione** per figure e trasformazioni.
- Dialogo ritmico configurabile: guida prodotta dalle drums, `groove_follow` per melodia e basso, memoria dei gesti completi e influenze ritmiche dalle frasi precedenti. Le drums continuano a reagire a melodia e basso nella finestra corrente. Configurazione operativa in `presets/organico.json`; dettagli in [Dialogo ritmico](DIALOGO-MUSICALE.md).
- Catalogo percussivo unico in `music/percussion/catalog.py`, riferimenti nei JSON e mappa dei pad in `adapters/percussion.py`.
- Selettore **Stile** per le drums: Nessuno, House classica, Boom bap e Breakbeat house. I profili orientano guida e materiale, conservando struttura, sviluppo e interazione; quattro figure per profilo, evoluzione su frasi e transizioni graduali regolabili in beat. Scelta nominale disponibile sul device e salvabile nei preset. [Stili percussivi](STILI-PERCUSSIVI.md).
- Vista globale nel terminale e snapshot JSON con avanzamento, collegamenti, ruoli e decisioni effettive di Director e Coordinator.
- Direzione dalle macrosezioni del GPX con assetti musicali configurati per famiglia; modalità con sezioni manuali disponibile.
- Direzione armonica automatica dal profilo complessivo: scelta della tavolozza, evoluzione di root e scala nelle macrosezioni e motivo ricavato dalla forma della tappa. Override di tavolozza, root, scala e motivo generali o per tappa. Attiva nelle configurazioni fornite; `--manual-sections` conserva la modalità manuale. [Direzione musicale](DIREZIONE-MUSICALE.md).
- Prova a quattro voci: melodia, accompagnamento, atmosfera sostenuta e pattern percussivi configurati. Esecuzione delle quattro parti confermata all'ascolto in Live da Marco; organico e comportamenti sono un banco di prova da affinare.

[Sessione multivoce](SESSIONE-MULTIVOCE.md) · [Configurazione](CONFIGURAZIONE.md) · [Passaggio di consegne](PASSAGGIO-CONSEGNE.md)

Le verifiche automatiche comprendono suite Python e JavaScript. Il dialogo ritmico è verificato
anche su 400 finestre consecutive con validazione delle frasi nel bridge;
la calibrazione all'ascolto in Live resta da eseguire. Sono verificate
le configurazioni manuale e guidata dalle macrosezioni GPX tramite
`--dry-run`. Comportamenti e comandi sono descritti in
[Dialogo ritmico](DIALOGO-MUSICALE.md) e [Tessitura sostenuta](TESSITURA.md).
I tre profili percussivi sono verificati anche su 100 finestre ciascuno,
con cambi di stile nella stessa sessione e validazione del bridge MIDI.
Il nuovo sviluppo melodico è verificato anche in 400 finestre multivoce
con cambi di stile, sezione, ruolo, durata del periodo e presenza.
La direzione automatica è verificata sui GPX Levanto–La Spezia,
Firenze–San Gimignano e San Nicola–San Severo, con esecuzione simulata
dell'intera timeline multivoce e controlli del bridge MIDI. La taratura
delle tavolozze e dei motivi richiede ancora ascolto in Live.

### 5. Analisi e macrosezioni del percorso
- Classificazione del profilo altimetrico per distanza con soglie e persistenza configurabili.
- Raggruppamento delle zone adiacenti in famiglie configurate, mantenendo le zone originali.
- Report HTML locale con quota, pendenza, zone, macrosezioni e misure di concordanza.

[Analisi del percorso](ANALISI-PERCORSO.md)

---

## Aspetti in sviluppo

- **Proposte di sviluppo**: [plancia grafica globale](proposte/PLANCIA.md) e [catalogo delle voci e ruoli musicali](proposte/RUOLI-MUSICALI.md), separati dalle funzionalità operative.
- **Quantizzazione metrica su Snake**: allineamento dei cambi di pattern a inizio battuta.
- **Calibrazione all'ascolto**: affinamento dei pesi armonici del generatore del basso durante le sessioni musicali.
- **Stili percussivi e relazioni**: resta da implementare la [combinazione delle influenze di stile](proposte/STILI-PERCUSSIVI.md#influenze-multiple-semantica-proposta-per-il-futuro), oltre alle ulteriori trasformazioni dei [contratti per le relazioni musicali](proposte/RELAZIONI-MUSICALI.md).

Per il dettaglio delle attività aperte, consultare [TODO.md](../TODO.md).

