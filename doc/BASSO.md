# Generatore del basso

`desnivel.music.bass` compone una linea di basso da una frase melodica.
È usato dalla sessione multivoce e dal banco di prova collegato a Snake.

---

## Logica compositiva

La composizione avviene tramite la funzione `generate_bass` (`src/desnivel/music/bass/generator.py`), che riceve una `Phrase` melodica e produce una nuova `Phrase` per il basso articolata su tre scelte:

### 1. Attacchi e ritmo (`_rhythm`)
- **Densità (`density`)**: numero desiderato di note per beat.
- **Sincopazione (`syncopation`)**: preferenza per gli appoggi sul battere (0.0) o per gli accenti in levare (1.0).
- **Legame ritmico (`rhythm_follow`)**: a valori bassi il basso tende a entrare tra gli attacchi della melodia; a valori alti tende a suonare insieme a essa. Il controllo modifica anche durate e accenti.
- **Spaziatura minima (`min_spacing`)**: garantisce una distanza minima tra note consecutive (es. 0.5 o 1 beat).

La densità è un obiettivo: griglia, attacchi sorgente e spaziatura minima
limitano il numero realizzabile. Aumentarla oltre quel limite non aggiunge
note; con `rhythm_follow = 1` i candidati sono soltanto gli attacchi sorgente.

`plan_bass` restituisce la stessa frase insieme al riepilogo della selezione
ritmica. La sessione lo usa per mostrare attacchi selezionati, capacità e
saturazione della **densità richiesta**; `generate_bass` restituisce soltanto
la frase. Il riepilogo riguarda la composizione prima della presenza.

### 2. Altezze e salienza armonica (`_salience`, `_pitches`)
- **Salienza**: analizza la frase melodica pesando durata, dinamica e posizione metrica di ogni nota per individuare l'appoggio armonico più solido.
- **Legame melodico (`melody_follow`)**: bilancia la coerenza con l'appoggio armonico generale (valori bassi) e l'attrazione verso l'altezza melodica più vicina (valori alti).
- **Mobilità (`mobility`)**: a valori bassi favorisce la vicinanza alla nota precedente; a valori alti favorisce un registro più basso sui beat interi e più alto tra i beat.
- **Registro (`lowest`, `highest`)**: limiti MIDI inclusivi per definire l'estensione dello strumento (es. 28–47 per un registro profondo).

### 3. Durate e dinamica (`_articulate`)
- **Articolazione (`articulation`)**: frazione di durata occupata dal suono prima dell'attacco successivo (staccato vs sostenuto).
- **Variazione (`variation`)**: introduce variazioni controllate nella scelta degli attacchi e delle altezze.

---

## Preset principali

I controlli sono raggruppati in preset di partenza:

`strategy` seleziona questi valori alla costruzione di `BassSettings`.
Nella sessione multivoce si usa solo in `settings`: non è un parametro
musicale applicabile alle sezioni. I preset del device sono insiemi dei
sette controlli esposti, distinti dai preset iniziali del generatore.

| Preset | Densità | Sincopi | Legame ritmico | Legame melodico | Mobilità | Articolazione | Carattere sonoro |
|---|---:|---:|---:|---:|---:|---:|---|
| **`responsive`** | 0.8 | 0.25 | 0.35 | 0.25 | 0.15 | 0.90 | Dialogo naturale, appoggi morbidi, movimento misurato. |
| **`slap`** | 1.8 | 0.70 | 0.15 | 0.50 | 0.85 | 0.50 | Note corte, sincopato, salti verso l'acuto e ritmo incalzante. |
| **`follow`** | 4.0 | 0.00 | 1.00 | 1.00 | 0.00 | 0.90 | Segue ritmo e note della melodia nel registro del basso, saltando gli attacchi troppo ravvicinati. |

---

## Assetti operativi di ascolto (Launcher 08)

Per l'ascolto immediato durante il replay delle tappe, il launcher `08 - Scegli assetto basso.command` mette a disposizione tre configurazioni collaudate:

- **`sobrio`**: registro profondo (28–47), densità contenuta (0.6), appoggio solido e non invadente.
- **`dialogo`**: registro esteso (28–55), densità 1.0, risposte contrappuntistiche negli spazi melodici.
- **`ritmico`**: basato sul preset `slap`, registro fino a 59, dinamica percussiva e accenti in levare.

```sh
# Avvio con scelta interattiva da menu
./comandi/08\ -\ Scegli\ assetto\ basso.command

# Oppure avvio diretto con sovrascrittura di un parametro
./comandi/08\ -\ Scegli\ assetto\ basso.command dialogo --density 0.8
```

---

## Controllo in tempo reale (Live OSC)

Durante l'esecuzione, il processo `live_bass` accetta comandi OSC sulla porta **9003** per modificare i parametri musicali al volo senza fermare l'esecuzione:

- **Indirizzo**: `/desnivel/v1/bass/control`
- **Payload**: stringa JSON con numerazione seriale e parametri di destinazione.

```json
{
  "version": 1,
  "serial": 1,
  "parameters": {
    "density": 0.9,
    "articulation": 0.65,
    "mobility": 0.4
  },
  "transition_windows": 4
}
```

### Transizioni fluide
`transition_windows` indica quante frasi servono per passare gradualmente ai nuovi valori. Il valore predefinito è 4: con frasi di quattro beat, il passaggio dura 16 beat. Con valore 0 o prima del primo piano, il cambio è immediato. Anche `seed`, `grid` e `variation_period` cambiano subito.

---

## Esecuzione in Ableton Live (Device M4L)

Per sincronizzare il basso al trasporto di Live:
1. Costruire i device Max for Live in una cartella di output nuova:
   ```sh
   python tools/build_live_bass.py \
     --source "$HOME/Music/Ableton/User Library/MaxForLive/MDD___SNAKE_V3.2.3.amxd" \
     --output /tmp/desnivel-live-bass
   ```
2. Caricare il device generato `MDD_SNAKE_LengthBank.amxd` sulla traccia melodica e `Desnivel_Bass.amxd` sulla traccia del basso prima del sintetizzatore o campionatore. Attivare **Export** su una sola istanza Snake.
3. Avviare il ricevitore Python:
   ```sh
   python -m desnivel.cli.live_bass --preset responsive
   ```

Il processo Python ascolta lo stato di Snake sulla porta 9003, genera il piano della frase e lo invia a `Desnivel_Bass.amxd` sulla porta **9004** (`/desnivel/v1/player/bass/plan`). Il device Max for Live programma gli eventi sul beat di Live tramite l'oggetto `timepoint`.

Il piano viene inviato come stringa JSON:

- `version`: 1.
- `session`, `serial`, `revision`: identificativi della sessione, del messaggio e della revisione del piano.
- `start`: posizione di inizio sul trasporto di Live, in beat.
- `phrase`: lunghezza della frase (`length_beats`) ed elenco delle note (`notes`). Ogni nota contiene attacco rispetto all'inizio della frase (`beat`), altezza MIDI (`pitch`), durata in beat (`duration`) e intensità (`velocity`).

Un beat è una semiminima. Per cancellare i piani e spegnere le note, il messaggio contiene `version`, `session`, `serial` e `reset: true`.

Con i valori predefiniti (`--window 4 --lead 1`), il basso prepara frasi di quattro beat. Ogni frase inizia a un multiplo di quattro beat, con almeno un beat di anticipo rispetto alla posizione ricevuta da Snake. Dopo la ricarica di Snake, riavviare `live_bass`.
