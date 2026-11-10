# Bozza: catalogo e assegnazioni per sezione

Proposta da revisionare insieme. I JSON di questa cartella non sono caricati dal sistema e non configurano una sessione eseguibile.

## File della bozza

- [vocabolario.json](vocabolario.json): identificativi dei ruoli, relazioni e descrittori timbrici in inglese.
- [catalogo-strumenti.json](catalogo-strumenti.json): tipi di strumenti e profili sonori concreti ancora da scegliere.
- [organico-sezioni.json](organico-sezioni.json): esempio di voci e assegnazioni manuali per tre sezioni di una tappa.

Le definizioni estese dei ruoli e le questioni aperte sono conservate nella [proposta sui ruoli musicali](../../media/in-attesa/RUOLI-MUSICALI.md).

## Strumento, suono e voce

`instrument_types` è un elenco iniziale di categorie per riconoscere gli strumenti. Non stabilisce ruoli, registro o polifonia. Le categorie sono una proposta del progetto, non riproducono la classificazione di un plugin.

`sound_profiles` identifica il suono effettivamente scelto: una patch, un preset o un kit. Due patch dello stesso strumento possono avere profili diversi. Le capacità operative devono riferirsi a quel suono e alla sua destinazione configurata.

`voices` identifica le parti compositive, collegando un profilo sonoro a un generatore. Il ruolo viene assegnato alla voce nella sezione, non al tipo di strumento.

I tre profili sonori sono segnaposto per la revisione. `null` significa informazione non definita; `[]` nei descrittori significa che nessun descrittore è stato assegnato. Non autorizzano deduzioni o valori predefiniti. Generatore, destinazione e capacità devono essere completati prima dell'esecuzione. Lo schema delle capacità resta da concordare su suoni reali.

Il profilo `sound_02` indica una patch analogica destinata all'esempio di linea grave: il ruolo `bass_line` è assegnato soltanto nelle sezioni dell'organico.

## Categorie del browser di preset

`vocabolario.json` conserva in `preset_classifications.serum_browser` le 29 categorie principali visibili nello screenshot fornito dall'utente. Le etichette originali sono preservate, comprese `E Piano`, `Seq`, `String` e `Drumkit`. Le sottocategorie non sono state osservate e non sono enumerate.

Questa classificazione resta separata da `instrument_types` e dai ruoli: contiene insieme nomi di strumenti (`Piano`), figure (`Arp`), categorie sonore (`Pad`) e materiali temporali (`Loop`). Nessuna categoria assegna automaticamente un ruolo o una capacità.

Il campo proposto `sound_profiles.*.preset_classification` permette di conservare la classificazione di un preset concreto, senza imporla ai suoni provenienti da altre sorgenti. Nei profili segnaposto resta `null` perché non è stato scelto alcun preset.

Esempio della struttura proposta, non assegnato ai profili:

```json
{
  "preset_classification": {
    "vocabulary": "serum_browser",
    "category": "pad",
    "subcategory_path": []
  }
}
```

`subcategory_path` contiene le etichette del percorso sotto la categoria principale, quando osservate. L'array vuoto dell'esempio non afferma che il browser non abbia sottocategorie. La classificazione serve a ritrovare e descrivere il suono; le capacità operative vanno verificate sul preset e sulla configurazione effettivi.

## Sezioni

L'esempio apre con una voce melodica, aggiunge altre due voci nello sviluppo e rimuove quella di pulsazione nella chiusura. Sono assegnazioni illustrative da confermare, non scelte definitive per una tappa.

- `from_progress` usa la progressione della distanza, come i preset delle tappe esistenti. I valori della bozza sono esemplificativi.
- `assignments` elenca tutte le voci attive della sezione. Non eredita le assegnazioni della sezione precedente.
- `dependencies` indica quali frasi servono al generatore. Non attribuisce automaticamente una relazione musicale come `response`.
- `parameters` è vuoto finché non scegliamo il generatore e i suoi controlli effettivi.
- Un cambio di sezione modifica il piano di organico. La gestione delle note già in corso resta da decidere prima del collegamento all'esecuzione.

## Funzioni proposte

Queste operazioni descrivono il confine delle responsabilità; non sono metodi implementati.

| Operazione | Ingressi | Risultato e responsabilità |
|---|---|---|
| `load_catalog` | JSON di vocabolario e catalogo | Lettura e verifica di identificativi, riferimenti e descrittori ammessi; nessuna scelta compositiva |
| `validate_arrangement` | Organico, catalogo e registro dei generatori | Verifica dei riferimenti, dati obbligatori, supporto dei ruoli e dipendenze attive e non cicliche per sezione |
| `MusicDirector.section_at` | Progressione della tappa e organico | Selezione della sezione e delle assegnazioni esplicite, insieme al contesto musicale; nessuna selezione automatica nella prima prova |
| `bind_voices` | Assegnazioni e registro dei generatori | Preparazione delle chiamate ai generatori con ruolo, parametri e dipendenze; risoluzione delle implementazioni fuori dalle classi generiche |
| `MusicCoordinator.plan` | Voci preparate, intervallo e contesto | Ordinamento delle dipendenze e raccolta delle frasi; il metodo esiste, ma non riceve ancora ruoli e assegnazioni di sezione |

Gli adattatori risolvono le destinazioni sonore. Il Coordinator non interpreta famiglie di strumenti o descrittori timbrici. La futura selezione automatica richiederà criteri del Director da definire; questa bozza conserva la scelta manuale.

## Punti per la revisione

1. Confermare o correggere le categorie iniziali. “Chitarra analogica” non è stata trasformata in una categoria: occorre chiarire se si intende acustica con corde metalliche o altro.
2. Scegliere i primi suoni reali e le destinazioni; descrivere quindi capacità e timbro senza dedurli dalla famiglia.
3. Confermare le voci e i ruoli della prima prova, quindi associare generatori effettivi e controlli supportati.
4. Decidere la gestione di ingresso e uscita delle voci ai confini di sezione.
