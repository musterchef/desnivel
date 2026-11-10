# Proposta: ruoli musicali e organico

Materiale di progettazione da discutere e implementare. Le definizioni di questo documento non descrivono funzionalità disponibili. Lo stato del codice è descritto in [Voci e contesto musicale](../../../../RUOLI-MUSICALI.md).

## Impostazione condivisa

- Identificativi e termini di configurazione in inglese; spiegazioni in italiano.
- Organico iniziale scelto esplicitamente per ogni tappa GPX, con voci attive configurate per sezione.
- Descrizione delle voci separata dalla scelta dell'organico e dalla destinazione sonora.
- Director responsabile delle scelte comuni e delle assegnazioni; Coordinator responsabile della pianificazione e delle dipendenze; generatori responsabili della composizione delle proprie parti.
- Classi generiche indipendenti da strumenti specifici.

## Struttura proposta

| Elemento | Informazioni proposte |
|---|---|
| Profilo della voce | Identificativo, generatore, ruoli supportati, capacità e limiti |
| Preset di organico | Voci selezionate, ruoli assegnati, parametri e dipendenze |
| Sezione | Voci attive e variazioni delle assegnazioni e dei parametri |
| Destinazione sonora | Associazione della voce allo strumento tramite adattatore |

Usare campi strutturati per i vincoli operativi. I descrittori timbrici non sostituiscono capacità e ruoli. JSON è il formato proposto per coerenza con i preset esistenti; lo schema dell'organico resta da definire.

## Vocabolario proposto dei ruoli

| Identificativo | Funzione proposta | Ingressi da assicurare | Comportamento e verifica da definire |
|---|---|---|---|
| `melody` | Esporre la linea melodica principale | Intervallo, materiale melodico o regole generative; contesto armonico quando usato per vincolare le altezze | Sviluppo riconoscibile del materiale, continuità tra frasi e rispetto dei vincoli dichiarati; valutazione anche all'ascolto |
| `bass_line` | Costruire la linea grave con funzione armonica e ritmica | Registro e riferimento armonico esplicito o interpretato da una frase | Appoggi e collegamenti nel registro assegnato; verificare le regole effettive del generatore senza imporre fondamentali a ogni attacco |
| `harmonic_accompaniment` | Sostenere l'armonia con accordi, arpeggi o altre disposizioni | Riferimento armonico, registro e limiti di simultaneità | Scelta e disposizione delle note, compatibilità con la polifonia disponibile e condotta delle parti quando prevista |
| `pulse` | Rendere percepibile la pulsazione | Intervallo, ricorrenza; metro e origine metrica se si usano accenti di battuta | Ricorrenze, suddivisioni, pause e accenti espliciti; non richiede un attacco su ogni beat |
| `countermelody` | Affiancare una linea distinta alla melodia principale | Frase di riferimento e regole della relazione armonica e ritmica | Valutare intervalli simultanei, movimento e distinzione delle linee; non implica contrappunto di specie |

I nomi sono convenzioni proposte per Desnivel. Il supporto dichiarato dal generatore e la validazione dei ruoli sono da implementare. Un ruolo non stabilisce valori universali di registro, densità o velocity.

## Relazioni proposte

| Identificativo | Significato | Requisiti aperti |
|---|---|---|
| `response` | Intervenire dopo una frase o un gesto di un'altra parte | Identificare il gesto e la sua conclusione, quindi definire lo spazio e la regola della risposta |
| `doubling` | Riprendere attacchi e altezze di una parte, eventualmente trasposte | Definire la trasformazione e la trasposizione |

Una dipendenza tra generatori non determina da sola la relazione musicale. `response` non significa occupare tutte le pause.

## Descrizioni distinte dai ruoli

- Famiglie sonore: `modular_synth`, `analog_synth`, `drum_kit`. Le capacità effettive dipendono dalla configurazione o dalla patch.
- Descrittori timbrici: `warm`, `round`, `bright`, `dry`, `metallic`, `punchy`. Restano descrittivi finché non viene definito un criterio di selezione; il controllo sonoro richiede mappature specifiche della destinazione.
- Tecniche e figure: `arpeggio`, `ostinato`.
- Interventi locali: `fill`, `accent`.

`Texture` riguarda l'organizzazione delle parti. L'etichetta `foundation`, discussa inizialmente, richiede di precisare se si intende sostegno grave, armonico o ritmico prima di diventare un'assegnazione operativa.

## Riscontri e decisioni aperte

| Punto | Base presente nel codice | Lavoro ancora da concordare |
|---|---|---|
| Materiale melodico | Motivi e scale nei preset; `journey.compose` produce `PatternChange` | Collegamento generale a generatori di `Phrase` con attacchi e durate |
| Riferimento tra parti | `Phrase` e dipendenze del Coordinator | Interpretazione musicale della relazione e supporto nei generatori |
| Spazi disponibili | Attacchi e durate nelle note | Analisi comune degli intervalli occupati; le pause degli eventi non equivalgono a silenzio audio |
| Fine del gesto | Nessuna rappresentazione dedicata | Configurazione esplicita o regola di segmentazione; la fine della finestra non basta |
| Armonia | Tonica e scala nel Director; preferenze locali nel generatore di accompagnamento | Accordi configurati o regole per sceglierli; non sono determinati univocamente dalla scala |
| Capacità delle voci | Registro configurato nel generatore di accompagnamento | Profili comuni di registro, eventi intonati/percussivi, articolazioni e polifonia |
| Pulsazione | Posizione e durata in beat nel Coordinator | Generatore e ricorrenza; metro e origine per gli accenti di battuta |
| Evoluzione della tappa | Sezioni dal viaggio e finestre in beat | Collegamento tra i tempi, ingressi e uscite delle voci, completamento o interruzione delle frasi |
| Selezione automatica | Nessun criterio implementato | Definire criteri musicali dopo la prova con organico esplicito |

La prima prova discussa prevede contesto comune, due generatori con una dipendenza dichiarata e verifica delle frasi prodotte. La scelta dei generatori e delle regole resta da concretizzare.

## Riferimenti della proposta

- [Open University — Melody and harmony; Texture](https://www.open.edu/openlearn/mod/oucontent/view.php?id=26858&section=2).
- [Ableton Learning Music](https://learningmusic.ableton.com/).
- [Tasmanian Symphony Orchestra — Chan Mali Chan, risorse didattiche](https://www.tso.com.au/content/uploads/2019/03/TSO-Songbook-Teaching-Resources-Chan-Mali-Chan-for-website-30042018.pdf).
