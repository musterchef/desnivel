# Contesto ambientale del viaggio

Il contesto ambientale associa informazioni esterne ai tratti osservati
del viaggio. Il meteo storico può modificare la musica; il fondo stradale
è acquisibile e consultabile nello stato della sessione, senza una
mappatura musicale definita.

## Componenti e responsabilità

- `trip/context.py`: formato comune `ContextSource`, identità della traccia,
  campionamento del percorso e aggregazione delle porzioni coperte.
- `trip/weather.py`: classe `WeatherFetcher`, acquisizione storica Open-Meteo
  lungo coordinate e orari originali, senza regole musicali.
- `trip/surface.py`: classe `SurfaceFetcher`, ricerca dei tag OSM del fondo
  stradale e valutazione dell'associazione spaziale.
- `trip/context_http.py`: richieste HTTP JSON durante l'acquisizione.
- `music/environment.py`: traduzione del meteo in indicazioni musicali.
- Politiche in `music/melodic/`, `music/texture/` e `music/percussion/`:
  scelta degli obiettivi per i controlli esistenti.
- `cli/fetch_context.py`: acquisizione esplicita e salvataggio JSON.
- `cli/weather_context.py`: caricamento automatico e cache persistente del meteo.
- `cli/ensemble.py` e `cli/ensemble_runtime.py`: caricamento, proiezione delle
  finestre musicali e applicazione degli interpreti registrati.

Il coordinatore musicale riceve soltanto indicazioni musicali, senza
dipendere dalle sorgenti meteorologiche o cartografiche. Il runtime può
registrare una sorgente con un interprete e un flag di attivazione oppure
esporla soltanto come informazione.

## Formato comune e copertura

Un file di contesto contiene versione `1`, identificativo `source`,
`track_signature`, asse `time` o `distance`, unità dei canali, intervalli
`records` e provenienza `provenance`. Ogni intervallo contiene:

- `segment`: indice del tratto osservato;
- `start`, `end`: estremi in secondi attivi oppure metri cumulativi
  dall'origine della traccia;
- `values`: valori numerici, categorie testuali o `null` per ciascun canale;
- `details`: riferimenti specifici della sorgente.

Gli intervalli di una sorgente sono ordinati e non sovrapposti per tratto.
L'impronta include tempi attivi, coordinate, distanza cumulativa e confini
sorgente: il caricamento rifiuta un file acquisito su una traccia o un
ricampionamento diverso. Usare gli stessi argomenti di lettura FIT/GPX
nell'acquisizione e nell'ascolto.

La proiezione delle finestre riutilizza `WindowContext`, sia in modalità
lineare sia allocata. Le interruzioni della registrazione rimangono
separate. I canali numerici sono mediati sulle porzioni coperte; le
categorie riportano le rispettive quote. Il peso è la durata sorgente
per l'asse temporale e la lunghezza per quello spaziale.

Ogni canale espone valore, unità, copertura e stato `available`, `partial`
o `unavailable`. Un valore mancante non equivale a zero. L'interprete
meteorologico usa soltanto canali che coprono tutta la porzione osservata
della finestra, indipendentemente dalla copertura degli altri canali.

## Meteo storico

L'acquisizione usa la
[Historical Weather API di Open-Meteo](https://open-meteo.com/en/docs/historical-weather-api),
modello `era5`, dati orari UTC di vento a 10 m e precipitazioni.
Si tratta di dati di rianalisi su griglia, non di misure effettuate dal ciclista.

Ogni tratto viene diviso ogni 5 km e ai confini delle ore originali.
Le richieste usano coordinate e orario del punto centrale di ciascun
intervallo, in gruppi di massimo 20 località. Il passo spaziale è
modificabile con `--distance-step-m`; un passo minore non aumenta la
risoluzione della sorgente meteorologica.

- `wind_speed_kmh`: vento interpolato fra i due campioni orari adiacenti
  nella località richiesta.
- `precipitation_mm`: accumulo dell'ora che contiene l'istante sorgente.
  L'API identifica l'accumulo con il timestamp di fine ora.
- `precipitation_change_mm`: differenza fra quell'accumulo e l'ora precedente
  nella stessa località. Il confronto non sottrae valori di due località
  diverse lungo la traccia.

Il vento descrive il carattere persistente locale. La differenza delle
precipitazioni descrive un cambiamento orario e può restare attiva per
tutto l'intervallo rappresentato. Una pioggia costante non produce
continuamente nuovi cambiamenti. Non vengono ricostruiti istanti di
inizio o fine pioggia all'interno dell'ora.

Le indicazioni musicali sono separate dal profilo altimetrico:

| Indicazione | Calcolo |
|---|---|
| `dynamic_pressure` | Vento medio / 40 km/h, limitato a 0–1 |
| `material_change` | Media del modulo delle differenze di precipitazione; sotto 0,2 mm vale zero, raggiunge 1 a 2 mm |

Le soglie sono assolute e uguali per tutte le tappe. Aumenti e diminuzioni
delle precipitazioni non si cancellano quando una finestra contiene entrambi.
Le soglie e i coefficienti musicali richiedono taratura all'ascolto.

| Voce | Contributo musicale |
|---|---|
| Melodia | Fino a +12 di velocity per la pressione; fino a +0,25 di `development` per il cambiamento |
| Tessitura | Contributo fino a 0,15 al fattore dinamico della velocity, conservando l'alleggerimento dovuto alla melodia |
| Percussioni | Contributo fino a 0,15 al fattore di `velocity_ratio`; fino a +0,20 di `variation` |

Il basso conserva le proprie regole di sostegno e dialogo. Gli obiettivi
restano nei limiti dei controlli. Il risolutore esistente applica transizioni
di 8 beat alla dinamica e 16 beat allo sviluppo; lo sviluppo melodico viene
rivalutato ai confini dei periodi e quello percussivo ai confini del ciclo.
I valori manuali del singolo parametro mantengono la precedenza.

## Fondo stradale

L'acquisizione interroga Overpass per le strade OSM vicine al percorso,
conservando il valore originale del
[tag `surface`](https://wiki.openstreetmap.org/wiki/Key:surface).
Il campionamento predefinito è ogni 100 m, separatamente per tratto; il
punto centrale rappresenta l'intervallo campionato.

La classe cerca la polilinea più vicina entro 25 m. Se una seconda strada
si trova a non più di 5 m dalla distanza della prima, l'associazione viene
segnalata come ambigua. La ricerca include anche strade prive di `surface`:
una strada vicina senza tag non viene sostituita con una più lontana dotata
di tag. Stati disponibili: `matched`, `ambiguous`, `surface_not_tagged`,
`no_road_within_radius`.

È un'associazione geometrica locale, non un riconoscimento completo del
percorso sulla rete stradale. Strade parallele, incroci, errori GPS e
variazioni più brevi del passo di campionamento possono ridurre la copertura
o l'attendibilità. Le richieste che attraversano l'antimeridiano sono rifiutate.
I dati OSM descrivono lo stato cartografico restituito al momento della
richiesta, senza ricostruzione storica del fondo nel giorno del viaggio.

Il file conserva identificativi OSM, distanza dalla strada, tag, stato
dell'associazione e attribuzione OpenStreetMap/ODbL. Non viene dedotta la
superficie dalla pendenza o dalla classe della strada. La traduzione
musicale delle categorie rimane da definire.

## Acquisizione e confronto in ascolto

All'avvio di `ensemble`, il meteo della tappa viene caricato automaticamente
da `output/context/weather/`. Se manca, viene acquisito e salvato prima di
avviare il server della sessione. La cache è identificata dall'impronta
della traccia, dal modello ERA5 e dal passo spaziale di 5 km. Durante
l'ascolto non sono effettuate richieste esterne. `--weather-context` permette
di scegliere un file esplicito al posto della cache. I file salvati
conservano anche richieste e risposte originali.
Errori HTTP o risposte non valide interrompono l'acquisizione senza
sostituire i dati con valori predefiniti.

L'acquisizione separata rimane disponibile:

```sh
python -m desnivel.cli.fetch_context weather \
  --track gpx/tappa04_Levanto_La_Spezia.gpx --output /tmp/desnivel-weather.json

python -m desnivel.cli.fetch_context surface \
  --track gpx/tappa04_Levanto_La_Spezia.gpx --output /tmp/desnivel-surface.json
```

I percorsi sono esempi sostituibili con qualsiasi tappa. Per GPX con
riferimento FIT, ripetere `--timing-reference` in tutti i comandi.

Con i device Voice collegati, eseguire le due sessioni in successione,
ripartendo dall'inizio con gli stessi suoni, preset, BPM e valori manuali:

```sh
# A: contributo meteorologico attivo
python -m desnivel.cli.ensemble \
  --track gpx/tappa04_Levanto_La_Spezia.gpx --config presets/organico.json \
  --weather-context /tmp/desnivel-weather.json

# B: stessi dati e politiche adattive, contributo meteorologico escluso
python -m desnivel.cli.ensemble \
  --track gpx/tappa04_Levanto_La_Spezia.gpx --config presets/organico.json \
  --weather-context /tmp/desnivel-weather.json --without-weather
```

`--surface-context /tmp/desnivel-surface.json` aggiunge il fondo allo stato.
`--without-weather` carica il meteo ma disattiva inizialmente il contributo
musicale. **M** nel terminale lo attiva o disattiva senza scaricare dati né
riavviare il viaggio. Le altre politiche adattive restano attive, anche
senza analisi altimetrica.

Il cambiamento riguarda le prossime finestre da pianificare: device e
dashboard conservano lo stato del piano corrente e segnalano i cambi in
coda. `--dry-run` valida configurazione e file e genera le sezioni;
riusa il file esplicito o la cache, segnala il meteo assente e non avvia
download né il confronto temporale lungo il viaggio.

I piani correnti e futuri nello stato della sessione espongono
`local_trip.environment`: misure aggregate, copertura, intervalli e
`interpretation_enabled`. `adaptive_context` espone le indicazioni
musicali; `automation` contiene obiettivi, valori applicati e motivi.
Le risposte originali delle API rimangono nel file acquisito e non sono
duplicate in ciascun piano musicale.

## Indicazione su device e dashboard

Il device Voice mostra `meteo` nella riga superiore. La dashboard mostra
uno stato complessivo con i nomi degli strumenti interessati e uno stato
per ciascuna voce. Entrambe le viste usano il piano corrente, senza
anticipare i contributi dei piani futuri. Prima dell'ingresso di un piano
o a trasporto fermo compare l'attesa; una perdita di collegamento segnala
che lo stato non è aggiornato.

Sono distinti: `non caricato`, `disattivato`, `abilitato` in attesa o con
dati indisponibili, `in uso` con l'elenco dei parametri, contributi esclusi
da `manual`, nessun nuovo contributo e voce non interessata. Una voce fuori
dal piano è segnalata separatamente. La dashboard elenca anche i parametri
manuali quando solo parte dei contributi è esclusa.

Le politiche annotano in `automation.<voce>.<parametro>.contributions` il
contributo all'obiettivo dopo limiti e arrotondamento, identificato da
`dynamic_pressure` o `material_change`. L'annotazione segue la cadenza di
aggiornamento dell'obiettivo. L'indicatore descrive il contributo agli
obiettivi automatici, non una misura dell'audio; `nessun nuovo contributo`
può includere il completamento di una transizione già avviata.

I test automatici verificano proiezione, lacune, associazione spaziale,
ripetibilità A/B, differenze nelle note e precedenza manuale. Il confronto
percettivo con strumenti e device richiede la prova d'ascolto.
