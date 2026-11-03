# Evoluzione del discorso melodico

Stato: regole concordate e implementate nel modulo `music/melodic/`.
Il comportamento operativo è descritto in [Generazione melodica](../MELODIA.md).

## Decisioni adottate

- Identità affidata a cellule ricavate dal motivo, con relazioni intervallari
  riconoscibili anche dopo trasposizione nei gradi della scala.
- Sviluppo tramite ripresa, variazione ritmica, trasposizione, frammentazione
  ed estensione, senza successione obbligata di quattro fasi.
- Richiamo del materiale dopo trasformazioni marcate; alternanza delle
  cellule per evitare la ripetizione continua dello stesso frammento.
- Continuità con l'ultima altezza ammessa a suonare e adattamento al nuovo
  contesto armonico senza ripresentare automaticamente tutto il tema.
- Distinzione tra fine del periodo, respirazione e chiusura melodica.
  Chiusure esplicite sulla tonica distanziate di 2–4 periodi partecipanti.
- Controlli esistenti conservati, senza nuovi parametri pubblici.
- Stato preparato e accettato separatamente; finestre silenziate e tentativi
  falliti non producono chiusure accettate o falsi avanzamenti del conteggio.

## Direzione del percorso

Il collegamento concordato e implementato usa il profilo complessivo della
tappa per scegliere una tavolozza armonica e ricavare un motivo dalla forma
normalizzata. Le macrosezioni ne guidano l'evoluzione mantenendo classi di
altezza comuni. Sono disponibili override generali e per tappa.
Configurazione e algoritmo effettivi in
[Direzione musicale dal percorso](../DIREZIONE-MUSICALE.md).

Le metriche geografiche restano fuori dal generatore melodico e dal
Coordinator generico. Le variazioni dei controlli dal contesto locale sono
descritte nella [direzione adattiva](../DIREZIONE-MUSICALE.md#adattamento-dei-parametri).
Progressioni di accordi e cadenze armoniche complete restano da definire.
