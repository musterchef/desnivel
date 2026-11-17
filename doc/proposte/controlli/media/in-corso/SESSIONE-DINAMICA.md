# Sessione dinamica senza organico statico

## Stato

Proposta in corso. La creazione guidata delle voci è già operativa; la
rimozione del banco statico `presets/organico.json` non è ancora completata.

## Obiettivo

La formazione musicale deve appartenere alla singola sessione. Generatori,
voci, ruoli, dipendenze e associazioni ai controlli Live vengono scelti durante
la preparazione del set e salvati nel documento della sessione, senza dipendere
da un organico globale precompilato.

Le impostazioni applicative restano in `settings/desnivel.toml`. I documenti
JSON di sessione conservano invece lo stato compositivo creato dall'utente.

## Stato attuale verificato

Il launcher crea una nuova sessione in `output/sessioni/` a partire da
`presets/sessione.json`. La base contiene soltanto i parametri della sessione e
collezioni vuote per generatori, voci, disposizione e associazioni Live.

La procedura guidata costruisce e aggiorna:

- la definizione del generatore scelto per ogni voce;
- la voce e il relativo ruolo nella disposizione;
- dipendenze obbligatorie e facoltative fra voci;
- componenti Snake e loro sorgenti;
- associazioni ai controlli presenti nelle tracce Live;
- voce di trasporto e sorgente ritmica;
- riconfigurazione e rimozione delle voci già create.

Il catalogo usato dalla procedura guidata è definito in
`desnivel.cli.session_setup`; non viene copiato da `organico.json`.

`presets/organico.json` è ancora usato come banco a quattro voci avviabile
direttamente, come esempio nella documentazione e come fixture condivisa da
test musicali, test della sessione e report del percorso. Questa dipendenza
rende il banco dimostrativo una sorgente implicita di configurazione per prove
che dovrebbero dichiarare autonomamente i dati necessari.

## Confini dei dati

| Informazione | Sede |
|---|---|
| Impostazioni applicative e tecniche | `settings/desnivel.toml` |
| Definizioni e stato di una formazione concreta | documento JSON della sessione |
| Materiali musicali riutilizzabili | cataloghi dei rispettivi moduli musicali |
| Traduzione verso controlli e strumenti | adattatori e moduli delle voci |
| Dati minimi necessari ai test | fixture specifiche dei test |

Il documento della sessione resta JSON perché rappresenta stato persistito,
non un insieme di impostazioni globali.

## Sequenza di migrazione

1. **Completare il contratto della sessione dinamica.** Verificare e testare
   che una sessione creata dal launcher possa rappresentare tutte le
   informazioni runtime oggi presenti nel banco statico. Le sezioni risolte dal
   percorso non devono essere duplicate come configurazione permanente.
2. **Separare le fixture.** Sostituire nei test l'accesso diretto a
   `presets/organico.json` con fixture minime per voce, dialogo musicale,
   direzione, timeline e report. Ogni prova deve dichiarare soltanto il proprio
   contratto.
3. **Aggiornare esempi e comandi.** Basare le guide operative sulla creazione o
   sull'apertura di una sessione salvata. Conservare eventuali banchi completi
   soltanto come esempi espliciti, senza attribuire loro un ruolo applicativo.
4. **Ritirare il banco statico.** Quando codice, test e guide non lo richiedono
   più, archiviare o rimuovere `presets/organico.json` e aggiornare tutti i
   riferimenti nello stesso cambiamento.

## Criteri di completamento

La migrazione è conclusa quando:

- il normale avvio crea e riapre formazioni senza leggere
  `presets/organico.json`;
- ogni voce e ogni relazione necessaria possono essere espresse nel documento
  salvato dalla procedura guidata;
- nessun test usa il banco dimostrativo come fixture generale;
- i comandi documentati usano sessioni create dall'utente oppure esempi
  dichiarati come tali;
- la rimozione del banco non modifica il comportamento del motore musicale.
