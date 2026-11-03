# Sequencer Snake

Snake può essere controllato come componente della sessione multivoce,
con un ruolo e una modalità di relazione scelti dall'utente. Continua a
produrre il MIDI attraverso i propri banchi e percorsi. Il banco melodico
`trip_music` e l'esportazione verso il basso restano disponibili separatamente.

## Componente multiruolo

1. Avviare `comandi/09 - Sessione multitappa.command` e scegliere la tappa.
   La sessione parte con le quattro voci della prova.
2. Prima del Play, premere **N** nel terminale per preparare Snake.
3. In Live creare una traccia MIDI con `MDD_SNAKE_LengthBank.amxd`,
   `Desnivel_Snake_Control.amxd` immediatamente dopo e uno strumento.
   Il controllo individua soltanto il device precedente nella stessa catena.
4. Nel controllo impostare `voce` su `snake_01`, Receive `9201`, Python `9007`.

La guida ritenta il collegamento ogni dieci secondi. **Invio** richiede
subito un controllo; non forza una conferma se la traccia non è pronta.
La verifica richiede controllo collegato, Snake compatibile con Length e
strumento dopo il controllo. Il terminale indica ciò che manca e conferma
quando Snake è pronto. **C** resta disponibile per collegare tutti i device.
**Esc** annulla la preparazione e chiude il servizio Snake, lasciando la
sessione principale disponibile. Le tracce create manualmente restano in Live.

Durante la preparazione il viaggio non avanza. Un Play ricevuto da Live
viene fermato; ripresa e avvio REC sono bloccati fino alla conferma o
all'annullamento. La guida non avvia automaticamente la riproduzione.
Dopo la conferma premere Play in Live.

Il componente lascia passare il MIDI di Snake; non esegue le frasi del
player Python. Alla pausa silenzia i gate; disconnessione e Panic
interrompono anche le note trattenute dal componente.

Il menu del ruolo usa gli identificativi musicali esistenti; `ruolo configurato`
ripristina il ruolo iniziale del componente:

| Ruolo | Uso e valori automatici iniziali |
|---|---|
| `melody` | Principale: motivo nel registro della sezione, attività 0,65, velocity 85, durata 220 ms |
| `bass_line` | Accompagnamento: un'ottava sotto, appoggi di tonica, quinta e terza, attività 0,4, velocity 75, durata 160 ms |
| `sustained_texture` | Sottofondo: un'ottava sopra, tonica sostenuta, attività 0,15, velocity 48, durata 2500 ms |

Nel menu `parametro`, `mode` sceglie **autonomo** o **coordinato** per
qualsiasi ruolo. Entrambe le modalità usano il contesto locale della finestra in esecuzione,
lo stesso `adaptive_context` delle altre voci. Autonomo usa armonia e motivo
della tappa. Coordinato
legge la voce scelta in `source` dal piano corrente: riprende le classi
di altezza, dirada l'accompagnamento con sorgenti fitte e usa l'altezza
più pesante per la tessitura. Una sorgente assente o silenziosa silenzia
i gate; prima del primo piano compare l'attesa.

Il viaggio modifica il comportamento di base di ciascun ruolo:

- intensità del terreno: attività dei gate, dinamica e suddivisione;
- cambiamento e persistenza: durata e movimento del percorso;
- vento e cambiamento della pioggia: dinamica e movimento, quando il
  contributo meteo è abilitato nel piano corrente.

Gli obiettivi numerici evolvono su otto beat usando le transizioni comuni
alle altre voci. Se un'indicazione manca, il relativo contributo resta neutro.
Accenti forti e deboli producono velocity e durate diverse fra le celle.
In modalità coordinata anche dinamiche e articolazioni della sorgente
modellano la linea melodica e il basso; la tessitura mantiene il sostegno.

Nel menu `parametro`:

| Controllo | Effetto |
|---|---|
| `octave` | Registro rispetto alla tonica |
| `activity` | Frazione di gate aperti nel ciclo |
| `velocity` | Livello di riferimento degli accenti MIDI |
| `length_ms` | Durata di riferimento delle singole note |
| `movement` | Ampiezza del motivo melodico, disposizione ritmica e percorso |
| `pulse` | Suddivisione comune delle tre lane, da `32n` a `2n` |

Modificare un controllo lo rende manuale; il cambio di ruolo conserva gli
override. Spegnere `manual` restituisce il controllo all'automatismo.
Velocity e durata manuali fissano il livello di riferimento, conservando
l'articolazione fra le celle. `mode` e `source` restano separati dal ruolo.

L'adattatore traduce il movimento in percorsi lineari, serpentine, spirale
o diagonali usando le Shape esistenti. Dispone note, gate, velocity e
Length lungo il percorso scelto, con tre lane di 16 passi in avanti e
uguale suddivisione e Shift 1.

Il componente aggiorna il materiale dalla finestra corrente, senza leggere
in anticipo quelle future. I pacchetti vengono confermati e ritrasmessi;
il controllo scrive soltanto i valori effettivamente diversi. Gli
aggiornamenti non sono quantizzati a battuta né allineati alla fase interna
di Snake. La modalità coordinata legge le altre voci; la previsione di
Snake non viene ancora comunicata al Coordinator.

La traduzione delle altezze usa **Chromatic, tonica C**: il parametro
nota vale MIDI − 24, con registro MIDI 24–107. Il componente imposta
Chromatic; mantenere C come tonica in Snake. Le durate sono espresse in
millisecondi e rimangono indipendenti dal BPM.

### Configurazione e costruzione

`presets/snake.json` contiene `port` e `components`. Ogni componente ha
`role`, `mode` e `source`, identificativo di una voce della sessione.
Per più Snake aggiungere componenti distinti e impostare ID e Receive
univoci, per esempio `snake_02` e `9202`. Il server Python resta unico.
Il file `snake.json` è cercato accanto al JSON della sessione e viene letto
soltanto alla richiesta **N**. L’avvio ordinario e `--dry-run` non aprono il
server Snake né richiedono questo file.

```sh
.venv/bin/python tools/build_snake_control.py --output /tmp/desnivel-snake-control
```

La cartella di output deve essere nuova. Conservare il device e i quattro
script generati insieme. Il builder riusa l'interfaccia Voice; il collegamento
al device precedente è in `m4l/desnivel_snake_control.js`, il materiale
musicale neutro in `music/sequence/material.py`. `cli/snake_control.py`
collega il controllo alla sessione senza avviare un secondo replay.
Lo snapshot espone i componenti separatamente in `components`.

---

## Bridge di controllo e parametri

Il bridge Max for Live (`m4l/desnivel-bridge.amxd` con `m4l/desnivel_snake_params.js`) riceve comandi OSC sulla porta **9001**:

```text
/desnivel/v1/control/snake/set  <nome_parametro>  <valore>
```

Lo script JavaScript cerca il primo device il cui nome contiene `snake` tra le tracce del Set e ne aggiorna i parametri tramite la Live API.

### Configurazione delle note e scale
- Il parametro `Note_01` accetta valori da `0` a `83`.
- Nella configurazione di riferimento (scala *Chromatic*, tonica *C*), i valori `36–51` generano note MIDI tra `60` e `75` (Do centrale e ottava successiva).
- **Shape dei Gate**: definisce il percorso geometrico attraverso la matrice 4×4 dei passi (valori da `0` a `13`). Durante il replay, il motore estrae una Shape all'ingresso di ciascuna sezione della tappa.

---

## Banco Length personalizzato

Lo script `tools/build_snake_length.py` estende il device vanilla MDD Snake (versione 3.2.3) aggiungendo un banco dedicato alla durata delle note (**Length**), preservando i banchi *Notes*, *Gates*, *Velocities* e *Custom*.

```sh
python3 tools/build_snake_length.py \
  --source "$HOME/Music/Ableton/User Library/MaxForLive/MDD___SNAKE_V3.2.3.amxd" \
  --output /tmp/desnivel-snake-length/MDD_SNAKE_LengthBank.amxd
```

Le mod costruite espongono nomi brevi univoci per Shape, Speed, Steps,
Direction e Shift delle lane Notes, Gates e Velocities: sono i nomi letti
dalla Live API. Dopo aver aggiornato il file in libreria, ricaricare il
device Snake nel Set per applicare la nuova definizione dei parametri.

Il banco Length gestisce 16 valori (0–127) convertiti in millisecondi tra i valori configurati di minimo e massimo (tipicamente 50–500 ms).

---

## Telemetria dello stato ed Export

La variante costruita da `tools/build_live_bass.py` aggiunge il controllo **Export** al banco Length e invia lo stato del sequencer verso Python.

- **Porta**: UDP **9003**
- **Indirizzo**: `/desnivel/v1/snake/state`
- **Payload**: stringa JSON contenente posizione corrente del trasporto, stato Play/Stop, BPM e stato dei banchi.

### Campi principali del messaggio
```json
{
  "version": 1,
  "source": "snake-source",
  "serial": 12,
  "epoch": 1,
  "beat": 16.0,
  "playing": 1,
  "state": {
    "notes": [60, 62, 64, 65, 67, 69, 71, 72, 60, 62, 64, 65, 67, 69, 71, 72],
    "gates": [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
    "velocities": [90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90],
    "lengths_ms": [200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200],
    "bpm": 94.0,
    "midi_offset": 0,
    "swing": 0,
    "notes_lane": {"shape": 1, "speed": "16n", "steps": 16, "direction": "forwards", "phase_beats": 0.0},
    "gates_lane": {"shape": 1, "speed": "16n", "steps": 16, "direction": "forwards", "phase_beats": 0.0},
    "velocities_lane": {"shape": 1, "speed": "16n", "steps": 16, "direction": "forwards", "phase_beats": 0.0}
  }
}
```

### Previsione melodica (`snake_sequence.predict`)
Il modulo Python `src/desnivel/adapters/snake_sequence.py` usa questi snapshot per prevedere gli attacchi, le altezze e le durate delle note future generate da Snake su una finestra temporale (es. 4 beat). In questo modo il generatore del basso conosce in anticipo gli eventi melodici e può comporre linee di risposta e contrappunto sincronizzate.

---

La previsione richiede swing zero, Shift = 1 sulle tre lane, direzioni `forwards` o `backwards` e velocità `32n`, `16n`, `8n`, `4n` o `2n`. Il calcolo presuppone che BPM e parametri di Snake restino invariati durante i beat previsti.

## Acquisizione delle sessioni

Per salvare gli snapshot del sequencer in JSONL:

```sh
python -m desnivel.cli.capture_snake --seconds 180 --label "sessione_studio"
```

Per acquisire anche i piani del basso usare `python -m desnivel.cli.live_bass --capture`. Non avviare `capture_snake` e `live_bass` insieme: usano entrambi la porta 9003.

I dati vengono salvati in una directory temporanea esterna alla repository, preservando la cronologia degli eventi e dei beat.

