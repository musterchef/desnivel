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

Commit della riorganizzazione:

- `ec22358` — `riorganizzazione dei ruoli musicali e armonia`

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

Il preset [prova-formazione.json](presets/prova-formazione.json) contiene
quattro voci: melodia, basso, armonia principale e armonia accompagnante.
Il comando [10 - Prova formazione armonica.command](comandi/10%20-%20Prova%20formazione%20armonica.command)
usa lo stesso menu sessioni del comando 09. Scegliere **P** crea una
sessione nominata dalla formazione di prova in `output/sessioni/`; il
viaggio e l’avvio mantengono il flusso della sessione manuale.

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

La nuova formazione di prova invece contiene solo quattro voci armoniche:
non include drums e richiede quindi quattro tracce MIDI con device Desnivel.
Riattivarli in quella prova significa aggiungere una voce ritmica distinta
(e una quinta traccia), oppure sostituire una delle quattro parti. Questa
scelta non è stata fatta; non modificare l’organico della prova senza
conferma. Non confondere il ruolo `rhythm`, la voce percussiva, il generatore
`percussion_phrase` o `percussion_pattern`, e Snake: sono componenti distinti.

## Prossime verifiche e decisioni

1. Decidere se la prova deve avere una quinta voce drums oppure restare a
   quattro tracce sostituendo una parte. Se aggiunta, scegliere se usare il
   generatore percussivo sviluppato già presente in `organico` o un pattern
   autonomo; definire sorgenti e stile iniziale senza duplicare controlli.
2. Provare in Live le quattro parti armoniche e verificare all’ascolto
   registro, volume, articolazione e comportamento dell’armonia sui cambi
   della melodia.
3. Decidere se il modello futuro deve includere una progressione armonica,
   distinta dal contesto attuale di tonica e scala per sezione.

La sessione personale eventualmente salvata in `output/sessioni/` non fa
parte del repository né del commit. Per la prova corrente, se l’armonia
principale deve seguire la melodia, riconfigurare la voce con **accordi sui
cambi di una voce**, poi selezionare la melodia come sorgente e salvare.
