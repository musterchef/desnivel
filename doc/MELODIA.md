# Generazione melodica

`music/melodic/generator.py` riceve un motivo in gradi, la tonica e la scala
della sezione, la finestra della timeline e le influenze ritmiche abilitate.
La direzione GPX può fornire il motivo e i contesti armonici, ma il generatore
non legge metriche geografiche.

## Motivo e sviluppo

Con `development = 0` il ruolo `melody` ripete il motivo, scandito da
`step_beats`. Con un valore positivo, `development.py` ricava cellule brevi
dai tratti monotoni del motivo e conserva i gradi e i loro intervalli. La
prima frase presenta una cellula; le successive possono riprenderla,
variare il suo ritmo, trasporla nei gradi della scala, frammentarla o
proseguirne il movimento. Dopo ripetizioni consecutive può passare alla
cellula successiva. Una fine ancora in movimento favorisce la prosecuzione.

La trasposizione è limitata al registro MIDI e a un'estensione di un'ottava
per lato rispetto al registro del motivo. Il raccordo considera l'ultima
altezza suonata e sceglie la collocazione più vicina realizzabile. Cambi di
tonica o scala riarmonizzano il materiale senza cancellare questa continuità.

`activity` regola la densità, le durate e le pause; `development` regola la
probabilità delle trasformazioni, inclusa la variazione ritmica della
cellula. `step_beats` fornisce la griglia di riferimento, non imposta un BPM.
Se la cellula non entra nella finestra, le sue suddivisioni vengono ridotte
quanto basta per mantenerla intera. Articolazione e velocity si applicano
alle note composte.

Il generatore non impone finali sulla tonica né una cadenza: riceve tonica e
scala, non una progressione di accordi. `phrase_windows` stabilisce la durata
del gesto dichiarato; il Coordinator lo rende disponibile alle relazioni
storiche solo quando il gesto è completo. La durata del gesto non programma
una chiusura melodica.

## Parametri

`degrees` è il motivo sorgente: una lista non vuota di gradi interi non
negativi. `0` è la tonica; gradi oltre l'ultimo della scala salgono
nell'ottava successiva.

| Parametro | Effetto musicale | Perché esiste |
|---|---|---|
| `octave` | Sposta il registro rispetto alla tonica di sezione. | Consente di collocare il motivo nell'estensione desiderata. |
| `step_beats` | Regola la spaziatura di riferimento e la griglia delle figure. | Permette di scegliere il passo ritmico senza fissare il BPM. |
| `articulation` | Regola quanto ciascuna nota occupa del proprio spazio. | Distingue note più legate o più separate senza cambiare la densità. |
| `velocity` | Imposta l'intensità MIDI di riferimento, con accenti locali. | Controlla la dinamica senza confonderla con il volume in dB. |
| `development` | Aumenta la probabilità e l'ampiezza delle trasformazioni del motivo; a zero resta letterale. | Dosare la variazione mantenendo riconoscibile il materiale sorgente. |
| `activity` | Regola la scelta di durate brevi o lunghe e la probabilità di pause. | Controllare la densità senza cambiare il motivo sorgente. |
| `phrase_windows` | Definisce quante finestre compongono il gesto dichiarato, da 2 a 8. | Allineare la durata dei gesti storici e la rivalutazione degli obiettivi adattivi. |
| `groove_follow` | Avvicina gli attacchi alla guida ritmica condivisa, da 0 a 1. | Collegare la frase al ritmo dell'ensemble senza copiarne le altezze. |

`seed` resta un'impostazione di configurazione, non un controllo del device:
serve a riprodurre le scelte generate. Nel modo letterale non modifica il
motivo. Le relazioni ritmiche storiche restano indipendenti da
`groove_follow`; entrambe le influenze agiscono dopo la composizione e
mantengono ordine e altezze delle note. Vedi
[Dialogo ritmico](DIALOGO-MUSICALE.md).

## Contesto e stato

Nel ruolo `melody`, la direzione adattiva può regolare `velocity` e
`activity` in base al contesto e alle altre voci; i cambiamenti ambientali
possono contribuire a `development`. Questi obiettivi sono applicati dal
Coordinator insieme ai parametri manuali e di sezione.

Il generatore prepara la frase e il nuovo stato in `VoicePlan`; lo stato
avanza solo dopo l'accettazione dell'intero piano multivoce. Una finestra
silenziata conserva l'ultima altezza e il materiale partecipante. Reset,
lacune nella timeline e cambi di ruolo rispettano le regole del Coordinator.
Richieste identiche ritentate non avanzano due volte lo stato.

`composition` espone l'operazione, la cellula sorgente, le trasposizioni,
gli attacchi iniziali e il gesto corrente. I test coprono riconoscibilità,
variazione, riproducibilità, continuità, scala, registro MIDI, finestre
silenziate, cambi di ruolo e accettazione transazionale.
