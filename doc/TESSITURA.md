# Armonia di sezione

`music/texture/generator.py` implementa `TextureGenerator`, con ruolo
`harmony`. Nella sessione fornita è il generatore di `voice_03` (Atmosphere).
La realizzazione predefinita è un accordo diatonico costruito a partire dal
grado configurato: fondamentale, terza e quinta, impilate secondo la scala
della sezione.

## Realizzazioni

Il controllo `realization` seleziona:

- **Accordi di sezione** (`chord`): genera simultaneamente i gradi 1, 3 e 5
  a partire da `degree`; le note durano per tutta la finestra.
- **Nota ripetuta** (`repeated_note`): ripete il grado di riferimento a
  intervalli di `step_beats`, con durata regolata da `articulation`.

`octave` trasporta il grado di riferimento rispetto alla tonica; `velocity`
si applica alle note generate. Con `degree: 0`, root 57, scala maggiore e
`octave: 1`, l'accordo è MIDI 69, 73 e 76. La realizzazione ripetuta usa
gli stessi grado e registro, ma genera una sequenza monofonica.

## Relazioni con una sorgente

Gli switch **Segui sorgente** (`follow_source`) e **Supporta sorgente**
(`support_source`) sono mutuamente esclusivi e richiedono al massimo una
dipendenza musicale.

- Con `follow_source`, la realizzazione ad accordi sceglie la classe di
  altezza più presente nella frase sorgente, la associa al grado della scala
  più vicino e costruisce l'accordo da quel grado. La realizzazione a nota
  ripetuta sceglie invece una nota della classe più presente nel registro
  configurato, privilegiando la continuità con la finestra precedente.
- Con `support_source`, l'accordo o la nota vengono trasposti per ottave
  finché l'intera realizzazione è fuori dal registro della sorgente nella
  finestra corrente. Se nessuna trasposizione è disponibile, la finestra
  è silenziosa (`register_contested`). La velocity si riduce in proporzione
  al rapporto di occupazione della sorgente.

Una sorgente assente silenzia entrambe le modalità coordinate. Una sorgente
presente ma con frase vuota silenzia `follow_source`; `support_source`
mantiene la realizzazione di sezione. In modalità indipendente la sorgente
non determina il risultato.

Stop, restart e discontinuità del trasporto azzerano la memoria musicale
tramite il reset del runtime. Ripianificare lo stesso beat iniziale conserva
il riferimento di continuità. Il cambio di sezione applica il nuovo contesto
alle frasi ancora da pianificare.

Il ruolo `harmony` del generatore `motif` delega allo stesso modulo la
realizzazione a nota ripetuta sul primo grado del motivo. I controlli di
sviluppo melodico restano responsabilità di `music/melodic/`.

## Prova nel dispositivo

1. Avviare la [sessione multivoce](SESSIONE-MULTIVOCE.md) con il device
   aggiornato e collegare Atmosphere come `voice_03`, Receive `9103`.
2. Nel menu **Parametro**, scegliere `realization` per confrontare accordi
   e nota ripetuta. Regolare `step_beats` e `articulation` per la seconda.
3. Provare **Segui sorgente** o **Supporta sorgente** con una dipendenza
   configurata, mantenendo lo stesso strumento e gli stessi valori di
   `octave` e `velocity`.

Le scelte agiscono sulle prossime frasi, persistono fra sezioni e sono
incluse nei preset salvati dal device. Il dettaglio delle decisioni espone
realizzazione, modalità, sorgente, registro, altezze generate ed eventuale
motivo del silenzio in `decisions.coordinator.voices.voice_03.composition`.

Valori predefiniti, intervalli e campi JSON sono nel
[riferimento della configurazione](CONFIGURAZIONE.md#parametri-del-generatore-sustained_texture).
