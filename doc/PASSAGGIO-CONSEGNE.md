# Passaggio di consegne — Desnivel

Stato della sessione del 19 ottobre 2026.

## Obiettivo e valore della prova

Desnivel è un motore di musica generativa multivoce basato su un viaggio
GPX. La composizione deve rendere percepibile l'evoluzione del percorso.
Strumenti, ruoli, generatori e destinazioni sono concetti distinti.

La prova corrente in Ableton Live comprende melodia, accompagnamento,
atmosfera e drums. Marco ha confermato di sentire le quattro parti e ha
valutato positivamente la direzione dello sviluppo. Questo conferma il
funzionamento della prova d'ascolto; qualità compositiva, suoni, organico e
corrispondenze fra terreno e musica rimangono materiale di sperimentazione.
Il preset della prova non costituisce un modello musicale definitivo.

## Regole da leggere prima di intervenire

Il riferimento vincolante è [AGENTS.md](../AGENTS.md). In particolare:

- Director e Coordinator dipendono da interfacce musicali generiche.
  Nomi, controlli e regole di strumenti o dispositivi specifici appartengono
  ai moduli delle voci o agli adattatori, anche nei loro import.
- Riutilizzare componenti esistenti e mantenere il codice semplice e
  modulare. Le configurazioni musicali sono dati espliciti modificabili.
- Documentare come operativo solo ciò che è collegato e verificabile nel
  codice o nelle configurazioni. Le proposte restano in `doc/proposte/`.
- Conservare le integrazioni e i banchi di prova esistenti, incluso quello
  con il sequencer esterno. La sessione Python è un'altra modalità di prova.
- Commit solo su richiesta esplicita, dopo revisione del diff; escludere
  output, log e pacchetti generati.

## Flusso operativo implementato

1. `trip/loader/` carica il GPX e produce `Track` con quota, distanza e
   metriche derivate.
2. `trip/analysis.py`, funzione `analyze_track`, classifica il profilo in
   fasce di pendenza con osservazione e persistenza configurate.
3. `trip/sections.py`, funzione `group_zones`, raggruppa soltanto zone
   consecutive e adiacenti della stessa famiglia. Le zone originali restano
   disponibili e le macrosezioni ne conservano gli indici.
4. `cli/trip_direction.py` prepara le sezioni musicali dagli assetti delle
   famiglie. I confini vengono dal GPX; gli assetti sono scelti nel JSON.
5. `music/director.py` seleziona contesto e assegnazioni della sezione;
   `music/coordinator.py` risolve le dipendenze e raccoglie le `Phrase`.
6. `cli/generators.py` collega le implementazioni concrete. Ogni voce
   riceve una propria istanza del generatore.
7. `cli/ensemble_runtime.py` governa replay e pianificazione;
   `adapters/voice_device.py` traduce le frasi per i dispositivi comuni
   `Desnivel_Voice`, collocati prima degli strumenti in Live.

I percorsi Python sopra indicati sono relativi a `src/desnivel/`.
`Note` e `Phrase` in `music/phrases.py` sono indipendenti dai dispositivi.

## Configurazioni e responsabilità

| File in `presets/` | Responsabilità |
|---|---|
| `organico.json` | Voci, dipendenze, generatori, impostazioni, preset e sezioni manuali |
| `direzione-viaggio.json` | Assetto musicale per ciascuna famiglia; riferimenti ai due file del percorso |
| `analisi-percorso.json` | Passo di campionamento, finestra di pendenza, persistenza e soglie delle fasce |
| `macrosezioni-percorso.json` | Appartenenza delle fasce alle famiglie |

La configurazione attuale raggruppa `climb` e `steep_climb` in `ascent`,
`descent` e `steep_descent` in `descent`, e conserva `level` come famiglia.
Un tratto di un'altra famiglia interrompe la macrosezione, anche se breve.
Non sono implementate tolleranze per assorbire queste interruzioni.

La prova Firenze–San Gimignano produce 49 zone e 33 macrosezioni. Marco ha
confrontato manualmente le fasce e le ha ritenute plausibili per procedere;
la taratura rimane revisionabile. Le percentuali nei risultati descrivono
posizioni ricavate dalla distanza, non confini musicali prestabiliti.

L'[indice dei preset](../presets/README.md) elenca anche i file usati dagli
altri comandi. Il [riferimento di configurazione](CONFIGURAZIONE.md) descrive
campi, unità, limiti dei controlli e precedenze. Aggiungere una voce alla
prova non richiede un JSON separato per lo strumento.

## Quattro voci della prova

| Part | Receive UDP | Generatore | Ruolo nella direzione GPX |
|---|---:|---|---|
| `voice_01` | 9101 | `motif` | `melody` |
| `voice_02` | 9102 | `responsive_line` | `bass_line`, dipendente dalla frase di `voice_01` |
| `voice_03` | 9103 | `sustained_texture`, istanza `atmosphere` | `sustained_texture`, con sorgente facoltativa `voice_01` |
| `voice_04` | 9104 | `percussion_phrase` | `percussion` |

Le porte sono impostate nelle istanze del dispositivo. Il server Python
usa 9006; la sorgente del trasporto è `voice_01`. Tutte le parti attive
devono essere collegate, altrimenti la sessione attende.

La direzione GPX mantiene attive le quattro voci. Le parti intonate usano
root MIDI 57 e scala `minor`. L'atmosfera è una nota monofonica sostenuta
per finestra, riarticolata nella successiva; con `octave: 1` e `degree: 0`
produce MIDI 69 in modalità indipendente. Lo switch **Segui sorgente**
attiva il sostegno dalla frase melodica: vedi [Tessitura sostenuta](TESSITURA.md).
Il timbro viene scelto nello strumento Live.

Il generatore percussivo legge pattern espliciti dal JSON; non genera ancora
un arrangiamento ritmico autonomo. La mappa concordata per il Drum Rack è
cassa 36, rullante 38, charleston 42. I pattern `sparse`, `steady` e `driving`
sono associati rispettivamente a pianura, salita e discesa. Mappa e pattern
non sono incorporati nelle classi generiche.

Gli assetti attuali differenziano attività, ritmo, articolazione e dinamica
delle voci. Tornare a una famiglia ripristina il suo assetto di base; i
parametri non si accumulano fra macrosezioni. Le modifiche manuali hanno
precedenza e persistono nella sessione Python. Il riferimento descrive
anche il comportamento del dispositivo, che applica l'intero insieme dei
controlli correnti quando si modifica un singolo parametro.

## Avvio e controllo

Nel checkout usato durante la sessione:

```sh
cd /Users/marco/ogni-tanto-programmo/desnivel
.venv/bin/python -m desnivel.cli.ensemble \
  --gpx gpx/tappa05_Firenze_San_Gimignano.gpx \
  --config presets/organico.json \
  --direction presets/direzione-viaggio.json \
  --speed 50
```

Aggiungere `--dry-run` per verificare tutte le sezioni senza aprire il
server o inviare note. Omettere `--direction` per usare le sezioni manuali.
Chiudere prima eventuali altri processi che occupano la porta 9006.

In Live, usare `Desnivel_Voice` prima di ciascuno strumento, impostare Part,
Receive e Python, scegliere `Follow section` e premere Connect. Il dispositivo
è lo stesso per tutte le voci; non carica strumenti o preset timbrici.
Il sorgente è in `m4l/`; costruzione e aggiornamento della cartella installata
sono descritti in [VOCE-M4L.md](VOCE-M4L.md).

Play permette il replay, Stop lo mette in pausa e spegne le note. Un salto
o loop nel trasporto ripianifica le note senza riportare il viaggio al punto
corrispondente alle battute. I cambi di assetto si applicano alla prossima
finestra ancora da pianificare; i generatori non vengono azzerati a ogni
macrosezione. Non è implementata una transizione graduale dei parametri.

Il terminale mostra avanzamento, macrosezione corrente, collegamenti e
decisioni. Lo snapshot `/tmp/desnivel-session/state.json` distingue la
posizione corrente dalla macrosezione dell'ultimo piano inviato. Questo
stato descrive i piani MIDI, non una misura del risultato audio.

Per ricreare il report del percorso:

```sh
.venv/bin/python -m desnivel.cli.analyze_trip \
  --gpx gpx/tappa05_Firenze_San_Gimignano.gpx \
  --config presets/analisi-percorso.json \
  --grouping presets/macrosezioni-percorso.json \
  --output output/analisi-percorso.json \
  --html output/analisi-percorso.html
```

Il file HTML è autonomo e si apre nel browser. Mostra profilo, pendenza,
zone, macrosezioni e concordanza fra zona confermata e osservazioni locali.
I file generati in `output/` sono esclusi dal repository.

## Verifiche e lavoro da riprendere

Ultima suite Python eseguita: **234 test superati**. Copertura rilevante:
fasce e persistenza, raggruppamento, configurazioni, dipendenze, trasporto,
ruoli e controlli, destinazioni distinte, continuità fra fasce interne,
pattern percussivi, report ed esecuzione `--dry-run` sulle 33 macrosezioni.
Il comando della suite è `.venv/bin/python -m pytest`.
Alcuni test aprono porte UDP locali e richiedono i permessi dell'ambiente.

La prova manuale comunicata da Marco conferma l'ascolto delle quattro parti.
La valutazione attuale serve a orientare le prossime prove di composizione.

Il lavoro successivo resta da concordare sul risultato d'ascolto:

- Affinare la qualità e la differenziazione musicale delle macrosezioni,
  confrontando lo stesso tratto con una modifica alla volta.
- Definire le variazioni musicali nelle fasce interne: al momento `climb`
  e `steep_climb` della stessa macrosezione non cambiano l'assetto.
- Definire eventuali transizioni graduali, controllo timbrico degli
  strumenti e sviluppo dei pattern percussivi. Non sono capacità attuali
  della direzione GPX.
- Valutare raggruppamenti che tollerino brevi interruzioni e riconoscimento
  di ulteriori eventi del percorso, senza alterare il dettaglio originale.

Le proposte conservate sono in
[Sezioni guidate dal viaggio](proposte/SEZIONI-GUIDATE-DAL-VIAGGIO.md),
[Plancia](proposte/PLANCIA.md) e
[Ruoli musicali](proposte/RUOLI-MUSICALI.md).
La plancia operativa attuale è testuale; il report del percorso è un HTML
statico interattivo, non una dashboard musicale in tempo reale.
