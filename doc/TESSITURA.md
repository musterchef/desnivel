# Tessitura sostenuta

`music/texture/generator.py` implementa `TextureGenerator`, con ruolo
`sustained_texture`. Produce al massimo una nota per finestra musicale.
Nella sessione fornita è il generatore di `voice_03` (Atmosphere).

## Modalità

Lo switch **Segui sorgente** (`follow_source`) sceglie fra due comportamenti:

- **0 — indipendente:** sostiene il grado `degree` della scala della
  sezione, trasposto di `octave` rispetto alla tonica. Con `degree: 0`,
  root 57 e `octave: 1`, la nota è MIDI 69.
- **1 — coordinato:** legge la frase di una sola dipendenza musicale e
  sceglie una classe di altezza presente nella sorgente. Per ogni classe
  somma durata × velocity delle note. Il punteggio dei candidati è questo
  peso normalizzato al massimo, meno la distanza dal riferimento di
  continuità divisa per 12. A parità prevalgono la nota più vicina e poi
  quella più bassa.

Il registro coordinato è l'ottava che parte dalla nota del grado
configurato e termina undici semitoni sopra, entro MIDI 127. Il riferimento
di continuità è l'ultima nota generata nella finestra precedente, se contigua e non
silenziosa; altrimenti è la nota del grado configurato. Il registro viene
ricalcolato da tonica, scala, grado e ottava a ogni richiesta. Se nessuna
classe sorgente è rappresentabile nel registro, la generazione segnala un errore.

In modalità coordinata una sorgente assente o una frase vuota producono
silenzio. In modalità indipendente la sorgente non determina il risultato.
Entrambe usano la velocity configurata e sostengono la nota dall'inizio
alla fine della finestra. A ogni finestra successiva avviene un nuovo
attacco, anche se l'altezza rimane uguale.

## Coordinamento

`organico.json` dichiara `voice_01` come dipendenza facoltativa di
`voice_03`. Il Coordinator genera prima la sorgente, se attiva, e passa la
sua frase effettiva alla tessitura. Questo comprende i silenzi determinati
dalla presenza. La tessitura segue a sua volta organico e presenza propri.
Gli identificativi delle parti sono configurazione, non regole del generatore.

Stop, restart e discontinuità del trasporto azzerano la memoria musicale
tramite il reset del runtime. Ripianificare lo stesso beat iniziale
conserva il riferimento di continuità. Il cambio di sezione applica il
nuovo contesto alle frasi ancora da pianificare.

Il ruolo `sustained_texture` del generatore `motif` delega allo stesso modulo
la modalità indipendente dal primo grado del motivo. I controlli di
sviluppo melodico restano responsabilità di `music/melodic/`.

## Prova nel dispositivo

1. Avviare la [sessione multivoce](SESSIONE-MULTIVOCE.md) con il device
   aggiornato e collegare Atmosphere come `voice_03`, Receive `9103`.
2. Nel menu **Parametro**, scegliere **Segui sorgente**. Switch spento:
   sostegno di sezione; acceso: sostegno dalla melodia della stessa finestra.
3. Confrontare le modalità mantenendo lo stesso strumento e gli stessi
   valori di `octave` e `velocity`.

La scelta agisce sulle prossime frasi, persiste fra sezioni ed è inclusa
nei preset salvati dal device. Non sono forniti preset base per questa
voce. Il dettaglio delle decisioni espone modalità, sorgente,
registro, altezza scelta ed eventuale motivo del silenzio in
`decisions.coordinator.voices.voice_03.composition`.

Valori predefiniti, intervalli e campi JSON sono nel
[riferimento della configurazione](CONFIGURAZIONE.md#parametri-del-generatore-sustained_texture).
