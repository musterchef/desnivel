# Indice della documentazione

Guida alla documentazione di **Desnivel**, organizzata per aree tematiche.

---

## Panoramica e sistema

| Documento | Argomento |
|---|---|
| [Presentazione](../README.md) | Scopo, flusso del sistema e accesso alle guide. |
| [Architettura](ARCHITETTURA.md) | Pipeline modulare, flusso dei dati, modelli musicali e organizzazione del codice. |
| [Sessione multivoce Python](SESSIONE-MULTIVOCE.md) | Avvio, replay, dispositivi, dashboard e registrazione in Live. |
| [Guida pratica ai device](GUIDA-DEVICE.md) | Valori di partenza per ottenere risultati su melodia, basso, tessitura e drums. |
| [Configurazione](CONFIGURAZIONE.md) | Campi JSON, unità, limiti dei controlli, ruoli e precedenze. |
| [Direzione musicale dal percorso](DIREZIONE-MUSICALE.md) | Profilo della tappa, tavolozze armoniche, motivo automatico e override. |
| [Dialogo ritmico](DIALOGO-MUSICALE.md) | Guida percussiva, adesione delle voci, memoria dei gesti e influenze storiche operative. |
| [Stili percussivi](STILI-PERCUSSIVI.md) | Selettore, profili disponibili, mappatura delle parti e confronto in Live. |
| [Timeline musicale](TIMELINE.md) | Allocazione in beat, manager della posizione, report e ascolto nelle modalità lineare e allocata. |
| [Voci e contesto musicale](RUOLI-MUSICALI.md) | Strutture esistenti per voci, dipendenze, richieste di pianificazione e contesto di sezione. |
| [Stato del progetto](STATO.md) | Funzionalità operative verificate e sviluppi aperti. |
| [Comandi e setup](COMANDI.md) | Ambiente virtuale, porte di rete, streaming delle metriche, launcher e test suite. |
| [TODO](../TODO.md) | Roadmap delle attività di ricerca e sviluppo. |

---

## Dati del viaggio e integrazioni attive

| Documento | Argomento |
|---|---|
| [Dispositivo MIDI di voce](VOCE-M4L.md) | Device comune, collegamento Python, controlli e prova di esecuzione. |
| [Dati del viaggio](DATI-VIAGGIO.md) | Lettura FIT/GPX, calcolo delle metriche nei tratti osservati e formato OSC. |
| [Contesto ambientale](CONTESTO-AMBIENTALE.md) | Sorgenti generiche, meteo storico, acquisizione del fondo stradale e confronto musicale A/B. |
| [Analisi del percorso](ANALISI-PERCORSO.md) | Zone del profilo altimetrico, macrosezioni configurabili, report visuale e misure di verifica. |
| [Sequencer Snake](SNAKE.md) | Controllo multiruolo autonomo/coordinato, banco Length, bridge e telemetria. |
| [Generazione melodica](MELODIA.md) | Motivo, sviluppo delle frasi, controlli e riproducibilità. |
| [Tessitura sostenuta](TESSITURA.md) | Sostegno monofonico indipendente o coordinato con una frase sorgente, switch e integrazione nella sessione. |
| [Generatore del basso](BASSO.md) | Banco di prova per l'accompagnamento: logica di contrappunto e dialogo con la melodia, controlli live e player. |
| [Tappe e percorsi modali](TAPPE-E-PRESET.md) | Caratterizzazione modale delle tappe (Levanto, Firenze, Sabaudia, Peschici) e ascolto. |

---

## Proposte di sviluppo

Materiale di progettazione separato dalla documentazione del sistema attuale.

- [Revisione dei controlli](proposte/REVISIONE-CONTROLLI.md): consolidamenti applicati a preset e controlli; ulteriori interventi proposti.
- [Direzione adattiva](proposte/DIREZIONE-ADATTIVA.md): politiche e transizioni implementate; compositore percussivo a regole ancora proposto.
- [Ruoli musicali e organico](proposte/RUOLI-MUSICALI.md): impostazione condivisa, vocabolario proposto e decisioni aperte.
- [Catalogo e assegnazioni per sezione](proposte/CATALOGO-E-SEZIONI.md): bozza JSON di vocabolario, strumenti e organico manuale.
- [Plancia globale](proposte/PLANCIA.md): requisiti, dashboard disponibile e decisioni ancora aperte.
- [Sezioni guidate dal viaggio](proposte/SEZIONI-GUIDATE-DAL-VIAGGIO.md): analisi e assetti implementati; ulteriori eventi e gestione degli intervalli incerti proposti.
- [Mappatura temporale](proposte/MAPPATURA-TEMPORALE.md): stato dell'integrazione della timeline e proposta di preavvisi per le transizioni musicali.
- [Contratto delle percussioni](proposte/STILI-PERCUSSIVI.md): centralizzazione del materiale, generazione a regole, dialogo e influenze stilistiche.
- [Coordinamento ritmico](proposte/COORDINAMENTO-RITMICO.md): direzione architetturale e confini del primo blocco implementato.
- [Contratti per le relazioni musicali](proposte/RELAZIONI-MUSICALI.md): specifica generale, stato dell'implementazione e relazioni ancora da realizzare.
- [Evoluzione melodica](proposte/EVOLUZIONE-MELODICA.md): fraseggio e collegamento al percorso implementati; ulteriori sviluppi armonici aperti.
- [Voce Snake](proposte/VOCE-SNAKE.md): controllo multiruolo e lettura come sorgente disponibili; accompagnamento nelle pause e aggiornamenti legati alla fase ancora proposti.

---

## Materiali storici

I documenti e i codici relativi a versioni precedenti, pipeline prototipali e decisioni superate sono conservati in:
- [Archivio della documentazione](archivio/README.md)
- [Archivio del codice e dei prototipi](../archivio/README.md)
