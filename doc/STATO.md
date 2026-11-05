# Stato del progetto

Desnivel legge registrazioni FIT/GPX e compone frasi multivoce. La sessione
principale è `desnivel.cli.ensemble`. Il launcher permette di creare sessioni
con un nome o caricare le configurazioni salvate in `output/sessioni/`, e
di scegliere `01`–`12`, la variante locale `07bis` o un file con `99`: [avvio e sorgenti](COMANDI.md#sessione-multivoce-con-scelta-della-tappa).

## Funzionalità operative

| Area | Comportamento | Riferimento |
|---|---|---|
| Viaggio | Lettura FIT/GPX, filtri GPS, selezione dei tratti osservati e ricampionamento a 10 Hz; metriche neutre pubblicabili via OSC | [Dati del viaggio](DATI-VIAGGIO.md) |
| Analisi | Profilo altimetrico, zone, macrosezioni, diagnostica della sorgente e report HTML | [Analisi del percorso](ANALISI-PERCORSO.md) |
| Direzione musicale | Tavolozza, armonia e motivo dal profilo; assetti delle macrosezioni e override configurabili | [Direzione musicale](DIREZIONE-MUSICALE.md) |
| Tempo | Replay lineare oppure allocazione in beat; Play, Stop, ripresa e restart collegati al trasporto di Live | [Timeline](TIMELINE.md) |
| Composizione | Generatori di melodia, basso, tessitura e percussioni; ruoli, organico, presenza e dipendenze per sezione | [Voci e contesto](RUOLI-MUSICALI.md) |
| Dialogo | Guida delle drums, relazioni fra frasi e osservazione degli ultimi 16 beat accettati | [Dialogo musicale](DIALOGO-MUSICALE.md) |
| Adattamento | Obiettivi dei controlli da contesto locale e osservazione musicale; transizioni fra finestre e precedenza manuale per parametro | [Adattamento](DIREZIONE-MUSICALE.md#adattamento-dei-parametri) |
| Contesto ambientale | Meteo storico acquisito e salvato in cache, contributo musicale attivabile con M; fondo OSM acquisibile come informazione | [Contesto ambientale](CONTESTO-AMBIENTALE.md) |
| Configurazione guidata | Sessione vuota, rilevamento dei controlli Live, aggiunta e associazione di voci, rimozione con verifica delle dipendenze e salvataggio | [Sessione guidata](SESSIONE-GUIDATA.md) |
| Device | Dispositivo MIDI comune, menu forniti da Python, controlli auto/manual e preset utente persistenti | [Voce M4L](VOCE-M4L.md) |
| Controllo Snake | Preparazione guidata con N, componente per istanza, tre ruoli e modalità autonoma/coordinata; adattamento al viaggio e lettura come sorgente con ruolo, previsione e note sostenute | [Snake](SNAKE.md#componente-multiruolo) |
| Osservazione e controllo | Terminale, snapshot JSON e dashboard con mappa, piano corrente e successivo, controlli e stato del meteo | [Sessione multivoce](SESSIONE-MULTIVOCE.md) |
| Registrazione | Preparazione delle tracce REC audio/MIDI e controllo della registrazione Arrangement in Live, con conferme del device | [Registrazione](SESSIONE-MULTIVOCE.md#registrazione-audio-e-midi-in-live) |

L’organico di esempio usa quattro voci. Snake può partecipare alla sessione
guidata e resta disponibile come banco separato; il player dedicato del basso
è un ulteriore banco di prova. Sono descritti in [Snake](SNAKE.md),
[Basso](BASSO.md) e [Tappe e preset](TAPPE-E-PRESET.md).

## Limiti e lavoro aperto

- Le lacune della registrazione separano i tratti: non vengono ricostruiti
  automaticamente percorso, tempi o distanze mancanti.
- Il meteo deriva da rianalisi storiche su griglia; il fondo OSM è
  un'associazione geometrica e non ha una mappatura musicale.
- Le drums sviluppano figure precomposte. Il compositore a regole e le
  influenze multiple di stile restano [proposte](proposte/STILI-PERCUSSIVI.md).
- I controlli agiscono su note e ritmo; i suoni e gli effetti degli
  strumenti si impostano in Live. Le corrispondenze musicali richiedono
  taratura all'ascolto.
- I cambi di pattern del banco Snake non sono quantizzati a battuta.

La suite Python e i test JavaScript verificano dati, composizione,
pianificazione, protocolli e interfacce simulate. Non misurano la qualità
sonora o il jitter audio in Live. Comandi in [COMANDI.md](COMANDI.md#suite-di-test).
Le attività aperte sono in [TODO.md](../TODO.md); i contratti futuri sono
separati in [proposte/](README.md#proposte-di-sviluppo).
