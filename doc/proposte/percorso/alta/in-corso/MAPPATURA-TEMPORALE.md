# Mappatura temporale delle macrosezioni

Stato: specifica richiesta il 19 ottobre 2026. Allocatore, oggetto Timeline,
manager della posizione, anteprima nel report e modalità di esecuzione
`ensemble --timing allocated` implementati e descritti in
[Timeline musicale](../../../../TIMELINE.md). Le risposte musicali ai preavvisi
restano da implementare. La configurazione operativa usa una scala comune
di 12 beat/km per la durata totale; il totale esplicito resta un’opzione
dell’allocatore.

## Obiettivo e confini

Conservare il replay lineare con `--speed` e aggiungere una modalità che
assegni a ogni macrosezione un numero minimo di finestre musicali. Il tempo
residuo dipende dalla distanza della macrosezione elevata a un esponente
configurabile, predefinito a 0,5. L'analisi delle fasce, il raggruppamento e
gli assetti musicali esistenti rimangono componenti separati.

L'unità concordata è il beat musicale. Il BPM determina la durata reale
dell'ascolto e non entra nell'allocazione. Non è richiesto un budget in
secondi o una conversione dipendente dal BPM.

## Interfaccia pubblica disponibile

Un modulo `src/desnivel/music/timeline.py` con una funzione pura:

```python
def allocate_timeline(
    distances_m: Sequence[float],
    *,
    target_beats: float,
    window_beats: float,
    min_windows: int = 2,
    distance_exponent: float = 0.5,
) -> Timeline:
    ...
```

Gli ingressi sono distanze positive e finite nell'ordine delle macrosezioni.
La funzione non conosce nomi delle famiglie, strumenti, GPX, clock o rete.
`window_beats` è quello già configurato per la sessione, senza duplicarlo.
`min_windows` è un intero positivo. Durata richiesta e finestra devono essere
positive e finite. L'esponente deve essere finito e non negativo: zero
distribuisce il residuo in parti uguali, 0,5 attenua le differenze di
distanza, uno mantiene le proporzioni metriche del residuo. Valori superiori
a uno accentuano le differenze, invece di comprimerle.

Due semplici strutture di risultato:

- `Timeline`: beat richiesti ed effettivi, ampiezza della finestra, elenco
  degli intervalli e avvisi strutturati sull'adattamento del budget.
- `TimelineSpan`: indice della macrosezione sorgente, finestra iniziale e
  numero di finestre assegnate. Inizio e fine in beat sono ricavabili da
  questi interi e da `window_beats`.

Gli intervalli sono consecutivi, senza buchi, in ordine di percorso. Il
confine finale è escluso dalla sezione uscente e incluso nella successiva.
Il risultato conserva l'associazione alle macrosezioni originali senza
riscriverne confini metrici o misure.

`TimelineManager` gestisce il cursore di finestra e offre avanzamento,
posizionamento esplicito, reset e snapshot. Non gestisce clock o dispositivi.
La configurazione confermata per la prima anteprima è 480 beat, finestre da
4 beat, minimo di 2 finestre ed esponente 0,5. L'anteprima è integrata nel
report esistente e nel runtime con `--timing allocated`.

## Allocazione e quantizzazione

1. Convertire il budget in finestre: `ceil(target_beats / window_beats)`.
   Il totale quantizzato non è inferiore a quello richiesto.
2. Calcolare il minimo complessivo: numero di macrosezioni × `min_windows`.
3. Usare il maggiore fra budget quantizzato e minimo complessivo. Se i
   minimi richiedono un'estensione, restituire un avviso con durata richiesta,
   durata effettiva e motivo; il chiamante lo mostra nel log e nello stato.
4. Riservare `min_windows` a ogni macrosezione.
5. Distribuire le finestre residue secondo i pesi `metri ** esponente`.
   Normalizzare i pesi evitando overflow per grandi distanze o esponenti.
6. Assegnare le parti intere delle quote residue; distribuire le finestre
   rimanenti ai resti frazionari maggiori. A parità di resto prevale l'ordine
   del percorso. La somma coincide esattamente con il budget effettivo.

L'arrotondamento è eseguito sull'allocazione complessiva, non separatamente
su ogni durata: si preservano sia il minimo sia la somma delle finestre.
L'eventuale aumento per quantizzazione viene riportato nel risultato,
distinto dall'auto-estensione necessaria per i minimi.

Esempio: distanze 9.000, 1.000 e 4.000 m; 240 beat richiesti; finestre da
4 beat; minimo di 2 finestre; esponente 0,5. I pesi sono in rapporto 3:1:2.
Delle 60 finestre totali, 6 sono riservate ai minimi e 54 distribuite coi
pesi. Il risultato è 29, 11 e 20 finestre, cioè 116, 44 e 80 beat.
A 120 BPM corrispondono a 58, 22 e 40 secondi, per due minuti complessivi.

## Aggancio al runtime implementato

- `cli/trip_direction.py` continua a preparare macrosezioni e assetti. Le
  distanze passate all'allocatore sono differenze dei confini metrici delle
  macrosezioni, non le durate originali del GPX.
- La sessione sceglie esplicitamente fra modalità lineare e allocata. Nella
  seconda, la durata musicale sostituisce `--speed` come criterio temporale;
  una configurazione ambigua deve produrre un errore, senza moltiplicare i
  due meccanismi. I parametri temporali trovano posto nella configurazione
  di sessione esistente, senza un nuovo JSON per ogni modalità.
- `EnsembleRuntime` consuma le finestre della timeline in sequenza. La
  selezione musicale deve seguire il piano temporale, senza campionare la
  posizione GPX e saltare le macrosezioni brevi.
- Il Director esistente conserva contesto e assegnazioni. Si usa la
  selezione tramite la progressione iniziale della macrosezione pianificata,
  riutilizzando la gestione degli override manuali.
- Il Coordinator continua a generare una frase per voce per la finestra
  richiesta; l'allocazione non cambia i suoi criteri di dipendenza.
- Posizione musicale e posizione del percorso rimangono distinte. La vista
  globale mostra il budget richiesto/effettivo, la macrosezione del piano e
  l'avanzamento nel percorso interpolato all'interno dell'intervallo metrico.
  Quest'ultimo descrive un viaggio rimappato, non il tempo GPX originale.
- Stop e dispositivi mancanti sospendono l'avanzamento logico. Seek e loop
  di Live riagganciano la pianificazione al trasporto preservando il punto
  logico raggiunto; non devono reinterpretare il beat assoluto come posizione
  nel viaggio o consumare sezioni senza pianificarle.
- La chiusura della sessione segue la fine dell'ultima finestra eseguita,
  non l'invio anticipato dell'ultimo piano.

## Confini, anticipo e transizioni

I cambi di assetto cadono sui confini delle finestre, allineati alla griglia
del trasporto. Una finestra non è necessariamente una misura: oggi il
sistema non dichiara il metro. Per esempio, quattro semiminime costituiscono
una misura solo assumendo 4/4.

`lead_beats` resta l'anticipo di invio al player. Non implica una chiusura
armonica né una dissolvenza. Le `Phrase` esistenti terminano entro la loro
finestra; durante il cambio ordinario non si deve inviare un Panic che tagli
la frase già iniziata. Stop e discontinuità mantengono la gestione esplicita
di cancellazione prevista dalla sessione.

Per prevedere una chiusura musicale si propone un preavviso generico nelle
richieste di composizione: finestre rimanenti e prossimo contesto musicale.
L'allocatore rende noti in anticipo i confini; ogni generatore deve poi
implementare esplicitamente la propria risposta al preavviso. Una dissolvenza
timbrica richiede inoltre controlli e adattamento alla destinazione. Questi
comportamenti non sono attualmente disponibili e non vanno dichiarati
ottenuti dal solo anticipo di pianificazione.

## Piano di test essenziale

Allocatore:

1. Somma esatta delle finestre, minimi rispettati e ordine preservato.
2. Budget insufficiente: estensione al minimo e avviso verificabile.
3. Budget non divisibile per la finestra: quantizzazione e scostamento
   espliciti; nessuna perdita o finestra residua non assegnata.
4. Esponenti zero, 0,5 e uno; distanze uguali; una sola macrosezione;
   determinismo dell'assegnazione dei resti.
5. Rifiuto di lista vuota, distanze non positive/non finite, minimi non
   interi o non positivi e parametri temporali non validi.
6. Pesi numericamente stabili e confini corretti su dati molto sbilanciati.

Integrazione:

1. Una macrosezione brevissima riceve tutte le finestre minime, anche quando
   il replay lineare a `speed 200` la attraverserebbe fra due pianificazioni.
2. Cambi di contesto e assegnazioni soltanto ai confini pianificati; nessuna
   macrosezione omessa, duplicata o riordinata.
3. Stop, ripartenza, loop/seek e perdita dei dispositivi conservano il punto
   logico e riagganciano correttamente i beat del trasporto.
4. Le note della finestra uscente possono terminare e l'ultima finestra
   viene eseguita prima dell'arresto finale.
5. Modalità lineare e override manuali conservano il comportamento attuale;
   configurazione e avvisi risultano visibili in dry-run e nello stato.
6. Gli algoritmi di analisi/raggruppamento e i loro risultati restano invariati.

L'implementazione del preavviso e delle risposte musicali richiede test
dedicati per i generatori coinvolti. Un test di sola allocazione non può
verificare una chiusura armonica o il risultato audio di una dissolvenza.
