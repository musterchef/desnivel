# Selezione dello stile percussivo

Il generatore `percussion_phrase` espone **Stile**, una scelta nominale
salvabile nei preset. Ogni profilo definisce un vocabolario ritmico in
4/4 con quattro figure: due groove principali, una figura di piatti più leggera
e una chiusura con levare di cassa e rullante debole. BPM e suoni restano nel trasporto e nel Drum Rack.

## Profili disponibili

Un beat è una semiminima; le posizioni sotto partono da zero.

| Identificativo | Menu | Struttura e complementi |
|---|---|---|
| `none` | Nessuno | Usa `material`, `standard_material` e le regole già configurate |
| `house_classic` | House classica | Cassa su 0, 1, 2, 3; rullante su 1 e 3; hi-hat in levare; una variante aggiunge un hi-hat debole su 3,75 |
| `boom_bap_90s` | Boom bap | Cassa su 0 e 2, con anticipo su 1,75 oppure risposta su 2,75; rullante su 1 e 3; hi-hat in ottavi con accenti alternati e ritardo dei levare di 0,08 beat; una variante aggiunge un rullante debole |
| `breakbeat_house` | Breakbeat house | Cassa su 0, 1,5 e 2,75 oppure 0, 1,75 e 2,5; rullante su 1 e 3; hi-hat in ottavi con levare accentati e ritardati di 0,04 beat; complementi deboli diversi fra le varianti |

Il catalogo in `music/percussion/styles.py` contiene ruoli percussivi,
posizioni, velocity, struttura e timing. Le figure sono interpretazioni
circoscritte per il confronto all'ascolto. I ritardi 0,08 e 0,04 sono valori
del catalogo Desnivel; non sono conversioni di percentuali MPC o Maschine.

Le figure si organizzano in frasi di quattro battute: la prima espone il
groove principale; le battute interne possono richiamarlo o variarlo;
l'ultima può alleggerire i piatti o usare la chiusura. Il groove principale
cambia fra le due figure di base a ogni frase. `variation` regola la
probabilità di scegliere una figura alternativa: a zero resta sempre la
prima figura. Il seed rende le scelte riproducibili e indipendenti dai
tagli delle finestre. La fase del
ciclo dello stile è di quattro beat. La sequenza `development` conserva
il proprio periodo, basato sulla durata del `material` configurato.

## Collegamento alla voce

Il generatore richiede una mappa esplicita dei ruoli verso tre `lanes`
distinte già definite nella stessa voce:

```json
"style_lanes": {"kick": "low", "snare": "mid", "hat": "high"}
```

In `presets/organico.json` e `presets/dialogo.json` corrispondono alle note
MIDI 36, 38 e 42. Un profilo non contiene numeri MIDI. Senza questa mappa
si può usare `none`; selezionare altri valori produce un errore esplicito.

Il parametro è `settings.style`, `assignments.<voce>.parameters.style`
oppure l'override manuale del device. Valore iniziale: `none`. La scelta
accetta gli identificativi della tabella, non gli indici del menu.
Esempio per un'assegnazione:

```json
{"role": "percussion", "parameters": {"style": "house_classic"}}
```

Selezionare lo stile lascia invariati gli altri controlli e la posizione
musicale. La modifica agisce sulle finestre ancora da pianificare.
**Concettualità** è il parametro numerico continuo `conceptuality`, da 0
a 1, regolabile senza selezionare un preset. I preset che lo impostano
sono scorciatoie; non cambiano il tipo del controllo.

## Generazione e dialogo

Lo stile alimenta sia il riferimento condiviso con le altre voci sia
il materiale percussivo. Con stile attivo, `material.hits`, `anchor_beats`
e `standard_material.hits` non forniscono gli attacchi; la durata del
materiale e la sequenza `development` continuano a governare lo sviluppo.

Casse e backbeat del profilo sono eventi strutturali: conservano attacco
e velocity prima del fattore finale, anche con melodia o basso silenziosi.
La protezione riguarda il singolo evento. I piatti di accompagnamento sono autonomi: la melodia silenziosa non li
elimina. Il catalogo marca esplicitamente i colpi di risposta, come ghost
note e piccoli complementi di chiusura. Solo questi attraversano
l'interazione configurata con basso e melodia. `variation` seleziona i
complementi da sottrarre, spostare o accentare secondo `development`. Lo swing del profilo precede lo spostamento `displace`.

| Controllo | Effetto con stile attivo |
|---|---|
| `conceptuality = 0` | Figura regolare dello stile, comprese le varianti e il timing; nessuna interazione |
| `conceptuality = 1` | Struttura dello stile e complementi sviluppati e reattivi |
| Valori intermedi | Combinazione riproducibile dei rami regolare e sviluppato; non misurano l'influenza del genere |
| `variation` | Scelta di figure alternative e quota dei complementi trasformati |
| `displacement_beats` | Ampiezza dello spostamento dei complementi in `displace` |
| `transition_beats` | Durata del prossimo cambio fra stili, 0–128 beat; default 16, zero immediato |
| `seed` | Scelta delle figure, sviluppo e combinazione; resta pertinente anche sul ramo regolare |
| `velocity_ratio`, `gate_beats` | Dinamica e durata MIDI finali |

Presenza e operazione `silence` restano operative: `silence` sospende il
ramo sviluppato, mentre il ramo regolare può contribuire con
`conceptuality < 1`. Come nel generatore esistente, `variation = 0`
disattiva le trasformazioni, inclusa `silence`.
I limiti restano 128 attacchi per finestra e per ciclo sviluppato; il
superamento viene rifiutato. Coincidenze di stessa altezza e posizione
vengono unite; le durate rispettano finestra, gesto e attacco successivo.

Lo snapshot espone stile di destinazione, pesi effettivi all'inizio e alla
fine della finestra, durata della transizione, metro, fase logica e figure
dello stile di destinazione. `swing_delay_beats` descrive il profilo di
destinazione; durante il passaggio il timing effettivo è interpolato.
I preset utente precedenti vengono completati in memoria con
`style: "none"` e `transition_beats: 16`; l'aggiunta è visibile in
`preset_migrations` e non riscrive automaticamente il file.

## Transizioni

Il cambio fra due stili parte dalla prima finestra ancora da pianificare.
`transition_beats` misura tempo musicale, indipendente dal tempo trascorso
con Live in pausa. Il valore viene acquisito al cambio di destinazione;
modificarlo senza cambiare stile non ridimensiona una transizione avviata.

Con variazione attiva, l'ingresso sceglie la figura di destinazione con
casse e backbeat più vicini alla miscela corrente, confrontando posizioni
e accenti. L'offset scelto resta nello sviluppo successivo; con variazione
zero si conserva la prima figura di ogni stile.
Le figure condividono metro 4/4 e fase del ciclo. I colpi con stesso ruolo
e posizione di griglia diventano un solo evento: velocity e ritardo dei
levare vengono interpolati. I colpi esclusivi dello stile precedente
si attenuano, quelli della destinazione entrano gradualmente. Figure con
più appoggi comuni conservano quindi più struttura durante il passaggio.
Il processo modifica eventi MIDI, non volume o timbro del Drum Rack.

Se si cambia ancora stile durante il passaggio, la nuova transizione
parte dai pesi già raggiunti, anche se coinvolgono più di due stili.
La guida ritmica condivisa e il generatore consumano lo stesso materiale
preparato. L'accettazione della guida avviene solo dopo la validazione
dell'intero piano, anche quando la voce percussiva è fuori organico.
Il reset cancella la transizione. La prima selezione e i passaggi da o
verso `none` sono immediati: `none` usa materiali configurati separatamente.

## Ascolto in Live

1. Ricostruire e ricaricare il [device di voce](VOCE-M4L.md#costruzione),
   conservando insieme `.amxd` e i due script JavaScript.
2. Avviare la sessione con `--config presets/dialogo.json`, usando il
   [comando completo](DIALOGO-MUSICALE.md#configurazione-dascolto).
3. In `voice_04`, scegliere il parametro **Stile**, poi il profilo nel menu.
4. Confrontare prima a `conceptuality = 0`, poi a `1`; mantenere uguali
   kit, BPM e seed nel confronto A/B. Con `variation = 0` si ascolta la prima figura senza sviluppo.
5. Impostare **Transizione (beat)** a 16 e cambiare stile durante Play;
   confrontare con zero per il cambio immediato.

Per un secondo confronto con tempi distinti si possono impostare
manualmente 120 BPM per House e Breakbeat house e 95 BPM per Boom bap.
Sono impostazioni d'ascolto; il selettore non cambia il tempo di Live.

## Fonti e interpretazione

- [Ableton — Rock and house](https://learningmusic.ableton.com/make-beats/rock-and-house.html):
  confronto di figure riutilizzabili fra stili; riferimento per la House regolare.
- [BandLab — Boom bap](https://blog.bandlab.com/how-to-make-a-boom-bap-beat-on-bandlab/):
  backbeat, casse sincopate, hi-hat in ottavi e levare ritardati; riferimento
  per l'articolazione. Le varianti e il ritardo numerico sono definiti nel catalogo.
- [Attack — Breakbeat House](https://www.attackmagazine.com/technique/beat-dissected/breakbeat-house-beats/):
  cassa spezzata con tre colpi per battuta, backbeat, piatti e colpi deboli;
  riferimento per il profilo. Nessuna conversione automatica dello swing Maschine.

Il progetto non importa loop o dataset esterni. Timbro, tempo e
calibrazione all'ascolto contribuiscono al carattere percepito.
