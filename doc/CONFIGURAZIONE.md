# Configurazione della sessione multivoce

L'[indice dei preset](../presets/README.md) distingue tutti i JSON operativi
per funzione e comando. Questa guida descrive i campi della sessione
`desnivel.cli.ensemble` e dei generatori registrati in `cli/generators.py`.

## Organico e pianificazione

In `presets/organico.json`:

| Campo | Significato e vincoli |
|---|---|
| `selection_mode` | `manual`: le voci vengono assegnate esplicitamente |
| `transport_voice` | Identificativo della voce da cui leggere Play, Stop e beat di Live; deve essere registrata in `voices` |
| `window_beats` | Lunghezza delle frasi pianificate, positiva e finita |
| `lead_beats` | Anticipo minimo della prossima frase rispetto al beat ricevuto, positivo e finito |
| `generators` | Definizioni dei generatori, identificate da un nome locale |
| `voices` | Voci della composizione, identificate dal valore da impostare in **Voce** sul dispositivo |
| `sections` | Assetti con confini manuali, usati in assenza di direzione GPX oppure con `--manual-sections` |
| `direction` | File della direzione GPX predefinita, relativo alla configurazione; `--direction` lo sostituisce |
| `timeline` | Parametri dell'allocazione in beat, letti da `analyze_trip --timeline-session` e da `ensemble --timing allocated` |
| `rhythm_voice` | Voce produttrice della guida ritmica; opzionale, attualmente richiede `percussion_phrase` |
| `history_beats` | Conservazione della storia e durata massima dei gesti, positiva e finita; predefinita 64 |
| `relations` | Lista facoltativa delle influenze storiche; campi, limiti e politiche in [Dialogo ritmico](DIALOGO-MUSICALE.md#relazioni-storiche) |

Un beat è una semiminima. `window_beats: 4` non definisce da solo un metro.
`presets/organico.json` abilita `rhythm_voice: "voice_04"`, storia
di 64 beat e relazione ritmica dalle drums precedenti verso la melodia.
L'adesione iniziale al groove è 0,3 per la melodia e 0,7 per il basso.
I parametri di sezione e gli override mantengono la precedenza.
Il controllo `groove_follow` di `motif` e `responsive_line` vale inizialmente
0 e accetta 0…1; richiede `rhythm_voice`. Modella le posizioni degli attacchi
già composti, conservando materiale e numero delle note. È distinto da
`rhythm_follow`, che riguarda la frase melodica sorgente del basso.
Algoritmo, limiti e comportamento nei silenzi in [Dialogo ritmico](DIALOGO-MUSICALE.md).
`percussion_phrase` espone inoltre `style`, una scelta nominale inizialmente
`none`. Gli altri valori sono `house_classic`, `boom_bap_90s` e
`breakbeat_house`. I ruoli `kick`, `snare`, `hat` sono risolti dalla
mappa della destinazione in `adapters/percussion.py`. Dettagli e ascolto in
[Stili percussivi](STILI-PERCUSSIVI.md).
Con `--timing linear` (predefinito) la velocità di replay si sceglie con `--speed`.
Con `--timing allocated` la durata dipende da `timeline` e dal BPM di Live;
una direzione GPX configurata o esplicita è richiesta e `--speed` non è accettato.
La sessione usa `timeline.beats_per_km: 12`: il totale dipende dalla distanza
GPX ed è quantizzato a finestre intere. `min_windows: 2` garantisce 8 beat
per macrosezione con la finestra corrente. Se non entrano, il sistema
segnala una scala insufficiente. In alternativa si può specificare
`target_beats`, escludendo `beats_per_km`, per un totale esplicito con
estensione automatica dei minimi. Vedi [Timeline](TIMELINE.md).

Ogni voce in `voices` contiene:

| Campo | Significato |
|---|---|
| `name` | Nome descrittivo mostrato nella vista globale; opzionale |
| `generator` | Nome di una definizione presente in `generators` |
| `destination` | Identificativo della destinazione; nella sessione ogni voce ne richiede una distinta |
| `dependencies` | Voci richieste: devono essere assegnate nella sezione quando la voce dipendente è attiva |
| `optional_dependencies` | Voci lette quando sono assegnate nella sezione; se attive vengono generate prima della voce dipendente. Nomi registrati, distinti e separati da `dependencies` |

`destination` non è una porta MIDI o UDP. Le porte **Receive** vengono
comunicate dai dispositivi al collegamento: devono essere distinte.
Ogni voce riceve un'istanza indipendente del proprio generatore.

Ogni definizione in `generators` contiene `type`, gli ingressi richiesti dal
tipo, `settings` opzionale e `presets` opzionale. Ogni preset è una mappa di
controlli: i valori omessi vengono completati con quelli iniziali del
generatore, non con l'assetto della macrosezione attraversata.

## Assetti musicali

Una sezione manuale contiene `name`, `from_progress`, `root`, `scale` e
`assignments`. Le progressioni sono frazioni della distanza totale: partono
da zero, sono strettamente crescenti e inferiori a uno. L'ultima sezione
copre la fine del viaggio.

`presets/direzione-viaggio.json`, caricato dal campo `direction` o da
`--direction`, definisce:

| Campo | Significato |
|---|---|
| `analysis` | File dei criteri di analisi del percorso |
| `grouping` | File delle famiglie di macrosezioni |
| `families` | Un assetto musicale per ogni famiglia configurata, senza famiglie aggiuntive |
| `automatic_music` | Profilo della tappa → tavolozza armonica e motivo, con override facoltativi; [contratto completo](DIREZIONE-MUSICALE.md) |

I due percorsi sono relativi al file di direzione. Ogni assetto di famiglia
richiede `assignments`. Con `automatic_music`, root e scala sono risolte
dal profilo; eventuali valori nella famiglia sono override espliciti.
Senza automatismo sono richieste `root` e `scale` per ogni famiglia.

| Campo dell'assetto | Significato |
|---|---|
| `root` | Altezza MIDI intera di riferimento, non soltanto una classe di altezza; i generatori verificano il registro delle note prodotte |
| `scale` | Nome della scala in `music.patterns.SCALES` |
| `assignments` | Voci attive, ciascuna con `role`, `presence` opzionale e una mappa opzionale `parameters` |
| `role` | Ruolo fra quelli supportati dal generatore della voce |
| `presence` | Probabilità di partecipazione per frase intera, da 0 a 1; predefinita 1 |
| `parameters` | Valori dei controlli di quel generatore applicati nella sezione |

Le scale disponibili sono `chromatic`, `major`, `minor`, `pentatonic_minor`,
`pentatonic_major`, `dorian`, `phrygian`, `lydian`, `mixolydian` e `blues`.
Una voce assente dalle assegnazioni è inattiva. Le sue dipendenze devono
essere presenti nell'organico quando viene attivata. Gli assetti sono
completi per sezione: non ereditano le assegnazioni della precedente.

I criteri di analisi, la persistenza delle fasce e il raggruppamento sono
descritti in [Analisi del percorso](ANALISI-PERCORSO.md).

### Presenza delle voci

La presenza automatica è `assignments.<voce>.presence` della sezione
corrente. Vale 1 se omessa e 0 per una voce fuori organico. Si applica alle
sezioni manuali e agli assetti di famiglia usati con `--direction`.
Per esempio, `{"role": "melody", "presence": 0.4}` prevede una
partecipazione indicativa del 40% delle frasi.

Le configurazioni fornite non impostano quote di presenza aggiuntive:
le voci assegnate mantengono il valore predefinito 1. L'attività e le pause
interne alle frasi dipendono dai generatori e dai loro parametri.

Il moltiplicatore manuale, da 0 a 10 e inizialmente 1, si modifica dal device.
La presenza effettiva è `min(1, presenza automatica × moltiplicatore)`.
Un valore automatico di 0,4 con moltiplicatore 2 produce 0,8; una voce
fuori organico rimane esclusa anche con un moltiplicatore maggiore di 1.
Il moltiplicatore si conserva fra sezioni e restart della sessione, fino
alla modifica manuale o alla chiusura del processo Python. È separato dai
preset dei generatori e dalla loro densità di note.

Ogni finestra di `window_beats` viene conservata o sostituita integralmente
con una frase vuota. La scelta è riproducibile in base a voce e beat di
inizio, con la stessa soglia per tutti i valori di presenza. Non garantisce
una percentuale esatta nella singola tappa. I generatori continuano a
elaborare le richieste; le voci dipendenti ricevono le frasi effettive,
compresi i silenzi decisi dalla presenza. Una voce ammessa con probabilità
1 può comunque produrre pause secondo il proprio generatore.

Le modifiche agiscono sulle frasi ancora da pianificare. Quelle già inviate
terminano normalmente. Il device e il terminale mostrano presenza automatica,
moltiplicatore e presenza effettiva della sezione corrente: sono valori di
partecipazione, non una misura del volume o una conferma audio.

## Parametri del generatore `motif`

`degrees` è una lista obbligatoria, non vuota, di interi non negativi.
I gradi partono da zero: `0` è la tonica, `1` il grado successivo della
scala; oltre l'ultimo grado si sale nell'ottava successiva.

I seguenti valori possono comparire in `settings`, nei preset e nei
`parameters` delle assegnazioni. I limiti riportati sono quelli del registro
della sessione e dei controlli esposti dal dispositivo.

| Parametro | Predefinito | Intervallo | Effetto |
|---|---:|---|---|
| `octave` | 0 | Intero −5…5 | Trasposizione di ottave rispetto a `root` |
| `step_beats` | 1 | 0,25…8 beat | Passo regolare nel motivo letterale; durata di riferimento nello sviluppo |
| `articulation` | 0,8 | 0,05…1 | Frazione della durata disponibile occupata dalla nota articolata |
| `velocity` | 85 | Intero 1…127 | Intensità MIDI di riferimento, con accenti nello sviluppo; non è un volume in dB |
| `development` | 0 | 0…1 | Zero ripete il motivo; sopra zero attiva e regola lo sviluppo |
| `activity` | 0,75 | 0…1 | Pesi di durate brevi, lunghe e pause nello sviluppo |
| `phrase_windows` | 4 | Intero 2…8 | Finestre del periodo e del gesto melodico; la fine non impone una chiusura sulla tonica |
| `seed` | 0 | Intero 0…2147483647 | Riproducibilità delle variazioni |

Ruoli supportati:

- `melody`: motivo letterale o sviluppato, secondo `development`.
- `bass_line`: motivo letterale, senza lo sviluppo melodico.
- `sustained_texture`: una nota per finestra dal primo grado di `degrees`;
  usa registro e velocity. Gli altri controlli ritmici e di sviluppo non
  modificano questa nota sostenuta.

I valori predefiniti del codice possono essere sovrascritti dal file.
Per esempio, `organico.json` imposta `development: 0.7` e `seed: 7`.
L'algoritmo è descritto in [Generazione melodica](MELODIA.md).

Nel motivo letterale `activity`, `phrase_windows` e `seed` non intervengono.
Il device segnala i controlli inattivi senza eliminarne i valori.

## Parametri del generatore `sustained_texture`

Supporta il ruolo `sustained_texture`. `degree` è il grado di riferimento,
intero non negativo e predefinito 0, con la stessa numerazione di `degrees`
del motivo. I controlli usabili in `settings`, preset e assegnazioni sono:

| Parametro | Predefinito | Intervallo | Effetto |
|---|---:|---|---|
| `octave` | 0 | Intero −5…5 | Trasposizione del grado di riferimento e del registro rispetto alla tonica della sezione |
| `velocity` | 85 | Intero 1…127 | Velocity della nota sostenuta |
| `follow_source` | 0 | Intero 0 oppure 1 | Switch **Segui sorgente**: 0 usa il grado di sezione; 1 sceglie una nota dalla frase ricevuta |

La modalità coordinata legge al massimo una dipendenza musicale, richiesta
o facoltativa secondo la configurazione della voce. In assenza della
sorgente o con una frase vuota produce silenzio. La modalità indipendente
usa soltanto il contesto armonico. Entrambe producono al massimo una nota,
dall'inizio alla fine della finestra, e rispettano presenza e organico.

`organico.json` assegna questo generatore ad `atmosphere`, con `degree: 0`,
`octave: 1`, velocity 52 e modalità indipendente iniziale. `voice_03` legge
`voice_01` come dipendenza facoltativa. Lo switch viene conservato nei
preset utente della tessitura. Non sono forniti preset base per questa voce.
Algoritmo, registro e prova d'ascolto sono in [Tessitura sostenuta](TESSITURA.md).

## Parametri del generatore `responsive_line`

Richiede una dipendenza musicale e supporta il ruolo `bass_line`.
I controlli esposti nella sessione sono:

| Parametro | Intervallo | Effetto |
|---|---|---|
| `density` | 0…4 | Numero desiderato di attacchi per beat, limitato dai posti disponibili e da `min_spacing` |
| `syncopation` | 0…1 | Preferenza fra beat interi e posizioni intermedie |
| `rhythm_follow` | 0…1 | Preferenza per attacchi coincidenti con quelli della frase sorgente; influenza anche durate e accenti |
| `melody_follow` | 0…1 | Peso dell'altezza sorgente locale rispetto agli appoggi complessivi della frase |
| `mobility` | 0…1 | Peso del movimento e delle preferenze di registro |
| `variation` | 0…1 | Peso delle variazioni riproducibili di attacchi e altezze |
| `articulation` | 0,05…1 | Frazione di durata disponibile occupata dalle note |
| `groove_follow` | 0…1 | Adesione degli attacchi composti alla guida ritmica condivisa |

Ulteriori impostazioni non esposte nel menu, accettate in `settings` e
nei `parameters` delle assegnazioni; `strategy` è ammesso solo in `settings`:

| Parametro | Predefinito | Significato e vincoli |
|---|---:|---|
| `lowest`, `highest` | 28, 47 | Limiti MIDI inclusivi 0…127; almeno 12 altezze consecutive |
| `strategy` | `responsive` | Preset iniziale del generatore: `responsive`, `follow` o `slap` |
| `min_spacing` | Dal preset | Distanza minima positiva fra attacchi, in beat |
| `velocity_ratio` | 0,9 | Fattore della velocity sorgente, maggiore di zero e al massimo uno |
| `seed` | 0 | Intero per le variazioni riproducibili |
| `variation_period` | 4 | Intero positivo; periodo in frasi della preferenza di risoluzione |
| `max_hold` | 2 | Durata disponibile massima prima dell'articolazione, in beat, positiva |
| `grid` | 0,5 | Passo positivo della griglia delle posizioni candidate, in beat |

I valori iniziali dei controlli compositivi dipendono da `strategy` e dagli
eventuali valori espliciti di `settings`. La tabella dei tre preset e
l'algoritmo sono in [Generatore del basso](BASSO.md).
I preset del device contengono gli otto controlli esposti, incluso `groove_follow`.

Nel device `density` è mostrato come **densità richiesta**. Il riepilogo
accanto al valore indica attacchi selezionati/capacità ritmica dell'ultimo
piano accettato; `saturo` indica che il target ha raggiunto tale capacità.
Il limite dipende da sorgente, candidati, spaziatura e ordine di selezione:
non è un massimo fisso a 1. Il riepilogo non cambia il valore richiesto.
La descrizione del controllo riporta i beat disponibili; lo stato espone
il dettaglio in `composition.density`. Con presenza nulla il device mostra
`voce non partecipante`.
`strategy` seleziona i valori iniziali, non cambia l'algoritmo a esecuzione avviata.

## Parametri del generatore `percussion_pattern`

Supporta `percussion` e non richiede dipendenze. Legge pattern espliciti
configurati, senza dedurre ritmo o altezze dalla scala del contesto.

| Campo della definizione | Contenuto |
|---|---|
| `lanes` | Mappa di nomi locali a note MIDI intere 0…127, distinte |
| `patterns` | Lista non vuota di pattern; l'ordine determina l'indice del controllo `pattern` |
| `patterns[].name` | Nome non vuoto e distinto, mostrato nelle decisioni del generatore |
| `patterns[].length_beats` | Lunghezza positiva e finita del ciclo, in beat |
| `patterns[].hits` | Lista di massimo 128 attacchi, anche vuota per un pattern silenzioso |
| `hits[].beat` | Posizione nel ciclo, da zero incluso alla lunghezza esclusa |
| `hits[].lane` | Nome presente in `lanes` |
| `hits[].velocity` | Intensità MIDI intera 1…127 |

Attacchi duplicati sulla stessa nota e alla stessa posizione sono rifiutati.
I controlli usabili in `settings`, preset e assegnazioni sono:

| Parametro | Predefinito | Intervallo nella sessione | Effetto |
|---|---:|---|---|
| `pattern` | 0 | Intero 0…numero di pattern meno uno | Selezione del pattern nell'ordine della lista |
| `velocity_ratio` | 1 | 0,05…1 | Moltiplica le velocity degli attacchi, arrotondando e limitando il risultato a 1…127 |
| `gate_beats` | 0,1 | 0,01…1 beat | Durata MIDI massima di ogni nota; accorciata prima della nota successiva della stessa altezza e alla fine della frase |

Il ciclo è ancorato al beat zero del trasporto: richieste di lunghezza
diversa ne selezionano la porzione corrispondente. La stessa richiesta e
gli stessi parametri producono le stesse note. Una finestra non può
contenere più di 128 attacchi. Il generatore produce una `Phrase` che usa
lo stesso adattatore e lo stesso dispositivo delle altre voci.

## Parametri del generatore `percussion_phrase`

La prova corrente usa `music/percussion/development.py`. Supporta
`percussion` con frasi di riferimento dichiarate nelle dipendenze. Sviluppa
un materiale su richieste consecutive e lo adatta agli attacchi delle
frasi ricevute; il contesto armonico non determina le note percussive.

| Campo della definizione | Contenuto |
|---|---|
| `material` | Identificativo del catalogo: `spaced_impacts` o `spaced_dialogue`; include attacchi, ancore, sviluppo e ruoli di sostegno |
| `standard_material` | Figura base opzionale per identificativo: `regular_pulse_eighths` o `regular_pulse_offbeats`; se assente, la base è `material` senza trasformazioni |
| `interaction` | Soltanto `support_source` e `answer_source`: identificativi delle frasi da usare come sostegno e risposta |
| `settings` | Valori iniziali dei controlli elencati sotto |
| `presets` | Assetti dei controlli; nella configurazione fornita non ci sono preset base per le drums |

Colpi, ancore e sequenze di sviluppo risiedono in
`music/percussion/catalog.py`. La CLI risolve i riferimenti e collega la
mappa dei pad di `adapters/percussion.py`. Riferimenti sconosciuti,
materiali di sviluppo incompleti e definizioni incorporate come `lanes`
o `style_lanes` producono un errore.

Il materiale corrente, `spaced_impacts`, distribuisce 40 attacchi su 32 beat.
La configurazione della prova copre i 16 pad del 909 Core Kit:

| Nota MIDI | Canale | Suono |
|---|---|---|
| 36 | `kick` | Bass Drum |
| 37 | `rim` | Rim Shot |
| 38 | `snare` | Snare Drum |
| 39 | `clap` | Hand Clap |
| 40 | `kick_alt` | Bass Drum alternativa |
| 41 | `snare_alt` | Snare Drum |
| 42 | `hat` | Closed Hi Hat |
| 43 | `snare_alt_2` | Snare Drum |
| 44 | `tom_low` | Low Tom |
| 45 | `tom_mid` | Mid Tom |
| 46 | `hat_open` | Open Hi Hat |
| 47 | `tom_high` | Hi Tom |
| 48 | `crash` | Crash |
| 49 | `crash_alt` | Crash alternativo |
| 50 | `ride` | Ride |
| 51 | `ride_alt` | Ride alternativo |

I nomi locali distinguono i pad; il timbro effettivo dipende dal Rack caricato.
Il materiale `spaced_impacts` assegna entrambe le casse al sostegno;
gli altri ruoli rispondono alla melodia. Ancore e assegnazioni musicali
appartengono al catalogo.
Gli attacchi sono su una griglia di 0,25 beat; i sostegni proposti ogni
quattro beat vengono adattati alla frase ricevuta.
La prova imposta `displacement_beats: 0`; il controllo regola
l’ampiezza degli spostamenti, per esempio 0,25 beat. Mappa, attacchi, posizioni protette e sequenza di
sviluppo sono definiti nel catalogo; i valori iniziali sono in `organico.json`.

Con `style: none`, ogni ciclo del materiale prepara un'operazione della lista `development`;
la lista viene ripercorsa in ordine. Le operazioni disponibili sono:

- `statement`: presenta il materiale integrale;
- `subtract`: elimina gli attacchi non protetti nel candidato sviluppato;
- `displace`: sposta gli attacchi non protetti di
  `displacement_beats`, in anticipo o in ritardo, tornando all'inizio del
  ciclo se supera il confine;
- `accent`: modifica la velocity degli attacchi non protetti di 64 unità
  MIDI, limitando il candidato a 1…127; Variazione interpola gli accenti comuni;
- `silence`: sospende l'intero ciclo, inclusi gli attacchi protetti.

L’ammissione delle figure sviluppate e il verso delle trasformazioni
dipendono da `seed` e indice del ciclo. Sono riproducibili a parità di sequenza delle richieste, parametri e frasi
di riferimento. Le durate MIDI sono limitate ai confini delle finestre.
In caso di coincidenza durante le trasformazioni locali sulla stessa nota,
l’attacco protetto ha precedenza. L’interazione successiva può spostarlo
o ometterlo per rispettare le frasi di riferimento.

| Controllo | Predefinito | Intervallo nella sessione | Effetto |
|---|---:|---|---|
| `style` | `none` | Scelta nominale | Profilo ritmico; [figure e transizioni](STILI-PERCUSSIVI.md) |
| `transition_beats` | 16 | 0…128 beat | Durata del prossimo cambio fra stili; zero immediato |
| `variation` | 0,7 | 0…1 | A 0 figura base senza sviluppo o interazione; a 1 sviluppo completo; fra gli estremi ammissione progressiva di figure e trasformazioni |
| `displacement_beats` | 0,25 | 0…1 beat | Ampiezza dello spostamento temporale |
| `velocity_ratio` | 0,85 | 0,05…1 | Moltiplicatore della velocity finale di tutti gli attacchi |
| `gate_beats` | 0,1 | 0,01…1 beat | Durata massima, accorciata alla fine della finestra e prima del prossimo attacco della stessa nota |
| `seed` | 7 | Intero 0…2147483647 | Selezione riproducibile degli attacchi e del verso delle trasformazioni |
| `support_tolerance_beats` | 0,5 | 0…1 beat | Distanza massima per allineare un colpo di sostegno a un attacco della sorgente |
| `answer_clearance_beats` | 0,25 | 0…1 beat | Distanza minima degli attacchi di risposta dagli attacchi della sorgente principale |

Nella prova, `voice_04` richiede la frase di `voice_01` e legge quella di
`voice_02` come dipendenza facoltativa. I ruoli `kick` e `kick_alt` cercano l'attacco più
vicino della frase di `voice_02` entro la tolleranza: lo raggiungono e mediano
la propria velocity con quella della sorgente. Se manca un attacco vicino,
il colpo viene omesso. In caso di parità di distanza prevale l'attacco con
velocity maggiore, poi quello precedente.

I ruoli di risposta del materiale omettono gli attacchi troppo vicini a quelli di
`voice_01`, lasciandogli spazio. Usano le posizioni del materiale rimaste
dopo lo sviluppo, senza aggiungere colpi per ogni nota melodica. Se la
frase melodica è silenziosa, le risposte vengono omesse. Se entrambe le
frasi sono silenziose, anche il candidato sviluppato è silenzioso.
Con Variazione inferiore a 1 può contribuire la figura base.

Con Variazione positiva la sorgente di risposta è obbligatoria;
la sua assenza produce un errore.
La sorgente di sostegno può essere inattiva: in quel caso i colpi di
sostegno sono omessi e la decisione espone `support_available: false`.
L'interazione legge soltanto gli attacchi delle frasi della finestra corrente,
non l'audio o le frasi future. Cambiare la partizione delle finestre può
cambiare quali attacchi sono disponibili vicino ai confini. Attacchi sulla
stessa nota e allo stesso beat vengono uniti conservando la velocity maggiore.

La sequenza corrente è `statement`, `statement`, `subtract`, `displace`,
`statement`, `accent`, `silence`, `displace`: otto cicli di 32 beat
con `style: none`; con uno stile selezionato, otto battute di quattro beat.
Il primo ciclo comincia alla prima frase pianificata, indipendentemente
dal beat assoluto di Live. La posizione avanza della durata di ciascuna
richiesta; ripianificare lo stesso inizio riutilizza la stessa posizione.
Il cambio di famiglia del terreno conserva lo sviluppo. Il reset del
runtime, compresi Stop e discontinuità del trasporto, lo riporta all'inizio.

Il piano descrive materiale, posizione logica e operazioni dei cicli nella
plancia. Non sono forniti preset base per le drums; quelli utente
possono salvare assetti completi. Una richiesta può coprire al massimo 128 cicli e
produrre al massimo 128 attacchi. Il generatore di pattern espliciti resta
disponibile come tipo distinto.

**Variazione** (`variation`) regola lo sviluppo attraverso un solo valore.
Con `style: none`, la base è `standard_material`, se presente; altrimenti
è `material` senza trasformazioni. Il candidato sviluppato usa `material`,
`development` e `interaction`. Nella configurazione fornita la base
`regular_pulse_eighths` dura quattro beat: cassa su 0 e 2, rullante su 1 e 3,
hi-hat ogni mezzo beat.

Fra 0 e 1, gli attacchi comuni mantengono la posizione e interpolano la
velocity. Gli eventi esclusivi della base o del candidato vengono scelti
in modo coerente per canale e ciclo del materiale, usando Variazione come
probabilità di ammettere lo sviluppo. Con uno stile selezionato la scelta
avviene per canale e battuta; Variazione orienta anche le figure del
catalogo. Non garantisce una percentuale esatta di colpi diversi.

A zero sono segnalati inattivi `displacement_beats`,
`support_tolerance_beats`, `answer_clearance_beats` e `seed`.
Velocity e durata MIDI restano applicate. Lo spostamento è inattivo anche
senza operazioni `displace`; con uno stile selezionato la tolleranza di
sostegno è inattiva quando nessun colpo di risposta usa `support_lanes`.
I valori restano modificabili e vengono usati quando pertinenti.
La conversione dei vecchi preset utente è descritta in
[Stili percussivi](STILI-PERCUSSIVI.md#generazione-e-dialogo).

## Precedenza e applicazione delle modifiche

Per una voce attiva i parametri vengono risolti in questo ordine:

1. Impostazioni iniziali del generatore.
2. Parametri dell'assegnazione della sezione corrente.
3. Politiche adattive, quando è collegata l'analisi GPX.
4. Valori manuali mantenuti nella sessione Python.

Le scelte manuali di ruolo hanno precedenza sul ruolo della sezione, ma
non attivano una voce esclusa dall'organico. `Follow section` ripristina il
ruolo assegnato; non cancella i parametri manuali.

Il comando **Preset** applica tutti i controlli iniziali completati con i
valori del preset, rendendoli manuali nelle sezioni successive.
Modificare un singolo **Parametro** mantiene manuale soltanto quel
controllo. Gli altri seguono le proprie politiche o gli assetti delle sezioni.
Nel device **manual** e l'indicatore auto/manual si riferiscono al
parametro selezionato. Spegnere lo switch lo restituisce all'automazione,
con rilascio graduale per i controlli adattivi, conservando gli altri override. Il flag `manual` è esposto
nello stato di ciascun controllo e rimane separato da ruolo e presenza.
`EnsembleSession.clear_parameters(voice)` elimina tutti gli override.
Riavviare il processo Python ripristina i valori dei file.

Le modifiche manuali non riscrivono i JSON di configurazione. Il salvataggio esplicito dal device aggiorna soltanto la libreria dei preset utente. Le nuove assegnazioni entrano
nelle finestre ancora da pianificare; i piani già inviati rimangono validi.
I controlli adattivi interpolano i valori fra finestre usando contesto
locale e osservazioni musicali. Quelli non gestiti dalle politiche
mantengono i cambi di assetto configurati. Formule e tempi sono in
[Direzione musicale](DIREZIONE-MUSICALE.md#adattamento-dei-parametri).
