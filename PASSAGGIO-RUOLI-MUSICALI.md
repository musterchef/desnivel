# Passaggio di contesto: ruoli musicali, armonia e drums

## Obiettivo

Desnivel è un motore generativo musicale multivoce guidato da GPX. La
formazione di prova serve ad ascoltare il dialogo fra voci; non definisce
un organico fisso per il sistema.

Il modello usa ruoli funzionali: `melody`, `bass_line`, `harmony` e
`rhythm`. Il ruolo descrive la funzione musicale; la realizzazione, il
generatore e il device sono scelte distinte. Una melodia è una linea in
primo piano; l’armonia può essere accordale o monodica e può avere più
parti accompagnanti.

## Lavoro fissato

Commit rilevanti:

- `ec22358` — `riorganizzazione dei ruoli musicali e armonia`
- `e47e955` — `creazione dell’organico nel flusso di sessione`

Il commit aggiorna le configurazioni, i generatori, i controlli, il workflow
di assegnazione e la documentazione. L’assegnazione guidata presenta ruolo,
comportamento ed eventuali sorgenti. Una voce già associata si può
riconfigurare con `:riconfigura` mantenendo il collegamento Live.

`TextureGenerator` realizza accordi diatonici o note singole ripetute.
Con “accordi sui cambi di una voce”, ricava una triade a ogni attacco della
sorgente e la mantiene fino al successivo. “Sostiene una voce” sposta la
realizzazione fuori dal registro della sorgente. Il contesto armonico
disponibile resta quello di tonica e scala della sezione: non è una
progressione di accordi configurabile.

L’organico appartiene alla sessione e si costruisce dal flusso guidato,
aggiungendo le voci e associandole alle tracce Live. Non c’è un numero fisso
di tracce né un organico predefinito da caricare per la prova. Il comando
[10 - Prova formazione armonica.command](comandi/10%20-%20Prova%20formazione%20armonica.command)
usa lo stesso menu sessioni e la stessa preparazione del comando 09; creare
una nuova sessione per comporre una formazione di prova. Il JSON salvato è
lo stato della sessione, mentre le voci vengono scelte nel flusso guidato.
Il setup deriva i generatori guidati dai default dei moduli musicali e dal
catalogo, non dal preset `organico.json`.

Verifica eseguita dopo il commit:

- `.venv/bin/python -m pytest tests/ -q` — suite completa superata.
- `git diff --check` — superato prima del commit.

## Audit dei drums

I drums non sono disattivati globalmente. [organico.json](presets/organico.json)
ha già una voce `voice_04` con generatore `percussion_phrase`, ruolo `rhythm`,
materiale, sorgenti d’interazione, `rhythm_voice` e relazione ritmica con la
melodia. Il generatore supporta stili e sviluppo; la mappa MIDI del Drum Rack
è definita in `src/desnivel/adapters/percussion.py`. La guida degli stili è
in [STILI-PERCUSSIVI.md](doc/STILI-PERCUSSIVI.md).

La sessione può aggiungere una voce con ruolo `rhythm` attraverso lo stesso
flusso guidato: pattern autonomo, groove sviluppato autonomo con stile,
oppure groove in relazione ad altre voci. Le sorgenti vengono associate
esplicitamente solo nella modalità relazionale. Non occorre aggiungere i
drums a un organico globale o scegliere un conteggio fisso di tracce. Non
confondere il ruolo `rhythm`, la voce percussiva, il generatore
`percussion_phrase` o `percussion_pattern`, e Snake: sono componenti distinti.

## Prossime verifiche e decisioni

1. Verificare in Live il groove autonomo e quello relazionale e scegliere
   sorgenti, stile, registro e volume adatti alla formazione composta.
2. Verificare all’ascolto l’articolazione e il comportamento dell’armonia sui
   cambi della melodia.
3. Decidere se il modello futuro deve includere una progressione armonica,
   distinta dal contesto attuale di tonica e scala per sezione.

La sessione personale salvata in `output/sessioni/` non fa parte del
repository né dei commit. Per provare l’armonia principale che segue la
melodia, scegliere **accordi sui cambi di una voce**, selezionare la melodia
come sorgente e salvare la sessione.
