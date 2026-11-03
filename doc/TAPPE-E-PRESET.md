# Tappe, percorsi modali e preset musicali

Questa guida riguarda il banco Snake, avviato con `desnivel.cli.trip_music`,
e il basso che ne legge la melodia. La sessione principale a quattro voci
usa invece la [direzione automatica del percorso](DIREZIONE-MUSICALE.md)
e si avvia dal [launcher multitappa](COMANDI.md#sessione-multivoce-con-scelta-della-tappa).

Nel banco Snake, i preset combinano:

1. **Dinamica fisica**: velocità e sforzo estratti dalla traccia GPX che determinano densità ritmica e numero di gate attivi.
2. **Evoluzione armonica del territorio**: sezioni geografiche che attraversano scale e modi diversi (dorico, frigio, lidio, pentatonico).

---

## Interpretazione dei dati del viaggio

Tre preset determinano come le grandezze fisiche influenzano la generazione:

| Preset | Sorgente | Effetto sonoro |
|---|---|---|
| **`presets/movimento.json`** | Velocità del ciclista | Più si pedala veloci, più la sequenza si fa densa; i rallentamenti diradano il ritmo. |
| **`presets/sforzo.json`** | Stima di sforzo (pendenza + velocità) | Uno sforzo stimato maggiore apre più gate, anche a basse velocità in salita. |
| **`presets/misto.json`** | 60% movimento, 40% sforzo | Bilanciamento naturale tra la spinta del passo e la fatica delle salite. |

---

## Le tappe e i percorsi modali

Levanto è suddivisa in tre sezioni (0%, 30% e 75% della distanza); Firenze, Sabaudia e Peschici in quattro (0%, 25%, 55% e 80%). Al passaggio tra una sezione e l'altra, il motore modula le scale consentite e l'adattatore sceglie casualmente il percorso dei Gates nella matrice (Shape):

### 1. Levanto – La Spezia (`presets/tappe/levanto_la_spezia.json`)
- **Carattere**: litorale ligure, salite brevi e ritorni ciclici.
- **Percorso delle scale**: La pentatonica minore ──► La minore (con inserimento di Si e Fa) ──► La pentatonica minore.
- **Densità gate**: 3 – 10 note attive.

### 2. Firenze – San Gimignano (`presets/tappe/firenze_san_gimignano.json`)
- **Carattere**: mobile, mosso da salite collinari e cambi di colore armonico.
- **Percorso delle scale**: Re dorico ──► Re misolidio ──► Re minore ──► Re dorico.
- **Densità gate**: 4 – 11 note attive.

### 3. Sabaudia – Formia (`presets/tappe/sabaudia_formia.json`)
- **Carattere**: disteso, luminoso, associato al litorale tirrenico.
- **Percorso delle scale**: Do pentatonico maggiore ──► Do maggiore ──► Do lidio ──► Do pentatonico maggiore.
- **Densità gate**: 3 – 8 note attive.

### 4. Peschici – Mattinata (`presets/tappe/peschici_mattinata.json`)
- **Carattere**: teso, aspro, denso di dislivelli nel promontorio del Gargano.
- **Percorso delle scale**: Mi minore ──► Mi frigio ──► Mi dorico ──► Mi minore.
- **Densità gate**: 4 – 12 note attive.

---

## Regole basate sulla quota (`presets/quota.json`)

Oltre alla suddivisione per sezioni chilometriche, è possibile modulare la musica tramite una regola a soglia altimetrica:
- **Sotto i 200 metri**: pattern rado (4 note su 16) con registro grave.
- **Sopra i 200 metri**: pattern più denso (8 note su 16) e melodia più acuta.
- **Isteresi (margine di 15 m)**: il passaggio da alto a basso scatta sotto i 185 m, e da basso ad alto quando la quota raggiunge o supera i 215 m, evitando continue oscillazioni quando si pedala attorno alla quota limite.

```sh
python -m desnivel.cli.trip_music \
  --gpx gpx/tappa04_Levanto_La_Spezia.gpx \
  --rules presets/quota.json \
  --speed 50
```

---

## Guida all'ascolto

### Ascolto della melodia (Replay della tappa)
Con Ableton Live avviato e bridge caricato sulla traccia di Snake:

```sh
# Esempio: Firenze – San Gimignano a velocità 50×
python -m desnivel.cli.trip_music \
  --gpx gpx/tappa05_Firenze_San_Gimignano.gpx \
  --stage-music presets/tappe/firenze_san_gimignano.json \
  --preset presets/misto.json \
  --speed 50 \
  --seed 7
```

Il flag `--seed 7` garantisce la ripetibilità delle Shape estratte nelle sezioni.  
Aggiungendo `--dry-run` è possibile visualizzare l'elenco cronologico di tutte le decisioni musicali a terminale senza trasmettere via rete.

### Ascolto combinato: Melodia e Basso generativo
Preparare i device come descritto in [BASSO.md](BASSO.md#esecuzione-in-ableton-live-device-m4l), attivare Export e avviare il trasporto di Live. Per ascoltare melodia e basso:

1. **Terminale 1 (Basso)**:
   ```sh
   ./comandi/08\ -\ Scegli\ assetto\ basso.command dialogo
   ```
2. **Terminale 2 (Melodia del viaggio)**:
   ```sh
   python -m desnivel.cli.trip_music \
     --gpx gpx/tappa05_Firenze_San_Gimignano.gpx \
     --stage-music presets/tappe/firenze_san_gimignano.json \
     --preset presets/misto.json \
     --speed 50 \
     --seed 7
   ```

Il basso ascolta la melodia via OSC (porta 9003) e programma i propri eventi sul trasporto di Live (porta 9004), creando un dialogo vivo e sincronizzato per tutta la durata del viaggio.

---

## Analisi automatica della tappa

Per suggerire un assetto iniziale del basso dai pattern generati per una tappa:

```sh
python -m desnivel.cli.analyze_bass \
  --gpx gpx/tappa05_Firenze_San_Gimignano.gpx \
  --stage-music presets/tappe/firenze_san_gimignano.json \
  --preset presets/misto.json
```

L'analisi misura quanti gate sono aperti e quanto cambia questo numero lungo la tappa, dando più peso ai pattern che durano più a lungo. Da questi dati propone densità, sincopazione, articolazione e variazione. Registro e mobilità restano quelli di `responsive`. Stampa un comando da provare, senza inviarlo a Live.

