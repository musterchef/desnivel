# Regole di lavoro

## Repository e commit
- Commit solo su richiesta esplicita, dopo aver esaminato il diff.
- Commit atomici con soli file necessari; escludere script usa e getta, log, dump e output temporanei.
- Titoli nominali con iniziale minuscola e oggetto esplicito (es. «correzione di…»).

## Scrittura del codice e architettura
- Codice semplice, modulare e leggibile, senza astrazioni premature, workaround o fallback silenziosi. Correggere le cause dei problemi.
- Non introdurre ridondanze tra parametri, configurazioni, preset o logiche. Ogni controllo deve avere una responsabilità distinta e un effetto verificabile; prima di aggiungerlo, verificare ciò che esiste e riutilizzarlo o consolidarlo quando copre lo stesso scopo. I preset devono rappresentare combinazioni utili di controlli, non duplicare singoli valori già esposti. Conservare le distinzioni che hanno responsabilità musicali effettivamente diverse.
- Mostrare in minuscolo i nomi e le opzioni dei parametri nei device, compreso l'indicatore auto/manual. La formattazione delle etichette non deve cambiare gli identificativi del protocollo o dei preset.
- Separare le responsabilità:
  - `src/desnivel/trip/`: lettura GPX e metriche neutre.
  - `src/desnivel/music/`: composizione multivoce agnostica, con una cartella per voce.
  - `src/desnivel/adapters/`: traduzione verso destinazioni e device specifici.
  - `src/desnivel/sinks/`: trasporto (OSC, file di cattura).
  - `src/desnivel/cli/`: entry point per comandi e sessioni.
  - `m4l/`, `tools/`, `comandi/`: rispettivamente sorgenti Max, builder e launcher macOS.
- Modelli musicali (`Pattern`, `Phrase`) indipendenti dai dispositivi.
- Direzione e coordinamento generici dipendono solo da contesti musicali, voci, generatori e relative dipendenze. Nomi, controlli, stato e regole di strumenti o dispositivi specifici appartengono ai moduli delle voci o agli adattatori, mai alle classi generiche né ai loro import.

## Principi di sistema e banchi di prova
- Desnivel è un motore di musica generativa multivoce agnostico basato su GPX. Gli strumenti e le prove in Ableton Live (es. Snake e generatore del basso) sono banchi di prova per l'ascolto e il dialogo polifonico; non definiscono il sistema.

## Documentazione
- Scrivere nella lingua richiesta, in modo chiaro, conciso, oggettivo e comprensibile senza conversazioni precedenti.
- Nella documentazione del sistema documentare soltanto componenti, responsabilità, interfacce, configurazioni e comportamenti esistenti nel progetto. Prima di scrivere, verificarne il riscontro nel codice o nelle configurazioni e il collegamento effettivo al sistema.
- Conservare proposte, funzionalità future, contratti non implementati e decisioni aperte in `doc/proposte/`, indicando chiaramente il loro stato e separandoli dalla documentazione del sistema esistente. Non eliminarli durante le revisioni. Un'architettura approvata non equivale a un'implementazione esistente.
- Distinguere ciò che il sistema calcola effettivamente da ciò che sarebbe teoricamente ricavabile: non documentare quest'ultimo come capacità disponibile. Se mancano informazioni essenziali, chiedere prima di scrivere.
- Evitare cronologie di soluzioni scartate, formulazioni difensive, ridondanze e gergo stereotipato. Nelle revisioni correggere solo ciò che serve, preservando i dettagli utili.
- Preservare i nomi dei file; archiviare quelli superati in `doc/archivio/` aggiornando i riferimenti.

## Modalità operativa
- Applicare l'intento e il principio generale della richiesta senza estenderne lo scopo o riprogettare il sistema.
- Fare modifiche concrete e verificabili; riportare sinteticamente modifiche ed esito dei controlli.
