# Progressioni armoniche autonome

Stato: catalogo iniziale implementato; evoluzioni successive da validare
all'ascolto prima di essere progettate o implementate.

## Obiettivo

Permettere a una voce con ruolo `harmony` di guidare il movimento armonico
senza dipendere da una melodia. La capacità non sostituisce l'armonia di
sezione: un accordo statico, una nota ripetuta e il sostegno a una sorgente
restano comportamenti distinti.

## Base implementata

`HarmonicProgressionGenerator` in `music/texture/progression.py` percorre
una lista ordinata di passi `{degree, beats}`. Ogni passo realizza una triade
diatonica nella tonica e scala della sezione; al termine dell'ultimo passo il
ciclo riparte. Un cambio di sezione ricomincia dal primo passo nel nuovo
contesto armonico.

La scelta guidata **progressione autonoma** offre i cicli `0–5–3–4`,
`0–3–4–0` e `0–4–5–3`, con otto beat per passo. Il controllo `progression`
seleziona il ciclo attivo. Non ha sorgenti o dipendenze. Il generatore
prepara lo stato in `stage` e lo applica in `accept`, quindi retry, reset e
pianificazione multivoce mantengono le stesse garanzie degli altri generatori.

La realizzazione delle triadi è condivisa con `TextureGenerator` tramite
`music/texture/voicing.py`; non esistono due interpretazioni dei gradi della
scala.

## Roadmap

### 1. Ascolto e consolidamento della base

- Provare la progressione lenta con armonia e drums, mantenendo fissi timbro,
  percorso e tempo.
- Verificare che il ciclo sia percepibile, che il cambio di sezione non sia
  arbitrario e che il riavvio della sessione riproduca il risultato.
- Correggere soltanto problemi osservati nella generazione o nella
  realizzazione del pad.

Completamento: una prova approvata definisce il ciclo iniziale come uscita di
riferimento; i test di frase e sessione restano verdi.

### 2. Catalogo di cicli espliciti — implementato inizialmente

- I cicli sono dati nominati, non rami nel coordinatore: ogni ciclo resta una
  sequenza di passi `degree` e `beats`.
- Il controllo `progression` seleziona il ciclo senza richiedere l'editing
  manuale del JSON nella sessione guidata.
- Il ciclo selezionato è serializzabile nella configurazione della sessione.

Completamento: due o più cicli con identità musicale distinta, riproducibili
e testati su più scale.

### 3. Realizzazione e continuità armonica

- Aggiungere, solo se l'ascolto lo richiede, scelte di voicing e inversione
  che riducano salti inutili tra accordi.
- Tenere la selezione dei gradi separata dalla disposizione delle note.
- Conservare limiti MIDI, durata entro la finestra e determinismo.

Completamento: una nuova realizzazione dimostra continuità migliore senza
modificare la progressione scelta né il comportamento della tessitura statica.

### 4. Forma armonica

- Definire cicli con apertura, sviluppo e conclusione, anziché soli loop.
- Aggiungere cadenze soltanto come comportamento dichiarato di una
  progressione; non imporre finali tonici a tutte le voci armoniche.
- Collegare eventuali cambi di forma alle sezioni musicali già risolte dal
  Director.

Completamento: una forma completa è ascoltata su percorsi riproducibili e
resta comprensibile nella configurazione.

### 5. Relazioni con percorso e altre voci

- Valutare se il percorso debba scegliere un ciclo, modificarne il ritmo o
  soltanto selezionare il contesto tonale.
- Valutare risposte a gesti musicali conclusi solo quando esiste un caso
  d'ascolto concreto; le dipendenze della finestra corrente restano un DAG e
  le relazioni storiche leggono soltanto piani accettati.

Completamento: ogni relazione indica sorgente, bersaglio, ambito temporale e
regola musicale verificabile.

## Confini

- Il Coordinator non sceglie accordi e non contiene regole di stile.
- I device Live ricevono soltanto note e controlli già previsti; non
  interpretano progressioni.
- `sustained_texture` non viene trasformato in un generatore di forma: resta
  una tessitura statica o coordinata.
- Non si introducono casualità, feedback simultanei o progressioni implicite
  finché non esiste una regola musicale e una prova d'ascolto che li motivi.
