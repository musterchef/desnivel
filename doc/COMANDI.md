# Comandi e configurazione

## Ambiente di sviluppo

Dalla radice del progetto:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

---

## Streaming e lettura delle metriche

Mostra un'anteprima dei messaggi OSC, senza inviarli:

```sh
desnivel-stream-metrics --gpx gpx/tappa04_Levanto_La_Spezia.gpx --dry-run
```

Trasmissione continua via OSC a velocità 30×:

```sh
desnivel-stream-metrics --gpx gpx/tappa04_Levanto_La_Spezia.gpx --speed 30
```

Opzioni utili:
- `--loop`: ripete il viaggio ciclicamente.
- `--osc-host` e `--osc-port`: configurano host e porta di trasmissione (predefinito: `127.0.0.1:9000`).

---

## Porte di rete predefinite

| Porta UDP | Flusso dati | Riferimento |
|---|---|---|
| **9000** | Pubblicazione delle metriche fisiche del viaggio. | [Dati del viaggio](DATI-VIAGGIO.md) |
| **9001** | Controllo dei parametri di Snake in Live. | [Sequencer Snake](SNAKE.md) |
| **9002** | Invio di frasi predefinite per il player ciclico. | [Player M4L](BASSO.md) |
| **9003** | Telemetria dello stato di Snake (`/desnivel/v1/snake/state`) e controlli live del basso (`/desnivel/v1/bass/control`). | [Snake](SNAKE.md), [Basso](BASSO.md) |
| **9004** | Piani di esecuzione per il basso sincronizzato al trasporto di Live. | [Basso in Live](BASSO.md) |

---

`capture_snake` e `live_bass` usano entrambi la porta 9003 e non possono essere avviati insieme. Per registrare mentre il basso suona, usare `live_bass --capture`.

## Operazioni e launcher principali

### Sessione multivoce con scelta della tappa

Aprire `comandi/09 - Sessione multitappa.command` dal Finder e inserire
una tappa da `01` a `12`, oppure `07bis` per il FIT ricostruito da Komoot.
Le tappe numerate usano i GPX in `gpx/`; `07bis` richiede il file locale
`output/ricostruzione-tappa07/tappa07_Roma_Sabaudia.fit`.

La variante integra 1.052 punti con posizione, quota e orario dal GPX Komoot
nel tratto Roma–Ciampino. Conserva i record, gli eventi timer e i riepiloghi
del FIT originale; questi ultimi non sono ricalcolati. Restano lacune nei
campioni disponibili, che possono produrre salti nella mappa e nel replay.
La provenienza dei punti aggiunti è in
`output/ricostruzione-tappa07/provenienza.json`. La cartella `output/` è
esclusa da Git: per usare `07bis` su un'altra copia del progetto occorre
trasferire anche questi file.

Il launcher usa `presets/organico.json`, il timing `allocated` e la mappa
sulla porta `8765`. Dal terminale, nella radice del progetto:

```sh
.venv/bin/python -m desnivel.cli.launch_stage --tappa 07bis
```

Senza `--tappa` la scelta è interattiva. Gli altri argomenti sono inoltrati
a `desnivel.cli.ensemble`; per esempio `--view-port 8766` cambia la porta
della mappa. La selezione della traccia è gestita da `cli.launch_stage`;
il `.command` imposta la directory del progetto e avvia il comando Python.
Collegamento dei device, controlli e comportamento del replay sono descritti
in [Sessione multivoce Python](SESSIONE-MULTIVOCE.md).

I launcher a doppio clic per macOS si trovano in `comandi/` e usano automaticamente l'ambiente virtuale `.venv`:

- **`08 - Scegli assetto basso.command`**: avvia il generatore del basso con scelta interattiva tra gli assetti `sobrio`, `dialogo` e `ritmico`.
- **`05 - Acquisisci Export Snake.command`**: registra gli stati esportati da Snake in un file JSONL temporaneo.
- **`04 - Snake - sequenza di riferimento.command`**: imposta una sequenza neutra di partenza su Snake.

Per l'ascolto completo delle tappe e dei percorsi modali, consultare la [Guida alle tappe e preset](TAPPE-E-PRESET.md).

---

## Suite di test

Verifica completa dei componenti Python e degli script JavaScript di Max for Live:

```sh
# Test suite Python
pytest -q

# Test unitari JavaScript Max for Live
node tests/js/phrase_player.cjs
node tests/js/snake_params.cjs
node tests/js/snake_state.cjs
node tests/js/transport_player.cjs
```
