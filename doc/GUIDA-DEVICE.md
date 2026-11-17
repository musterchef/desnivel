# Guida pratica ai device

> I riferimenti a `organico.json` descrivono il banco storico archiviato in `doc/archivio/organico.json`. Per creare e salvare le sessioni correnti consultare [Sessione guidata](SESSIONE-GUIDATA.md).

Per la sessione multivoce con `organico.json`.
Nel device scegli il controllo dal menu **Parametro**, poi imposta il valore.
Le tabelle propongono valori di partenza: gli altri controlli restano come sono.

## Prima di regolare

- Collega le Voice con **C** nel terminale e avvia **Play** in Live.
- Cambia un controllo alla volta. Le modifiche agiscono sulle prossime frasi; ascolta almeno quattro battute. Per confrontare dallo stesso punto usa **R**, poi **Play**, mantenendo lo stesso `seed` configurato.
- **Presenza ×** regola quante frasi partecipano: `0` silenzia la voce; `1` segue la presenza prevista dalla sezione. Non regola il volume e non rende attiva una voce fuori organico.
- Un controllo **[inattivo]** non interviene nel ruolo o nella modalità corrente.
- **manual** e l'indicatore **auto/manual** si riferiscono al parametro selezionato. Modificarlo rende manuale soltanto quel valore. Spegni **manual** per restituirlo all'automazione: i controlli adattivi riprendono gradualmente, gli altri seguono la configurazione. Un preset rende manuali i valori che applica, rilasciabili singolarmente. Ruolo e presenza restano indipendenti.
- In **auto**, le politiche adattive regolano attività e velocity della melodia, densità e sincopi del basso, velocity della tessitura, variazione e velocity ratio delle drums. Il meteo può contribuire anche allo sviluppo melodico e nelle sezioni manuali. Il campo e lo slider mostrano il valore della finestra in ascolto; `→` indica l'obiettivo e l'annotazione ne spiega il motivo. [Ingressi e formule](DIREZIONE-MUSICALE.md#adattamento-dei-parametri).
- `groove_follow = 0` toglie l'adesione diretta alle drums. Le relazioni con frasi precedenti configurate nella sessione restano attive.

## Melodia — Synth, `voice_01`

Usa il ruolo `melody` per questi assetti.

| Risultato cercato | Valori da impostare |
|---|---|
| Motivo riconoscibile, trasformazioni contenute | `development = 0.25`, `activity = 0.65`, `step_beats = 1` |
| Frase più ariosa | `development = 0.6`, `activity = 0.3`, `step_beats = 1.5`, `articulation = 0.65` |
| Frase più fitta e mobile | `development = 0.7`, `activity = 0.9`, `step_beats = 0.5`, `articulation = 0.8` |
| Altezze del motivo senza trasformazioni | `development = 0`, `step_beats = 1`; il dialogo ritmico resta applicabile |
| Più appoggio sulla guida delle drums | `groove_follow = 0.8`; per meno adesione diretta usa `0.1` |

`development` governa le trasformazioni del motivo; `activity` la densità e
le pause; `step_beats` la griglia ritmica di riferimento. Con
`development = 0`, `activity` e `phrase_windows` sono inattivi. `seed` è
configurato nel preset e non è un controllo del device.

`phrase_windows = 2` dichiara gesti di 8 beat; `8` gesti di 32 beat nelle
configurazioni fornite. Determina quando un gesto completo può essere usato
dalle relazioni storiche; non programma una chiusura melodica.
`octave = -1` abbassa il registro di riferimento, `1` lo alza.
`velocity` regola l'intensità di riferimento; `articulation` accorcia o
allunga le note rispetto allo spazio disponibile.

## Basso — Bass, `voice_02`

| Risultato cercato | Valori da impostare |
|---|---|
| Sostegno sobrio e disteso | `density = 0.5`, `syncopation = 0.1`, `mobility = 0.1`, `articulation = 0.9` |
| Risposta più sincopata e corta | `density = 0.8`, `syncopation = 0.8`, `rhythm_follow = 0.2`, `groove_follow = 0.3`, `articulation = 0.5` |
| Più legame con le drums | `groove_follow = 0.8`, `rhythm_follow = 0.2` |
| Più legame con la melodia | `rhythm_follow = 1`, `melody_follow = 1`, `groove_follow = 0` |
| Nessuna nota di basso | `density = 0` |

I tre legami hanno compiti diversi:

- `rhythm_follow`: preferisce gli attacchi melodici e ne riprende durate e accenti.
- `melody_follow`: preferisce la classe di altezza della nota melodica vicina. Anche a zero il basso usa le classi di altezza presenti nella frase sorgente.
- `groove_follow`: avvicina gli attacchi già composti agli appoggi delle drums; non aggiunge note. Valori alti possono ridurre le sincopi scelte prima.

`mobility` apre il movimento fra registri; `variation` varia le scelte
di attacchi e altezze. Non sono lo stesso controllo.
Per aumentare le note prova `density` da `0.5` a `0.8`, poi a `1`.
La spaziatura minima configurata limita il numero realizzabile: superare
`1` può non aggiungere note. Con melodia silenziosa, il basso può produrre
un sostegno di sezione se `groove_follow > 0`; con valore zero tace.

Il controllo è mostrato come **densità richiesta**. Il riepilogo
`4/4 attacchi · saturo`, per esempio, indica che l'ultimo piano ha
selezionato tutti i quattro attacchi consentiti dalla sua selezione
ritmica. Aumentare la richiesta non aggiunge note in quel piano.
Il valore numerico rimane quello impostato.

## Tessitura — Atmosphere, `voice_03`

| Risultato cercato | Valori da impostare |
|---|---|
| Sostegno del grado armonico della sezione | **Segui sorgente** `0`, `octave = 1`, `velocity = 45` |
| Sostegno ricavato dalla melodia | **Segui sorgente** `1`, `octave = 1`, `velocity = 50` |
| Stesso comportamento in un registro più basso | Mantieni lo switch scelto; imposta `octave = 0` |

La realizzazione iniziale è un accordo di sezione. Nel controllo
`realization` puoi scegliere anche la nota ripetuta e regolarne gli attacchi
con `step_beats` e `articulation`. Con **Segui sorgente** attivo, una
melodia assente o silenziosa fa tacere anche l'armonia. Il timbro e il
rilascio dello strumento determinano la continuità sonora percepita.

## Progressione armonica autonoma

Questa sezione compare soltanto per una voce configurata con il comportamento
**progressione autonoma**. Nel device, apri il menu **Parametro**, scegli
`progression`, quindi usa il menu del valore per selezionare `ciclo 0–5–3–4`,
`ciclo 0–3–4–0` oppure `ciclo 0–4–5–3`. La scelta agisce sulle prossime
finestre e rende manuale soltanto il ciclo; `octave`, `velocity` e
`articulation` restano indipendenti.

## Percussioni — Drums, `voice_04`

Per confrontare lo sviluppo su battute brevi, scegli House classica,
Boom bap o Breakbeat house nel controllo **Stile**.

| Risultato cercato | Valori da impostare |
|---|---|
| Groove di riferimento stabile | **Stile** a scelta, **Variazione** `0` |
| Groove riconoscibile con sviluppo moderato | **Stile** a scelta, **Variazione** `0.4`, `displacement_beats = 0` |
| Sviluppo completo, compresi spostamenti | **Variazione** `1`, `displacement_beats = 0.25` |
| Cambio di stile graduale | **Transizione (beat)** `16`, poi cambia **Stile**; `32` allunga il passaggio, `0` lo rende immediato |
| Risposte più distanti dagli attacchi melodici | Con Variazione positiva, `answer_clearance_beats = 0.5`; agisce sui colpi di risposta |

**House classica** usa la cassa sui quattro beat; **Boom bap** casse
sincopate e hi-hat ritardati; **Breakbeat house** una cassa spezzata con
backbeat. Con **Nessuno** si usano i materiali configurati.

Variazione ammette figure alternative e trasformazioni. Non rende ogni
battuta diversa; con il valore `1` anche le sospensioni previste da
`development` sono complete. I passaggi da/verso **Nessuno** sono immediati.

`velocity_ratio = 0.6` attenua la dinamica MIDI rispetto a `0.9`.
`gate_beats` regola la durata MIDI, non direttamente la coda sonora del kit.
`support_tolerance_beats` riguarda l'allineamento dei sostegni al basso:
con gli stili forniti è inattivo. Gli hi-hat di accompagnamento restano
autonomi; le risposte possono lasciare spazio alla melodia.

Per intervalli completi e configurazione: [Configurazione](CONFIGURAZIONE.md).
