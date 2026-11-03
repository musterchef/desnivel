# Snake come voce configurabile

Stato: controllo multiruolo implementato come componente della sessione.
La modalità coordinata legge una voce del piano corrente; il collegamento
in uscita da Snake verso il Coordinator rimane proposto. Il banco Length, il controllo dei parametri e la previsione
della sequenza esistono già: [Snake](../SNAKE.md).

## Comportamento richiesto

Snake conserva la generazione MIDI tramite i propri banchi e percorsi.
Python, motore di Desnivel, ne controlla il materiale e il comportamento.
Ogni istanza deve essere identificata individualmente; il collegamento
non deve dipendere dal primo Snake trovato nel Live Set.

L'utente sceglie separatamente:

- **Ruolo musicale:** parte principale, accompagnamento o sottofondo;
  comportamenti iniziali definiti in [Snake](../SNAKE.md#componente-multiruolo).
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
- Per un futuro collegamento in uscita, Snake dovrà partecipare al coordinamento attraverso una rappresentazione
  della sequenza che produrrà effettivamente. Una frase composta per un
  altro esecutore non è automaticamente equivalente all'uscita di Snake.
- L'attuale previsione supporta swing zero, Shift 1, direzioni avanti e
  indietro e le velocità elencate in [Snake](../SNAKE.md). Le condizioni
  non prevedibili devono essere segnalate, senza inventare note sorgente.
- Il componente deve distinguere il materiale impostato, la sequenza
  prevista e le modifiche manuali. La previsione non è una misura audio.

## Ulteriori integrazioni proposte

Il componente adatta banchi, percorsi e suddivisione al viaggio. Restano da
definire l’applicazione delle modifiche alla fase esatta del sequencer e
l'inserimento della sequenza prevista fra le sorgenti del Coordinator.
Il ruolo di accompagnamento attuale offre sostegno armonico con gate più
radi quando la sorgente è fitta; risposte con allineamento temporale esatto
richiedono queste ulteriori integrazioni.

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
