# Dialogo ritmico multivoce

La sessione può usare le drums come riferimento ritmico e conservare gesti
musicali per influenzare le frasi successive. I generatori mantengono il
proprio materiale, le altezze e le regole di sviluppo.

## Flusso della composizione

1. Il modulo percussivo prepara gli appoggi ritmici della finestra.
2. La melodia compone dal motivo, dal contesto armonico e dalle influenze abilitate.
3. Il basso legge la melodia e può aderire alla guida ritmica.
4. La tessitura sostiene la sezione oppure la frase sorgente, secondo `follow_source`.
5. Le drums completano la propria frase reagendo a melodia e basso.
6. Il Coordinator accetta il piano e aggiorna gesti e osservazioni musicali.

La relazione storica drums → melodia chiude lo scambio: il risultato delle
drums, composto anche in risposta alle altre voci, può influenzare la
melodia successiva. Non cambia retroattivamente le frasi già pianificate.
Le dipendenze nella stessa finestra devono formare un grafo senza cicli.

## Guida e adesione

`rhythm_voice` identifica la voce produttrice. Attualmente il produttore
supportato è `percussion_phrase`. Il suo `prepare_reference` usa
`standard_material`, se presente, altrimenti `material`, ripetuto nella fase
musicale corrente. Per ogni attacco distinto conserva il massimo peso
`velocity / 127`. `RhythmReference` contiene durata della finestra,
lunghezza e fase del ciclo, posizioni e pesi; non contiene altezze MIDI.

Lo stesso materiale prepara anche i colpi strutturali sulle `support_lanes`.
La frase finale li conserva insieme ai complementi reattivi. L'operazione
esplicita `silence`, quando attiva, silenzia anche la struttura. La guida
rimane disponibile se le drums sono silenziate dalla presenza o escluse
dall'organico; il produttore deve comunque essere registrato.

| Controllo | Ambito | Significato |
|---|---|---|
| `groove_follow`, 0…1, iniziale 0 | `motif`, nei ruoli `melody` e `bass_line`; `responsive_line` | Peso della guida ritmica nella collocazione degli attacchi |
| `rhythm_follow`, 0…1 | `responsive_line` | Preferenza per gli attacchi della frase melodica sorgente, nella generazione del basso |

`groove_follow` richiede `rhythm_voice`. Senza produttore il controllo è
segnalato inattivo nel dispositivo e un valore positivo viene rifiutato.
Nel ruolo `sustained_texture` del motivo non ha effetto ed è segnalato inattivo.

I preset utente salvati prima dell'introduzione di `groove_follow` vengono
completati in memoria con valore zero. Lo snapshot espone l'aggiunta in
`preset_migrations`; il file viene aggiornato soltanto salvando il preset.
La migrazione dei preset percussivi è descritta in [Stili percussivi](STILI-PERCUSSIVI.md).
Gli altri controlli mancanti o sconosciuti vengono rifiutati.

La modellazione ritmica avviene dopo la composizione propria della voce.
Mantiene numero e ordine delle note, altezze e velocity. Può spostare ogni
attacco al massimo di mezzo beat, scegliendo fra posizioni originali e
appoggi ricevuti. Conserva attacchi distinti e accorcia le durate quando
necessario per terminare prima della nota successiva o della fine finestra.

I pesi della guida e delle relazioni si sommano; oltre uno vengono
normalizzati. La preferenza per le posizioni originali pesa
`max(0, 1 − somma delle influenze)`. A parità di punteggio prevale lo
spostamento complessivo minore. Le influenze esprimono preferenze: un peso
di uno non impone la copia del pattern né una percentuale esatta di note.

Con guida abilitata (`groove_follow > 0`), se la melodia sorgente è vuota,
il basso usa una tonica nel proprio registro come materiale di sezione,
poi applica i controlli compositivi e ritmici. Con valore zero conserva il
comportamento dipendente dalla sorgente. La dipendenza registrata resta
obbligatoria; una voce assente dall'organico non equivale a una frase vuota.

## Relazioni storiche

`relations` è una lista di configurazioni lette da `EnsembleSession`:

```json
{
  "id": "drums_to_melody",
  "source": "voice_04",
  "target": "voice_01",
  "scope": "history",
  "aspects": ["rhythm"],
  "roles": ["melody"],
  "lookback_beats": 32,
  "fragment_beats": 4,
  "strength": 0.4,
  "on_unavailable": "independent"
}
```

| Campo | Vincolo e comportamento |
|---|---|
| `id` | Identificativo non vuoto, unico nella sessione |
| `source`, `target` | Voci registrate; il destinatario deve supportare influenze ritmiche |
| `scope`, `aspects` | Valori supportati: `history` e `["rhythm"]` |
| `roles` | Filtro facoltativo dei ruoli destinatari; senza filtro tutti i ruoli dichiarati dal destinatario devono essere compatibili |
| `lookback_beats` | Limite positivo e finito: l'intero gesto sorgente deve rientrare fra `start − lookback_beats` e `start` |
| `fragment_beats` | Durata positiva e finita del tratto finale del gesto; non può superare la finestra destinataria |
| `strength` | Peso 0…1; a zero la relazione non viene interrogata né consumata |
| `on_unavailable` | `independent` (predefinito): compone con gli altri ingressi; `silence`: silenzia la frase destinataria; `error`: rifiuta il piano |

Il selettore prende l'ultimo gesto completo non vuoto entro il limite,
non ancora usato da quella relazione. Estrae gli attacchi del tratto
finale e li trasla all'inizio della finestra destinataria, senza riscalarli.
I pesi ritmici derivano dalle velocity relative alla massima velocity
del frammento. Le altezze della sorgente non vengono trasferite.

Il gesto viene consumato una volta per relazione quando il piano è
accettato, anche se il destinatario viene silenziato dalla presenza.
Nessuna scelta di attacchi nel frammento equivale a materiale indisponibile.
Sono destinatari supportati `motif` nei ruoli `melody` e `bass_line`,
e `responsive_line` in `bass_line`. Altri aspetti, trasformazioni e campi
non riconosciuti vengono rifiutati.

## Osservazione musicale condivisa

`music/observation.py` conserva riferimenti alle frasi accettate negli
ultimi 16 beat. Prima della composizione, guida e generatori ricevono lo
stesso `PlanningRequest.observation`, riferito esclusivamente a finestre
accettate che terminano entro l'inizio del nuovo piano.

| Misura per voce | Definizione |
|---|---|
| `attacks` | Note con attacco nell'intervallo osservato; note simultanee contano separatamente |
| `attacks_per_beat` | Attacchi divisi per i beat accettati disponibili |
| `occupied_ratio` | Durata dell'unione degli intervalli con note, divisa per i beat disponibili; la polifonia non moltiplica la durata |
| `register` | Minima e massima altezza MIDI delle note che intersecano l'intervallo, oppure `null` |
| `assigned_beats` | Beat osservati nei quali la voce appartiene all'organico, anche se silenziosa |

`available_beats` e `coverage_ratio` indicano quanta parte dei 16 beat è
disponibile. Intervalli non pianificati non diventano silenzi osservati.
Senza storia, frequenza degli attacchi e occupazione sono `null`; una
frase accettata silenziosa produce zero. Una nota iniziata prima del
limite contribuisce all'occupazione residua e al registro, senza contare
come nuovo attacco.

L'osservazione comprende anche le parti accettate dei gesti incompleti;
le relazioni storiche continuano a richiedere gesti completi. La memoria
avanza soltanto dopo la validazione dell'intero piano e viene cancellata
dal reset. Ripetere un piano accettato non registra nuovamente le note.

Lo stato espone il riepilogo in `decisions.coordinator.observation`.
Le politiche delle voci lo usano per adattare i parametri nella sessione
guidata dal GPX. Formule, transizioni e precedenze sono descritte in
[Direzione musicale](DIREZIONE-MUSICALE.md#adattamento-dei-parametri).

## Gesti, stato e reset

Il generatore dichiara gli intervalli tramite `GestureSpan`, in beat di
trasporto. Il motivo sviluppato dichiara l'intero periodo `phrase_windows`;
le drums dichiarano il ciclo del materiale; motivo letterale, basso e
tessitura dichiarano la propria frase della finestra.

La memoria raccoglie le parti dopo l'applicazione della presenza e delle
politiche di silenzio. Un gesto diventa disponibile soltanto quando tutte
le sue finestre sono state accettate senza lacune. Un gesto iniziato prima
della prima finestra pianificata rimane incompleto. Nessuna nota può
attraversarne il confine. I gesti vuoti sono registrati ma non selezionati
come spunti sonori.

`history_beats`, positivo e finito, vale 64 se omesso. Limita la conservazione
della storia e la durata massima dei gesti; deve coprire i `lookback_beats`
configurati. La storia descrive piani musicali accettati, non certifica
l'esecuzione audio del dispositivo.

`stage(request) -> VoicePlan` prepara frase, decisioni, gesti e stato
successivo senza avanzare lo stato compositivo. Dopo la validazione di
tutte le voci, `accept(plan)` applica soltanto lo stato già preparato.
Un errore di preparazione o validazione del Coordinator non aggiorna
stati, storia o consumo delle relazioni. I generatori registrati nel
dialogo devono fornire entrambe le operazioni.

Nella stessa sequenza, ripetere l'ultima richiesta identica restituisce
il piano già accettato. Richieste modificate sullo stesso intervallo,
finestre sovrapposte e ritorni indietro richiedono un reset. Il runtime
azzera memoria e generatori su Stop, restart e discontinuità del trasporto.
Il reset apre una nuova `epoch`; `logical_start` riparte da zero alla
prima finestra, mentre `start` resta sul trasporto.

Le decisioni espongono guida, `epoch`, `plan_id`, numero dei gesti,
sorgenti storiche, attacchi spostati e risoluzione di ogni relazione.
L'indisponibilità distingue `missing`, `incomplete`, `silent`, `consumed`
ed `empty_fragment`.

## Configurazione d'ascolto

[`presets/organico.json`](../presets/organico.json) collega quattro voci:
guida percussiva, adesione melodica 0,3, adesione del basso 0,7 e relazione
storica drums → melodia con peso 0,4. La tessitura segue la sezione oppure
la melodia secondo lo switch **Segui sorgente**. La mappa dei pad è unica
in `adapters/percussion.py`; i device usano `voice_01`…`voice_04`.

```sh
.venv/bin/python -m desnivel.cli.ensemble \
  --gpx gpx/tappa05_Firenze_San_Gimignano.gpx \
  --config presets/organico.json --speed 50
```

La configurazione carica la [direzione musicale GPX](DIREZIONE-MUSICALE.md).
Con `--manual-sections` usa le sezioni esplicite dell'organico.
Con Stile **Nessuno**, `spaced_impacts` dura 32 beat: il primo gesto completo
può essere disponibile dopo otto finestre. Con uno stile selezionato il
gesto dura quattro battute, cioè quattro finestre nella configurazione
fornita. La disponibilità effettiva dipende anche da presenza e silenzi.

Il catalogo conserva anche `spaced_dialogue` di 8 beat e la base
`regular_pulse_offbeats`. Per usarli, impostare i due riferimenti
`material` e `standard_material` nella stessa configurazione. Non occorre
un altro file di sessione. La [selezione dello stile](STILI-PERCUSSIVI.md)
cambia la guida e il materiale; le ulteriori relazioni dei
[contratti proposti](proposte/musica/media/in-corso/RELAZIONI-MUSICALI.md) restano da implementare.

### Accettazione del riferimento ritmico

Una voce può fornire `prepare_reference(request)` e, se mantiene stato
associato alla guida, `accept_reference(prepared)`. Il primo prepara un
`PreparedRhythm` senza mutare lo stato; il secondo riceve lo stesso oggetto
solo dopo la validazione del piano completo, anche quando il produttore
non è assegnato alla sezione. Il generatore attivo riceve il materiale
preparato in `PlanningRequest.prepared_material`. Le regole degli stili e
le transizioni restano nel modulo percussivo.
