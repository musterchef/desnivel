# Generazione melodica da motivo

`music/melodic/generator.py` produce frasi dalla tonica e dalla scala della
sezione e da un motivo configurato in gradi. `octave` determina il registro
di riferimento. Nel ruolo `melody`, `development > 0` attiva lo sviluppo;
con `development = 0` il motivo viene ripetuto letteralmente su passi regolari.

## Cellule e continuità

`music/melodic/development.py` ricava cellule di 2–4 note dai tratti monotoni
del motivo. Se non ci sono tratti di almeno tre note usa frammenti contigui;
un motivo di una nota resta una cellula valida. Dal motivo della sessione
`[0, 2, 4, 1, 3, 2, 1, 0]` ricava `[0, 2, 4]` e `[3, 2, 1, 0]`.

Ogni finestra inizia con una cellula intera, eventualmente trasposta nei
gradi della scala. Le relazioni intervallari in gradi restano riconoscibili.
Il seguito può riprenderla, usarne un frammento o estenderne la direzione.

| Operazione | Comportamento |
|---|---|
| Presentazione | Espone la prima cellula alla prima entrata e dopo una chiusura |
| Ripresa | Riusa la cellula mantenendo il suo profilo |
| Variazione ritmica | Cambia le durate della cellula, conservandone le altezze |
| Trasposizione | Sposta la cellula nei gradi della scala, mantenendo il ritmo di riferimento |
| Frammentazione | Espone la cellula e usa un suo frammento nel seguito |
| Estensione e prosecuzione | Espone la cellula e ne continua il movimento per grado |
| Richiamo | Ripristina la cellula senza trasposizione dopo una trasformazione marcata |

Le operazioni non formano una successione fissa. Una fine ancora in movimento
favorisce la prosecuzione. Dopo due finestre con la stessa cellula viene
favorito il passaggio alla successiva; con una sola cellula si usa l'estensione.
Dopo trasposizione, frammentazione o estensione con `development >= 0.6`,
la finestra successiva richiama materiale non trasposto.

La collocazione confronta l'inizio della cellula con l'ultima altezza
ammessa a suonare. Può scegliere l'ottava di riferimento oppure una delle
due adiacenti, rispettando MIDI 0…127. Le trasposizioni non realizzabili
sono escluse prima della scelta dell'operazione. Il registro disponibile
è l'estensione del motivo ampliata di un'ottava per lato, entro MIDI 0…127.
Anche le estensioni del seguito rispettano questi limiti. Gli intervalli
del motivo originale restano ammessi, inclusi eventuali salti ampi configurati.

## Ritmo e conclusioni

`step_beats` è il riferimento per le durate. Il ritmo di base della cellula
è riproducibile da seed, cellula e attività; la variazione ritmica può
cambiarlo. Se la cellula non entra nello spazio disponibile, le sue durate
vengono ridotte proporzionalmente. Il seguito usa durate di mezzo, uno,
uno e mezzo o due passi, con pause dipendenti da `activity` e `development`.

Articolazione e velocity si applicano alle note composte; l'inizio è
accentato e gli attacchi fra beat interi sono attenuati nel seguito.
La modellazione da guida ritmica e relazioni storiche avviene dopo questa
composizione, conservando ordine e altezze delle note. Vedi
[Dialogo ritmico](DIALOGO-MUSICALE.md).

Un periodo dura `phrase_windows × length_beats`. Il suo termine non impone
una conclusione. Una chiusura esplicita sulla tonica diventa possibile nel
secondo periodo partecipante; viene favorita quando la frase non richiede
prosecuzione. Dopo tre periodi completati senza chiusura, la prima finestra
successiva ammessa a suonare conclude: la distanza fra chiusure è quindi
2–4 periodi partecipanti, con durata del periodo invariata.

Un periodo conta se almeno una sua finestra è ammessa a suonare. I periodi
interamente silenziati non avanzano il conteggio; una finestra silenziata
non può realizzare una chiusura. La tonica viene scelta nell'ottava più
vicina all'ultima nota, con una durata più lunga e uno spazio finale.
Una respirazione può invece accorciare la frase senza imporre la tonica.
Queste sono chiusure melodiche; il generatore non riceve progressioni di accordi.

## Parametri e contesto

| Parametro | Responsabilità |
|---|---|
| `octave` | Registro di riferimento rispetto alla root della sezione |
| `step_beats` | Durata di riferimento delle figure |
| `articulation` | Proporzione di durata occupata dalle note |
| `velocity` | Intensità di riferimento, con accenti e variazioni locali |
| `development` | A zero mantiene il motivo letterale; valori positivi pesano le trasformazioni e ne ampliano la trasposizione fino a tre gradi |
| `activity` | Peso delle suddivisioni, durate lunghe e pause |
| `phrase_windows` | Durata del periodo e del gesto dichiarato, da 2 a 8 finestre |
| `seed` | Riproducibilità delle scelte compositive |
| `groove_follow` | Adesione ritmica alla guida condivisa, da 0 a 1 |

I cambi di root e scala adattano le cellule al nuovo contesto, cercando
un raccordo con l'ultima altezza. I nuovi parametri ritmici si applicano
alla prossima finestra senza riavviare la presentazione. Cambiare durata
del periodo apre un nuovo gesto alla finestra corrente: il gesto interrotto
rimane incompleto e non viene promosso nella storia condivisa.

Uscire dal ruolo melodico o passare al motivo letterale interrompe lo
sviluppo. Al rientro viene presentata una cellula. Anche una lacuna fra
richieste apre una nuova sequenza; Stop e discontinuità del runtime eseguono
il reset. Ripetere l'ultima richiesta identica non avanza due volte lo stato.

Lo stato viene preparato in `VoicePlan` e applicato con `accept` dopo
la validazione del piano multivoce. Il Coordinator comunica nel campo
`PlanningRequest.participating` se presenza e politiche delle relazioni
ammettono la finestra. Le finestre silenziate conservano ultima altezza,
cellula e necessità di nuova apertura del materiale partecipante.

La [direzione GPX](DIREZIONE-MUSICALE.md) può fornire un motivo ricavato dalla
forma della tappa, insieme ai contesti armonici delle macrosezioni. Il
generatore riceve i gradi già risolti e continua a svilupparli con le
stesse regole; non legge metriche geografiche o nomi di tappa.

## Stato, ascolto e verifiche

`composition` espone operazione (`phase`), cellula, gradi sorgente,
trasposizione, altezze e attacchi del frammento iniziale prima della guida,
tipo di finale (`ending`), periodo, finestra, seed e conteggio delle chiusure.
Il terminale ne mostra la descrizione sintetica.

`presets/organico.json` usa sviluppo 0,7, attività 0,75, quattro finestre,
seed 7 e adesione al groove 0,3. I parametri di sezione e gli override
manuali conservano le rispettive precedenze. Impostare `development = 0`
per confrontare il motivo regolare. L'efficacia musicale richiede ascolto
con lo stesso motivo, suono e tempo.

I test verificano cellule, riconoscibilità, riproducibilità, intervalli fra
chiusure, silenzi, adattamento di scala e periodo, limiti MIDI, cambi di ruolo,
ritentativi e reset. La suite multivoce verifica il dialogo con le drums e
l'assenza di aggiornamenti dello stato quando una voce successiva fallisce.

Nel ruolo `bass_line` il generatore mantiene il motivo letterale. Nel ruolo
`sustained_texture` delega al [generatore di tessitura](TESSITURA.md) usando
registro e velocity. Il dispositivo segnala i controlli non pertinenti al
ruolo o alla modalità corrente.
