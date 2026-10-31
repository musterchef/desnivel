# Revisione dei controlli delle voci

Stato: analisi completata; gli interventi elencati non sono implementati.
Ambito: device Voice della sessione multivoce, configurazioni
`organico.json`, generatori e relativi preset.

## Ridondanze individuate

| Componente | Riscontro nel codice/configurazione | Intervento proposto |
|---|---|---|
| Melodia, preset `developed` | L'assetto completo coincide con i valori iniziali del generatore in `organico.json` | Rimuovere il preset |
| Basso, preset `responsive` del device | L'assetto completo coincide con i valori iniziali del generatore | Rimuovere il preset del device; conservare il preset iniziale del motore `BassSettings` |
| Melodia, preset `literal` e `low_register` | Rispetto ai valori iniziali cambiano soltanto `development` e `octave`, rispettivamente | Usare i controlli già esposti e rimuovere le due scorciatoie |
| Tessitura, preset `soft` e `present` | Cambiano soltanto `velocity`; ricaricano anche `follow_source = 0` | Rimuovere le scorciatoie; mantenere i tre controlli della voce |
| Melodia, stato `_origin` | Il generatore lo inizializza e lo assegna da `VoicePlan.state`, senza usarlo nella composizione; un test ne verifica il reset | Rimuovere lo stato superfluo e aggiornare il relativo test |

Gli assetti sono confrontati dopo l'espansione dei preset in
[`cli/generators.py`](../../src/desnivel/cli/generators.py), non soltanto
leggendo le chiavi dichiarate nei JSON. Ogni preset carica tutti i valori
iniziali più le proprie modifiche.

## Intervallo del basso da correggere o rendere esplicito

`density` è esposto da 0 a 4, ma la configurazione corrente usa
`min_spacing = 1` beat. La selezione degli attacchi si satura quindi prima
del massimo del controllo. Con una frase di quattro beat, attacchi
melodici su 0, 1, 2, 3 e i valori iniziali del basso, `density = 1`, `1.8`
e `4` producono la stessa frase. Il risultato è stato verificato anche
con `syncopation = 0.7` e `1`.

Non è un doppione di un altro controllo: è un intervallo esposto più ampio
di quello utile in questo assetto. Va allineato ai vincoli di spaziatura
oppure accompagnato da un'indicazione della saturazione. Il preset
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
alias di un singolo valore; resta da correggere il limite di densità indicato.
