# Proposta: ruoli musicali e organico

Materiale di progettazione da discutere e implementare. Le definizioni di questo documento non descrivono funzionalità disponibili. Lo stato del codice è descritto in [Voci e contesto musicale](../../../../RUOLI-MUSICALI.md).

## Principi

- **Voce stabile**: una voce è un'identità che resta per tutto il brano. Non cambia genere, device o capacità durante la composizione.
- **Capacità dichiarate**: ogni voce dichiara ciò che sa fare (ruoli, registro, polifonia, articolazioni). Una sezione può assegnare solo ruoli compresi in queste capacità.
- **Ruolo per sezione**: il ruolo è un'assegnazione temporanea di una sezione a una voce. Una voce può suonare, tacere o cambiare funzione tra sezioni diverse, purché la capacità lo permetta.
- **Strati separati**: l'intenzione della sezione (il Director), la realizzazione della parte (il generatore) e la destinazione sonora (l'adattatore) sono definiti separatamente.
- **Relazioni esplicite**: le interazioni tra voci sono dati dichiarati, con parametri e regole verificabili. Una dipendenza tra generatori non basta a definirle.
- **Parametri continui**: densità, registro, attività e intensità sono valori per sezione. Le etichette descrivono solo funzioni, mai un valore fisso.
- **Identificativi in inglese**; spiegazioni in italiano. Classi generiche indipendenti da strumenti specifici.

## Modello proposto

| Entità | Contenuto | Esempio |
|---|---|---|
| Voce | Identificativo, generatore, capacità (ruoli, registro, polifonia, articolazioni), dipendenze | `voice_01`: generatore melodico, capacità `melody` e `countermelody` |
| Sezione | Intervallo nel viaggio, voci attive, ruolo e parametri di ciascuna voce | sezione 3: `voice_01` in `melody` con densità bassa |
| Relazione | Tipo, voce sorgente, voce destinataria, parametri e regola | `voice_02` in `response` a `voice_01` |
| Destinazione | Associazione della voce allo strumento tramite adattatore | `voice_01` → device Live `melodic` |

L'organico è un preset per tappa: elenca le voci e le loro capacità. Le sezioni definiscono quali voci sono attive e con quale ruolo. Il formato resta JSON, per coerenza con i preset esistenti; lo schema è da definire.

Ogni voce ha un ruolo fisso. Una voce che cambia funzione richiede una ragione musicale esplicita nel preset; in assenza di questa, si usa una voce separata. Una voce appartiene a una sola famiglia funzionale: melodica (`melody`, `countermelody`), di basso (`bass_line`), armonica (`harmony`) o ritmica (`rhythm`). Non si mescolano funzioni diverse nella stessa voce. Una voce melodica che tace in una sezione resta sé stessa: non diventa una texture.

## Ruoli

Un ruolo è una funzione che una voce svolge in una sezione, non un valore musicale: non fissa registro, densità o velocity. Un ruolo esiste solo se richiede ingressi o criteri di verifica che nessun altro ruolo condivide.

| Ruolo | Funzione | Ingresso specifico | Criterio di verifica | Origine |
|---|---|---|---|---|
| `melody` | Linea principale, materiale tematico | Materiale tematico, contorno | Riconoscibilità e continuità della linea | Invariato |
| `countermelody` | Linea secondaria indipendente | Linea di riferimento | Indipendenza ritmica e di contorno dalla melodia | Proposta precedente |
| `bass_line` | Linea più grave, radice armonica | Radice armonica, registro grave | La nota più grave del momento appartiene alla voce | Invariato |
| `harmony` | Accordi o sostegno armonico, tenuti o ritmici | Riferimento armonico, spazio di registro | Coerenza con l'armonia della sezione | Unisce `sustained_texture` e `harmonic_accompaniment` |
| `rhythm` | Pulsazione e figure ritmiche | Metro, pulsazione | Regolarità e posizione degli accenti | Unisce `pulse` e `percussion` |

Il profilo di attacco (tenuto o ritmico) è un parametro di `harmony`. Il tipo di strumento (percussivo o intonato) è una capacità della voce.

Restano fuori dal vocabolario: `fill`, `accent`, `arpeggio`, `ostinato` (interventi o tecniche, non ruoli) e le famiglie sonore come `drum_kit` e `modular_synth` (strumenti, non funzioni).

## Relazioni proposte

Ogni relazione è un dato del preset con quattro campi: voce sorgente, voce destinataria, parametri e regola. I criteri seguenti sono proposte di partenza; le soglie numeriche vanno tarate con l'ascolto.

| Identificativo | Significato | Regola | Verifica |
|---|---|---|---|
| `doubling` | La voce destinataria riprende la sorgente con gli stessi attacchi e contorno, a un intervallo consonante fisso (unisono, ottava, terza o sesta) | Attacchi coincidenti entro una tolleranza in beat; altezze uguali o trasposte di un intervallo fisso; contorno invariato | Confronto tra le sequenze di attacchi e altezze; scarto di intonazione e di tempo entro la tolleranza |
| `response` | La voce destinataria risponde a un gesto completo della sorgente | Il gesto termina in una cadenza o è seguito da una pausa minima; la risposta entra dopo la pausa, usa materiale derivato dal gesto (inversione, retrogrado, sequenza, o solo il profilo ritmico) e termina prima del gesto successivo | Il gesto è riconosciuto come frase completa; la risposta non si sovrappone alla sorgente oltre la tolleranza; la durata della risposta non supera quella del gesto |
| `support` | La voce destinataria sostiene la sorgente con note dell'accordo corrente, senza competere con il suo registro o i suoi attacchi | Usa le note dell'armonia della sezione; evita il registro occupato dalla sorgente e i suoi attacchi principali; la densità cala quando la sorgente è attiva | Nessuna nota della destinataria cade nella banda di registro della sorgente nei momenti di attacco; le note di sostegno appartengono all'armonia della sezione |

Il criterio comune: una relazione è verificabile sulle note prodotte, non sull'esistenza di una dipendenza tra generatori. `response` non significa occupare le pause: la risposta è un evento con inizio e fine propri, anche breve. Le pause degli eventi non equivalgono a silenzio audio, come già indicato nei riscontri.

`support` è implementato in [`TextureGenerator`](../../../../../src/desnivel/music/texture/generator.py) come `support_source`: non introduce un nuovo campo di relazione nel preset, ma riusa la dipendenza già dichiarata dalla voce e trasporta per ottave l'intera realizzazione armonica fuori dal registro occupato dalla sorgente nella finestra corrente, riducendo la velocity in proporzione alla sua occupazione. Il generatore realizza l'armonia di sezione come accordo diatonico oppure come nota singola ripetuta; `doubling` e `response` restano da implementare.

Restano da definire: la soglia di tolleranza in beat, la soglia di pausa che chiude un gesto, e il metodo di riconoscimento della cadenza.

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
| Riferimento tra parti | `Phrase` e dipendenze del Coordinator; `support` implementato in `TextureGenerator` | Interpretazione musicale di `doubling` e `response` nei generatori |
| Spazi disponibili | Attacchi e durate nelle note | Analisi comune degli intervalli occupati; le pause degli eventi non equivalgono a silenzio audio |
| Fine del gesto | Nessuna rappresentazione dedicata | Configurazione esplicita o regola di segmentazione; la fine della finestra non basta |
| Armonia | Tonica e scala nel Director; preferenze locali nel generatore di accompagnamento | Accordi configurati o regole per sceglierli; non sono determinati univocamente dalla scala |
| Capacità delle voci | Registro configurato nel generatore di accompagnamento | Profili comuni di registro, eventi intonati/percussivi, articolazioni e polifonia |
| Pulsazione | Posizione e durata in beat nel Coordinator | Generatore e ricorrenza; metro e origine per gli accenti di battuta |
| Evoluzione della tappa | Sezioni dal viaggio e finestre in beat | Collegamento tra i tempi, ingressi e uscite delle voci, completamento o interruzione delle frasi |
| Identità della voce | Ogni voce ha un generatore e `supported_roles`; le assegnazioni vengono verificate contro questi ruoli in [session.py](../../../../../src/desnivel/music/session.py) | Cambi di ruolo per sezione e uscite temporanee di una voce, senza cambio di identità |
| Selezione automatica | Nessun criterio implementato | Definire criteri musicali dopo la prova con organico esplicito |

La prima prova discussa prevede contesto comune, due generatori con una dipendenza dichiarata e verifica delle frasi prodotte. La scelta dei generatori e delle regole resta da concretizzare.

## Riferimenti della proposta

- [Open University — Melody and harmony; Texture](https://www.open.edu/openlearn/mod/oucontent/view.php?id=26858&section=2).
- [Ableton Learning Music](https://learningmusic.ableton.com/).
- [Tasmanian Symphony Orchestra — Chan Mali Chan, risorse didattiche](https://www.tso.com.au/content/uploads/2019/03/TSO-Songbook-Teaching-Resources-Chan-Mali-Chan-for-website-30042018.pdf).
