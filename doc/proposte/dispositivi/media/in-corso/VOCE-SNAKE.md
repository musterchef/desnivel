# Snake come voce configurabile

Stato: controllo multiruolo e lettura come sorgente del Coordinator
implementati. La previsione comprende banchi, fasi e note MIDI sostenute;
i cambi automatici dei banchi attendono le finestre già accettate.
Comportamento attuale in [Snake](../../../../SNAKE.md).

## Comportamento richiesto

Snake conserva la generazione MIDI tramite i propri banchi e percorsi.
Python, motore di Desnivel, ne controlla il materiale e il comportamento.
Ogni istanza deve essere identificata individualmente; il collegamento
non deve dipendere dal primo Snake trovato nel Live Set.

L'utente sceglie separatamente:

- **Ruolo musicale:** parte principale, accompagnamento o sottofondo;
  comportamenti iniziali definiti in [Snake](../../../../SNAKE.md#componente-multiruolo).
- **Relazione con l'insieme:** autonomo, guidato dal viaggio e dal proprio
  materiale; coordinato, con una sorgente musicale scelta esplicitamente.

La modalità autonoma non implica il ruolo principale. L'assegnazione del
ruolo non deve impedire di usare più istanze di Snake contemporaneamente.
Note, gate, velocity e durate devono conservare responsabilità distinte.
Il banco Length esistente gestisce le durate; non serve un secondo sistema
per la stessa funzione.

## Componenti da riutilizzare

| Componente esistente | Funzione |
|---|---|
| `tools/build_snake_length.py` | Banco delle durate e gestione dei note-off |
| `tools/build_live_bass.py` | Variante con esportazione dello stato |
| `m4l/desnivel_snake_params.js` | Risoluzione e controllo dei parametri Live |
| `m4l/desnivel_snake_state.js` | Lettura di note effettive, banchi e fasi |
| `adapters/snake_sequence.py` | Previsione della frase da stato, BPM, durate e percorsi |
| Ruoli, dipendenze e controlli della sessione | Assegnazione musicale, relazione con altre voci e intervento manuale |

## Vincoli dell'integrazione

- Le classi generiche del motore non devono conoscere Snake o i nomi
  dei suoi parametri. Traduzione dei banchi e protocollo restano negli adattatori.
- Il collegamento in uscita usa la previsione ricavata dallo stato di Snake,
  distinta dal materiale richiesto da Python e dalla storia musicale accettata.
- L'attuale previsione supporta swing zero, Shift 1, direzioni avanti e
  indietro e le velocità elencate in [Snake](../../../../SNAKE.md). Le condizioni
  non prevedibili devono essere segnalate, senza inventare note sorgente.
- Il componente deve distinguere il materiale impostato, la sequenza
  prevista e le modifiche manuali. La previsione non è una misura audio.

## Ulteriori integrazioni proposte

Resta da implementare il ruolo `accompaniment`: sostegno contenuto durante
la melodia sorgente e risposte brevi nelle pause, con conclusione prima
del suo rientro. Richiede la programmazione delle revisioni rispetto alla
fase effettiva di Snake; la lettura delle previsioni non equivale ancora a
questa funzione di risposta. Restano aperti anche l'invalidazione e il
ricalcolo dei piani già accettati dopo interventi manuali sui banchi.

## Aggiunta degli strumenti dalla sessione

La preparazione guidata di Snake è implementata: **N** apre il servizio e
mostra le istruzioni; l'utente crea la traccia in Live. Il collegamento viene
ritentato ogni dieci secondi oppure su **Invio**. La conferma richiede Snake
con Length, controllo e strumento; **Esc** annulla. Il launcher resta unico
e l'avvio base mantiene synth, basso, atmosfera e drums.

L'aggiunta guidata di altri strumenti resta un'estensione futura. Il numero
di quattro voci appartiene alla configurazione di prova, non a un limite
del motore. Questa fase non implementa un catalogo di strumenti o il
caricamento automatico di tracce da file.
