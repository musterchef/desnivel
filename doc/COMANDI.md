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
| **9007** | Controllo dei componenti Snake, con Receive iniziale 9201 per il primo componente. | [Snake multiruolo](SNAKE.md#componente-multiruolo) |
| **9006** | Server della sessione multivoce e ricevitore diagnostico Voice, da usare separatamente. | [Sessione multivoce](SESSIONE-MULTIVOCE.md) |
| **9101–9104** | Ricezione manuale delle quattro istanze Voice nel banco di esempio. | [Device Voice](VOCE-M4L.md) |

Nella sessione guidata i controlli annunciano la presenza sulla porta **9006**
e scelgono una porta Receive per istanza; le associazioni sono gestite dal terminale.

Il pannello web e la mappa usano HTTP sulla porta **8765** quando avviati dal launcher
multitappa; `--view-port` permette di cambiarla.

---

`capture_snake` e `live_bass` usano entrambi la porta 9003 e non possono essere avviati insieme. Per registrare mentre il basso suona, usare `live_bass --capture`.

## Operazioni e launcher principali

### Sessione multivoce con scelta della tappa

Aprire `comandi/09 - Sessione multitappa.command` dal Finder, scegliere
una sessione salvata oppure `0` per crearne una con un nome, poi inserire
una tappa da `01` a `12` oppure premere `O` per aprire subito un file FIT o
GPX.
Per provare una formazione, creare una sessione e aggiungere le voci dal
flusso guidato. Ogni sessione conserva il proprio organico; non è richiesto
un numero fisso di tracce. Il comando
`comandi/10 - Prova formazione armonica.command` apre lo stesso flusso del
comando 09.
Le tappe numerate usano i file disponibili nel progetto.

Il menu elenca le configurazioni in `output/sessioni/` e il file
`output/sessione.json` quando presente. Le nuove sessioni partono senza voci
e **V** le salva in `output/sessioni/<nome>.json`. `--config <file>` carica
direttamente una configurazione; **A: apri file…** nel menu permette
di sceglierla dal dialogo macOS. Il launcher usa il timing `allocated`
e la mappa sulla porta `8765`. Dal terminale, nella radice del progetto:

```sh
.venv/bin/python -m desnivel.cli.launch_stage --tappa 05
```

Senza `--tappa` viene riutilizzato il viaggio salvato nella sessione; se il
riferimento manca, la scelta è interattiva. **V** salva anche il viaggio
attivo. `--tappa O` permette di aprire un altro FIT/GPX per la sessione.
Gli altri argomenti sono inoltrati
a `desnivel.cli.ensemble`; per esempio `--view-port 8766` cambia la porta
dell'interfaccia web. `--no-terminal` disabilita tastiera e pannello del terminale
durante l'esecuzione. Il controllo web è su <http://127.0.0.1:8765/session/>,
la mappa su <http://127.0.0.1:8765/>.
La selezione della traccia è gestita da `cli.launch_stage`;
il `.command` imposta la directory del progetto e avvia il comando Python.
Collegamento dei device, controlli e comportamento del replay sono descritti
in [Sessione multivoce Python](SESSIONE-MULTIVOCE.md).

A Live fermo, **A** apre la procedura per associare una traccia con controllo
Desnivel e creare la voce; **B** ricollega una voce esistente, **T** ripete
la ricerca e **V** salva. La schermata mostra tracce e domanda corrente;
**D** apre i dettagli. I comandi testuali con `:` e il tasto **N** restano disponibili.
Comandi, costruzione dei device e configurazione sono descritti in
[Sessione guidata](SESSIONE-GUIDATA.md). L’organico a quattro voci resta
caricabile con `--config presets/organico.json`.

### Banchi di prova separati

Anche questi launcher in `comandi/` usano l'ambiente virtuale `.venv`:

- **`08 - Scegli assetto basso.command`**: avvia il generatore del basso con scelta interattiva tra gli assetti `sobrio`, `dialogo` e `ritmico`.
- **`05 - Acquisisci Export Snake.command`**: registra gli stati esportati da Snake in un file JSONL temporaneo.
- **`04 - Snake - sequenza di riferimento.command`**: imposta una sequenza neutra di partenza su Snake.

Per il banco Snake e il basso collegato, consultare [Snake](SNAKE.md) e [Basso](BASSO.md).

---

## Suite di test

Verifica completa dei componenti Python e degli script JavaScript di Max for Live:

```sh
# Test suite Python
.venv/bin/python -m pytest -q

# Test JavaScript dei device e del viewer
for test_file in tests/js/*.cjs; do
  node "$test_file" || exit 1
done
```
