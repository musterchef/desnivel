# Dati del viaggio e metriche OSC

Il modulo `desnivel.trip` legge FIT e GPX, seleziona i tratti osservati e
ricampiona ciascun tratto a intervalli regolari. Il comando
`desnivel.cli.stream_metrics` pubblica le grandezze fisiche via OSC.

Il FIT usa gli eventi timer di pausa e ripresa. Per file senza questi eventi,
`ensemble --infer-fit-pauses` abilita esplicitamente la stima delle pause dai
campioni GPS. Un GPX può utilizzare
gli eventi del FIT corrispondente tramite `--timing-reference`; senza
riferimento le soste sono stimate dalle coordinate. Lettura, provenienza
dei canali e criteri sono descritti in
[ANALISI-PERCORSO.md](ANALISI-PERCORSO.md#sorgenti-fit-e-gpx).

---

## Formato dei messaggi OSC

Ogni misura viene trasmessa con due argomenti numerici:

```text
/desnivel/v1/trip/metric/<nome>  elapsed_s  value
```

- **`elapsed_s`**: secondi dall'inizio dei tratti osservati concatenati, escluse le interruzioni, corrispondenti alla fine dell'intervallo di misura. Quota e distanza totale sono disponibili anche all'istante iniziale. Il replay accelerato non cambia il valore del timestamp.
- **`value`**: valore numerico della grandezza, nell'unità specificata.

### Frequenza di campionamento e aggregazione
- **Ricampionamento interno**: 10 Hz (`TimingConfig.internal_rate_hz`).
- **Pubblicazione OSC**: un aggiornamento per ogni secondo del viaggio (`OscConfig.trip_metrics_rate_hz`, porta predefinita **9000**). Con replay 30×, viene inviato un aggiornamento ogni 1/30 di secondo.

---

## Catalogo delle metriche

| Metrica | Unità | Descrizione e calcolo |
|---|---|---|
| `distance_delta_m` | m | Distanza percorsa nel secondo trascorso. |
| `distance_total_m` | m | Distanza osservata complessiva, senza ricostruire gli spostamenti attraverso le interruzioni. |
| `elevation_m` | m | Quota riportata dalla sorgente, filtrata con mediana sui dati grezzi. |
| `speed_kmh` | km/h | Velocità oraria calcolata come `distance_delta_m / durata × 3.6`. |
| `slope_ratio` | rapporto | Pendenza del terreno (rapporto dislivello / distanza percorsa). Un valore di `0.08` indica una salita dell'8%. |
| `effort_estimate` | 0.0 – 1.0 | Indice composito di sforzo, ottenuto combinando velocità normalizzata e pendenza positiva. |

### Calcolo dell'indice di sforzo

L'indice sintetico di sforzo combina la spinta della velocità e la resistenza della pendenza:

```text
speed_norm      = clip(speed_kmh / speed_reference_kmh, 0, 1)
slope_norm      = clip(max(slope_ratio, 0) / slope_reference, 0, 1)
effort_estimate = clip(weight_speed * speed_norm + weight_slope * slope_norm, 0, 1)
```

I pesi e le velocità di riferimento sono configurabili in `src/desnivel/trip/config.py`.

---

## Gestione dei valori mancanti

- I campi non disponibili nella traccia originale (ad esempio quote assenti) non vengono trasmessi; l'assenza di un messaggio non equivale a zero.
- Se un tratto contiene solo alcune quote, quelle mancanti vengono interpolate linearmente in base alla posizione dei punti nella sequenza. I tratti separati da interruzioni sono trattati indipendentemente.
- Le finestre di movimento che attraversano una giunzione o un intervallo segnalato come non valido non producono misure di velocità, pendenza o sforzo.

---

## Riferimenti nel codice e uso

- **Catalogo metriche**: `src/desnivel/trip/metrics.py`
- **Configurazioni e parametri**: `src/desnivel/trip/config.py`
- **Comando per lo streaming delle metriche**:
  ```sh
  python -m desnivel.cli.stream_metrics --gpx gpx/tappa04_Levanto_La_Spezia.gpx --speed 30
  ```

Per le opzioni complete e la modalità `--dry-run`, vedere [COMANDI.md](COMANDI.md).

