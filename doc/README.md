# Indice della documentazione

Guida alla documentazione di **Desnivel**, organizzata per aree tematiche.

---

## Panoramica e sistema

| Documento | Argomento |
|---|---|
| [Presentazione](../README.md) | Origine del progetto, viaggio da Torino a Castel del Monte e i tre livelli di lettura. |
| [Architettura](ARCHITETTURA.md) | Pipeline modulare, flusso dei dati, modelli musicali e organizzazione del codice. |
| [Sessione multivoce Python](SESSIONE-MULTIVOCE.md) | Comando unico, replay, generatori, dispositivi e stato globale. |
| [Guida pratica ai device](GUIDA-DEVICE.md) | Valori di partenza per ottenere risultati su melodia, basso, tessitura e drums. |
| [Configurazione](CONFIGURAZIONE.md) | Campi JSON, unità, limiti dei controlli, ruoli e precedenze. |
| [Direzione musicale dal percorso](DIREZIONE-MUSICALE.md) | Profilo della tappa, tavolozze armoniche, motivo automatico e override. |
| [Dialogo ritmico](DIALOGO-MUSICALE.md) | Guida percussiva, adesione delle voci, memoria dei gesti e influenze storiche operative. |
| [Stili percussivi](STILI-PERCUSSIVI.md) | Selettore, profili disponibili, mappatura delle parti e confronto in Live. |
| [Timeline musicale](TIMELINE.md) | Allocazione in beat, manager della posizione, report e ascolto nelle modalità lineare e allocata. |
| [Voci e contesto musicale](RUOLI-MUSICALI.md) | Strutture esistenti per voci, dipendenze, richieste di pianificazione e contesto di sezione. |
| [Stato del progetto](STATO.md) | Funzionalità operative verificate e sviluppi aperti. |
| [Passaggio di consegne](PASSAGGIO-CONSEGNE.md) | Stato della prova a quattro voci, architettura, configurazioni, comandi e lavoro aperto per riprendere il progetto. |
| [Comandi e setup](COMANDI.md) | Ambiente virtuale, porte di rete, streaming delle metriche, launcher e test suite. |
| [TODO](../TODO.md) | Roadmap delle attività di ricerca e sviluppo. |

---

## Dati del viaggio e integrazioni attive

| Documento | Argomento |
|---|---|
| [Dispositivo MIDI di voce](VOCE-M4L.md) | Device comune, collegamento Python, controlli e prova di esecuzione. |
| [Dati del viaggio](DATI-VIAGGIO.md) | Lettura FIT/GPX, calcolo delle metriche nei tratti osservati e formato OSC. |
| [Analisi del percorso](ANALISI-PERCORSO.md) | Zone del profilo altimetrico, macrosezioni configurabili, report visuale e misure di verifica. |
| [Sequencer Snake](SNAKE.md) | Banco di prova per la linea melodica: integrazione del sequencer Snake, bridge M4L e telemetria. |
| [Generazione melodica](MELODIA.md) | Motivo, sviluppo delle frasi, controlli e riproducibilità. |
| [Tessitura sostenuta](TESSITURA.md) | Sostegno monofonico indipendente o coordinato con una frase sorgente, switch e integrazione nella sessione. |
| [Generatore del basso](BASSO.md) | Banco di prova per l'accompagnamento: logica di contrappunto e dialogo con la melodia, controlli live e player. |
| [Tappe e percorsi modali](TAPPE-E-PRESET.md) | Caratterizzazione modale delle tappe (Levanto, Firenze, Sabaudia, Peschici) e ascolto. |

---

## Proposte di sviluppo

Materiale di progettazione separato dalla documentazione del sistema attuale.

- [Revisione dei controlli](proposte/REVISIONE-CONTROLLI.md): ridondanze verificate negli altri device e interventi proposti.

- [Ruoli musicali e organico](proposte/RUOLI-MUSICALI.md): impostazione condivisa, vocabolario proposto e decisioni aperte.
- [Catalogo e assegnazioni per sezione](proposte/CATALOGO-E-SEZIONI.md): bozza JSON di vocabolario, strumenti e organico manuale.
- [Plancia globale](proposte/PLANCIA.md): informazioni da mostrare e decisioni aperte sull’interfaccia.
- [Sezioni guidate dal viaggio](proposte/SEZIONI-GUIDATE-DAL-VIAGGIO.md): assetti delle macrosezioni operativi e variazioni interne ancora da definire.
- [Mappatura temporale](proposte/MAPPATURA-TEMPORALE.md): stato dell'integrazione della timeline e proposta di preavvisi per le transizioni musicali.
- [Evoluzione degli stili percussivi](proposte/STILI-PERCUSSIVI.md): design del catalogo e futura combinazione di influenze da 0 a 1.
- [Coordinamento ritmico](proposte/COORDINAMENTO-RITMICO.md): direzione architetturale e confini del primo blocco implementato.
- [Contratti per le relazioni musicali](proposte/RELAZIONI-MUSICALI.md): specifica generale, stato dell'implementazione e relazioni ancora da realizzare.
- [Evoluzione melodica](proposte/EVOLUZIONE-MELODICA.md): regole adottate per il fraseggio e decisioni ancora aperte sul collegamento al GPX.

---

## Materiali storici

I documenti e i codici relativi a versioni precedenti, pipeline prototipali e decisioni superate sono conservati in:
- [Archivio della documentazione](archivio/README.md)
- [Archivio del codice e dei prototipi](../archivio/README.md)
