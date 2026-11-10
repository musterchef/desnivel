# Timeline musicale e anteprima dell'allocazione

`music/timeline.py` implementa un'allocazione pura, un piano immutabile e
un manager della posizione logica. L'unità temporale è il beat: non sono
richiesti BPM o durate in secondi. Cambiare il BPM cambia la durata reale
dell'ascolto, non il numero di beat assegnati.

Questi componenti sono collegati all'analisi e al report tramite
`analyze_trip --timeline-session`. La sessione di ascolto `ensemble --timing allocated` usa lo stesso allocatore
e consuma la timeline seguendo i beat del trasporto. `--timing linear`
(predefinito) conserva il replay GPX con `--speed`.

## Responsabilità e interfaccia

```python
allocate_timeline(
    distances_m,
    *,
    target_beats=None,
    beats_per_km=None,
    window_beats,
    min_windows=2,
    distance_exponent=0.5,
) -> Timeline
```

Le distanze sono positive e finite, nell'ordine delle macrosezioni. Il
modulo non legge GPX, famiglie, strumenti, clock o rete. Analisi e
raggruppamento esistenti forniscono le distanze; il chiamante collega gli
indici del piano alle macrosezioni originali.

`Timeline` è un oggetto immutabile con beat richiesti, dimensione della
finestra, minimo, esponente e tupla di `TimelineSpan`. Ogni intervallo
contiene `source_index`, `start_window` e `window_count`; `end_window` è
calcolato. Gli intervalli coprono il piano senza buchi, conservano l'ordine
e rispettano il minimo. Il piano espone `total_windows`, `total_beats`,
`quantized_beats` ed `extended_for_minimum`.

`Timeline.to_dict()` produce una rappresentazione JSON con confini e
durate in beat. `adjustments` distingue:

- `window_quantization`: aumento necessario per avere finestre intere;
- `minimum_extension`: ulteriore aumento necessario per garantire i minimi.

La modalità per chilometri produce soltanto la quantizzazione; se i minimi
non entrano nella durata proporzionale, segnala un errore. L’estensione
automatica resta disponibile con un totale esplicito `target_beats`.

Ogni adattamento riporta `from_beats` e `to_beats`. Il comando stampa gli
avvisi corrispondenti, senza bloccare l'allocazione.

## Allocazione

La durata deriva da una sola fonte, scelta esplicitamente:

- `beats_per_km`: somma delle distanze in km moltiplicata per la scala;
- `target_beats`: durata totale esplicita, indipendente dalla distanza.

Specificare entrambe o nessuna produce un errore. La durata viene
arrotondata verso l'alto a finestre intere. Con `beats_per_km`, se non basta
per i minimi il calcolo si interrompe indicando una scala sufficiente:
non viene allungata automaticamente una tappa in base al numero di sezioni.
Con `target_beats`, il totale viene invece esteso fino a coprire i minimi. Dopo la riserva dei minimi, le finestre residue sono
distribuite con pesi proporzionali a `metri ** distance_exponent`.

Le parti intere delle quote vengono assegnate subito; le finestre rimaste
vanno ai maggiori resti frazionari, con precedenza all'ordine del percorso
in caso di parità. La somma coincide con il budget effettivo. I pesi sono
normalizzati in forma logaritmica per evitare overflow.

L'esponente è finito e non negativo: zero distribuisce il residuo in parti
uguali, 0,5 attenua le differenze metriche, uno le mantiene proporzionali.
Valori superiori a uno le accentuano. Minimo, beat richiesti e ampiezza
della finestra devono essere positivi; il minimo deve essere intero.
Input invalidi o durate non rappresentabili numericamente producono errori.

## Manager

`TimelineManager(timeline)` conserva un cursore intero di finestra,
indipendente dal piano. Due manager possono ispezionare la stessa timeline
senza modificarla e senza condividere la posizione.

| Interfaccia | Comportamento |
|---|---|
| `timeline` | Piano di riferimento, proprietà di sola lettura |
| `window_index` | Posizione corrente, inizialmente zero |
| `current_span` | Intervallo corrente; al confine passa al successivo, alla fine vale `None` |
| `advance()` | Consuma una finestra; dopo la fine produce un errore |
| `seek_window(index)` | Posizionamento esplicito da zero al numero totale di finestre incluso |
| `reset()` | Ritorno alla prima finestra |
| `finished` | Vero alla posizione finale |
| `snapshot()` | Finestra, beat, indice sorgente, finestre rimanenti nella sezione e stato finale |

Il manager non legge né modifica il trasporto di Live, non decide quando
far avanzare la posizione e non invia note. Queste responsabilità restano
al chiamante che ne governa l'avanzamento.

## Configurazione e report

In `presets/organico.json` la sezione `timeline` contiene:

```json
{
  "beats_per_km": 12,
  "min_windows": 2,
  "distance_exponent": 0.5
}
```

La finestra viene letta dal campo `window_beats` della stessa sessione,
attualmente 4. Il minimo di 2 finestre rimane 8 beat per macrosezione.
`beats_per_km` è positivo e finito e sostituisce `target_beats` nella stessa
configurazione; non viene creato un file JSON aggiuntivo.

La scala corrente assegna 12 beat per km al totale della tappa. Il totale
viene arrotondato alla finestra successiva: due distanze molto vicine possono
quindi ottenere lo stesso numero di beat. La distribuzione interna conserva
l'esponente 0,5 e i minimi, quindi i singoli tratti non hanno tutti lo stesso
rapporto beat/km. Il report mostra la scala e la durata effettiva.

```sh
.venv/bin/python -m desnivel.cli.analyze_trip \
  --gpx gpx/tappa05_Firenze_San_Gimignano.gpx \
  --config presets/analisi-percorso.json \
  --grouping presets/macrosezioni-percorso.json \
  --timeline-session presets/organico.json \
  --output output/analisi-percorso.json \
  --html output/analisi-percorso.html
```

`--timeline-session` richiede `--grouping`. L'analisi JSON mantiene zone,
profilo e macrosezioni e aggiunge `timeline` con il piano e la posizione
iniziale del manager. L'HTML usa questi dati senza ricalcolare i pesi.

Nel report la sezione «Timeline musicale in beat» mostra budget, avvisi,
tre barre di quote relative (distanza, tempo lineare GPX e beat allocati), una tabella delle assegnazioni
e un cursore per esplorare le finestre. La navigazione nel browser legge
gli intervalli esportati e non avvia audio o controlla il manager Python.
Selezionare una riga inquadra il tratto nel profilo del percorso.

Nel riquadro «Durata al BPM scelto» si può modificare il BPM (inizialmente
120) per leggere la durata totale, di una finestra e della macrosezione
selezionata. Il calcolo `beat × 60 / BPM` assume tempo costante e arrotonda
al secondo. Valori vuoti, non positivi o non finiti sono segnalati. Il
campo aggiorna soltanto la stima nel browser: non modifica il piano o Live.

Il campo `timeline.linear_reference` proietta le durate delle macrosezioni
nel tempo del `Track` sullo stesso totale di beat della timeline allocata,
senza minimi o quantizzazione. Le proporzioni temporali sono quelle del
replay lineare: una velocità `--speed` uniforme non le modifica. Le soste
iniziali appartengono alla prima sezione; quelle sui confini interni alla
sezione uscente. La tabella confronta beat allocati e beat lineari GPX.

Con i valori confermati per Firenze–San Gimignano il piano contiene
33 macrosezioni, 181 finestre e 724 beat effettivi con la scala di 12 beat/km. L'anteprima non modifica
il rilevamento delle 49 zone né il raggruppamento.


## Ascolto nelle due modalità

Dalla cartella del progetto, per il replay lineare:

```sh
.venv/bin/python -m desnivel.cli.ensemble \
  --gpx gpx/tappa05_Firenze_San_Gimignano.gpx \
  --config presets/organico.json \
  --direction presets/direzione-viaggio.json \
  --timing linear --speed 200
```

Per la timeline allocata:

```sh
.venv/bin/python -m desnivel.cli.ensemble \
  --gpx gpx/tappa05_Firenze_San_Gimignano.gpx \
  --config presets/organico.json \
  --direction presets/direzione-viaggio.json \
  --timing allocated
```

`allocated` richiede una direzione GPX tramite `direction` o `--direction`
e i parametri `timeline` della sessione;
non accetta `--speed`. Aggiungere `--dry-run` verifica configurazione,
allocazione e generazione senza aprire porte o inviare note.

Il runtime mantiene due posizioni: finestre già concluse e finestre inviate
in anticipo. Il manager avanza quando Live raggiunge la fine di una finestra
inviata; l'ultima deve concludersi prima dello stato `finished`. Le sezioni
sono pianificate in ordine, con tutte le finestre assegnate, anche quando
un aggiornamento del trasporto arriva in ritardo. L'inizio dell'ascolto
attende la prima finestra utile con l'anticipo `lead_beats`; tale attesa non
fa parte del budget musicale.

Stop, perdita dei dispositivi e discontinuità cancellano i piani pendenti.
Alla ripresa viene ripianificata per intero la prima finestra non conclusa,
conservando quelle già concluse; non si conserva la frazione di finestra
interrotta. Loop e salti non selezionano una macrosezione dal beat assoluto
di Live. Per ripartire dall'inizio del viaggio si riavvia il processo Python.

Il Director seleziona contesto e assegnazioni usando la progressione iniziale
della macrosezione pianificata; il Coordinator compone la finestra con le
interfacce esistenti. La posizione mostrata nel viaggio interpola la distanza
entro la macrosezione corrente: è una posizione rimappata, non il replay
originale del tempo GPX. Lo stato include `timing` e, in modalità allocata,
`timeline` con posizione, beat richiesti/effettivi e adattamenti del budget.
Il terminale mostra i beat completati rispetto al totale.

L'anticipo di invio lascia concludere le frasi della finestra uscente nei
cambi ordinari. Non implementa chiusure armoniche o dissolvenze, descritte
come proposta in [Mappatura temporale](proposte/percorso/alta/in-corso/MAPPATURA-TEMPORALE.md).
