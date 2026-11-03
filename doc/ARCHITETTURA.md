# Architettura del sistema

Desnivel adotta un'architettura a pipeline modulare con separazione rigorosa tra:
1. **Dati fisici del viaggio** (oggettivi, neutrali e indipendenti dall'estetica).
2. **Interpretazione compositiva** (regole musicali, scale, contrappunto e dinamica).
3. **Adattamento e trasporto** (traduzione nei formati e protocolli di destinazione).
4. **Esecuzione sonora** (generazione audio, sintesi o sequencer nella destinazione finale; attualmente Ableton Live e Max for Live costituiscono il primo banco di prova operativo).

---

## Flusso generale

```text
Traccia FIT/GPX ──► [trip] Metriche neutre ──► [music] Generazione musicale ──► [adapters] ──► [sinks] ──► Destinazioni (DAW / Synth / MIDI / OSC)
```

| Modulo | Responsabilità | Package |
|---|---|---|
| **Analisi del viaggio** | Legge FIT e GPX, seleziona i tratti osservati, ricampiona ciascun tratto e calcola distanza, quota, pendenza, velocità e stima di sforzo. | `src/desnivel/trip/` |
| **Generazione musicale** | Applica le scelte compositive: traduce metriche in pattern, governa l'armonia, genera frasi musicali e relazioni polifoniche tra le voci. | `src/desnivel/music/` |
| **Adattatori** | Converte strutture musicali astratte (`Pattern`, `Phrase`) nei parametri specifici dei dispositivi o protocolli di destinazione. | `src/desnivel/adapters/` |
| **Trasporto** | Gestisce la trasmissione dei messaggi via rete (es. OSC) e il salvataggio dei log di acquisizione. | `src/desnivel/sinks/` |
| **Interfaccia CLI** | Entry point eseguibili da riga di comando o tramite launcher per orchestrare replay, analisi e sessioni. | `src/desnivel/cli/` |
| **Vista della sessione** | Serve mappa e dashboard; legge lo snapshot e accoda i comandi al ciclo della sessione. | `src/desnivel/viewer/` |
| **Integrazioni attive** | Device MIDI comune per la prova multivoce, registrazione Live e bridge dei banchi Snake e basso. | `m4l/` |

---

## Principi architetturali fondamentali

### 1. Separazione tra tempo del viaggio e tempo musicale
Ableton Live fornisce beat, BPM e stato Play/Stop. Nel replay lineare il
viaggio avanza in secondi con un fattore di velocità; nella modalità allocata
le macrosezioni ricevono finestre in beat. Cambiare BPM modifica la durata
reale dell'ascolto allocato, senza cambiare i beat assegnati.
I cambi dei parametri del banco Snake non sono quantizzati a battuta.

### 2. Neutralità delle metriche
`trip` legge tracce e sorgenti ambientali, calcola metriche e classifica
il profilo. Mantiene separati tratti osservati, interruzioni e dati mancanti.
Le interpretazioni musicali appartengono a `music`; `cli` collega gli
interpreti ai dati e ai generatori.

### 3. Modelli musicali condivisi
La generazione musicale si basa su due strutture dati fondamentali:
- **`Pattern`**: sequenza di passi, ciascuno con una nota e un gate. `PatternChange` indica quando applicarla durante il viaggio.
- **`Phrase`**: insieme polifonico di eventi sonori, in cui ogni nota specifica attacco relativo (in beat), altezza MIDI (0–127), durata (in beat) e velocity (1–127).
- **Piano di esecuzione**: messaggio preparato da `adapters/snake_live.py` per il player Live. Contiene la frase da eseguire, il beat di inizio e gli identificativi di sessione, messaggio e revisione.

---

## Music Director e Music Coordinator

I due ruoli sono implementati in classi distinte nel package `music`: il Director seleziona il contesto compositivo, il Coordinator pianifica le voci a partire dalle frasi disponibili.

- **`MusicDirector`** (`music/director.py`): riceve le sezioni configurate e seleziona, dalla progressione del viaggio, un `MusicalContext` con indice e nome della sezione, tonica e scala. `journey.compose` usa questo contesto per generare i pattern; motivo, gate e trasformazioni dei gradi restano nella composizione della voce.
- **`MusicCoordinator`** (`music/coordinator.py`): riceve generatori identificati per voce e le rispettive dipendenze. Verifica dipendenze mancanti o cicliche prima della generazione, ordina le chiamate e raccoglie le frasi. Ogni generatore riceve un `PlanningRequest` con intervallo in beat, eventuale contesto comune e frasi delle sole dipendenze dichiarate. Il chiamante può fornire frasi sorgente già pianificate.
- **Moduli delle voci** (`music/<voce>/`): contengono regole compositive, controlli e stato specifici della voce. Il planner presente in `music/bass/` conserva continuità e transizioni dei controlli per quel generatore.
- **Adattatori**: traducono stato delle sorgenti e risultati musicali nei formati di destinazione; gestiscono identificativi, revisioni, trasporto e conferme dei dispositivi. Il collegamento di generatori e Coordinator è governato dai comandi in `cli`.

Il Director legge anche le assegnazioni manuali delle voci per sezione. Il Coordinator verifica i ruoli supportati e passa ruolo e parametri ai generatori. `cli/ensemble.py` collega queste assegnazioni a generatori e destinazioni registrati dal chiamante. Il Coordinator propaga il contesto fornito dal chiamante senza interpretarlo. Nella sessione multivoce ogni generatore riceve il contesto delle sezioni; il generatore di accompagnamento compone dalla frase fornita come dipendenza. L’integrazione `live_bass` usa invece una frase ricostruita dalla sorgente esterna. La [sessione multivoce](SESSIONE-MULTIVOCE.md) include vista globale e dettaglio delle decisioni di pianificazione.

---

## Organizzazione delle cartelle

- `src/desnivel/`: codice sorgente Python del pacchetto.
  - `music/<voce>/`: ogni voce o strumento ha una sottocartella dedicata (es. `music/bass/`).
- `tests/`: test automatici, speculari alla struttura di `src/`.
- `m4l/`: sorgenti e patch Max for Live (`.amxd`, `.js`, `.maxpat`).
- `tools/`: script per la costruzione e l'ispezione dei device Max for Live.
- `presets/`: configurazioni musicali delle tappe e delle regole.
- `fit/`, `gpx/`: registrazioni delle tappe nei due formati; il FIT conserva gli eventi timer.
- `comandi/`: launcher macOS per l'avvio rapido delle sessioni di ascolto.
- `doc/`: documentazione del sistema. I documenti storici o superati sono conservati in `doc/archivio/`.

---

## Riferimenti

- [Voci e contesto musicale](RUOLI-MUSICALI.md)

- [Dati del viaggio e metriche GPX](DATI-VIAGGIO.md)
- [Sequencer Snake e ponte M4L](SNAKE.md)
- [Generatore del basso e controlli](BASSO.md)
- [Tessitura sostenuta e relazione con la sorgente](TESSITURA.md)
- [Setup e comandi operativi](COMANDI.md)

