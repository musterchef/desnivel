# Revisione dei controlli delle voci

Stato: rimozione dei preset ridondanti e dello stato melodico inutilizzato
implementata. Saturazione della densità resa esplicita nel device e nello
stato del piano. Lo spostamento del supporto ai test indicato in fondo resta proposto.
Ambito: device Voice della sessione multivoce, configurazioni
`organico.json`, generatori e relativi preset.

## Consolidamento dei controlli

| Componente | Riscontro dell'analisi | Intervento applicato |
|---|---|---|
| Melodia, preset `developed` | Assetto identico ai valori iniziali | Preset rimosso |
| Basso, preset `responsive` del device | Assetto identico ai valori iniziali | Preset del device rimosso; preset iniziale del motore `BassSettings` conservato |
| Melodia, preset `literal` e `low_register` | Scorciatoie di `development` e `octave` | Preset rimossi; controlli conservati |
| Tessitura, preset `soft` e `present` | Scorciatoie di `velocity`, con ripristino anche di `follow_source` | Preset rimossi; tre controlli della voce conservati |
| Melodia, stato `_origin` | Assegnato senza letture nella composizione | Stato eliminato; reset verificato sulla memoria compositiva effettiva |

Gli assetti sono confrontati dopo l'espansione dei preset in
[`cli/generators.py`](../../src/desnivel/cli/generators.py), non soltanto
leggendo le chiavi dichiarate nei JSON. Ogni preset carica tutti i valori
iniziali più le proprie modifiche.

## Densità richiesta e capacità del piano

`density` è esposto da 0 a 4, ma la configurazione corrente usa
`min_spacing = 1` beat. La selezione degli attacchi si satura quindi prima
del massimo del controllo. Con una frase di quattro beat, attacchi
melodici su 0, 1, 2, 3 e i valori iniziali del basso, `density = 1`, `1.8`
e `4` producono la stessa frase. Il risultato è stato verificato anche
con `syncopation = 0.7` e `1`.

Il controllo mantiene l'intervallo 0…4: con intervalli più brevi o altre
spaziature anche valori superiori a 1 possono aggiungere note. Per esempio,
con quattro attacchi candidati in 3,2 beat, spaziatura di un beat e adesione
completa agli attacchi, densità 1 seleziona tre note e 1,2 ne seleziona quattro.

`plan_bass` restituisce frase e riepilogo della stessa selezione ritmica.
Il device mostra **densità richiesta** e gli attacchi selezionati rispetto
alla capacità dell'ultimo piano accettato. `saturo` indica che il target
ha raggiunto tale capacità, senza modificare il valore impostato. La
capacità dipende anche dall'ordine di selezione dei candidati. Il preset
`rhythmic` conserva effetti distinti su sincopi e articolazione, ma il suo
`density = 1.8` non garantisce più note di `1`.

Riferimento: [`music/bass/generator.py`](../../src/desnivel/music/bass/generator.py),
funzione `_rhythm`.

## Distinzioni utili da conservare

| Controlli | Responsabilità distinte |
|---|---|
| Melodia: `development`, `activity`, `step_beats` | Trasformazioni delle cellule; pause e suddivisioni; durata ritmica di riferimento. Gli ultimi due non sono sostituti dello sviluppo |
| Basso: `rhythm_follow`, `groove_follow` | Il primo seleziona attacchi dalla melodia e influenza durate e accenti; il secondo ricolloca gli attacchi composti sulla guida condivisa |
| Basso: `melody_follow`, `mobility`, `variation` | Attrazione verso la classe di altezza locale; movimento nel registro; variazioni riproducibili nelle scelte |
| Presenza, densità/attività, velocity | Partecipazione di una finestra; quantità e disposizione delle note; dinamica MIDI |
| Tessitura: `follow_source`, `octave`, `velocity` | Sorgente delle altezze; registro; dinamica |

Non emerge una seconda coppia di controlli equivalenti a Concettualità e
Variazione delle drums. I controlli inattivi in alcuni ruoli sono già
segnalati dal generatore; l'inattività contestuale non ne giustifica la rimozione.

I preset melodici `spaced`, `flowing`, `spacious` e quelli del basso
`sparse`, `rhythmic` combinano responsabilità diverse. Non sono semplici
alias di un singolo valore. La saturazione della densità è indicata dal
riepilogo del piano, senza introdurre un secondo controllo.

## Uso operativo e uso nei banchi di prova

- `interpolate_settings` è usato dal planner del basso; non è codice morto.
- `percussion_pattern` è un generatore registrato e verificato per frasi
  esplicite, distinto da `percussion_phrase` usato nell'organico principale.
- I materiali `spaced_dialogue` e `regular_pulse_offbeats` sono usati nei
  confronti e nei test multivoce. La loro assenza dall'organico principale
  non ne giustifica l'eliminazione.
- `style_events` in `music/percussion/styles.py` è chiamato soltanto dai
  test degli stili. Si propone di spostarlo nel supporto ai test, conservando
  la verifica delle figure; non è il compositore usato durante la sessione.

La presentazione in minuscolo di nomi, opzioni e modalità dei parametri è
applicata dal device comune. Non modifica identificativi, preset o regole
musicali; non comporta rinomine dei file o dei simboli Python.
