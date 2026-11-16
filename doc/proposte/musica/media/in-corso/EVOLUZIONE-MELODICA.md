# Evoluzione del discorso melodico

Stato: impianto semplificato implementato. Il comportamento operativo è
descritto in [Generazione melodica](../../../../MELODIA.md).

## Comportamento

- Il motivo in gradi è il materiale sorgente; le cellule ne mantengono il
  profilo intervallare.
- Lo sviluppo può riprendere, trasporre o frammentare una cellula, variare
  il ritmo o proseguirne il movimento. Dopo ripetizioni consecutive può
  passare a un'altra cellula.
- Il raccordo considera l'ultima altezza e la scala della sezione.
- `activity` regola densità e pause; `development` regola la probabilità
  delle trasformazioni.
- `phrase_windows` definisce la durata del gesto condiviso con il sistema
  delle relazioni storiche; non programma una chiusura melodica.
- La preparazione e l'accettazione dello stato restano separate, così
  finestre silenziate o piani falliti non avanzano il generatore.

Il generatore non riceve progressioni di accordi. La direzione dal percorso
può fornire un motivo e i contesti di sezione; i dettagli sono descritti in
[Direzione musicale dal percorso](../../../../DIREZIONE-MUSICALE.md).
