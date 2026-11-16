# Forma musicale guidata dalla tappa

Stato: fondazione neutra e riduzione delle variazioni locali
implementate; interpretazione musicale da definire con prove d'ascolto.

## Obiettivo

Derivare l'andamento della composizione dai cambi persistenti del viaggio,
senza imporre sezioni `opening`, `development` e `closing` a percentuali
prefissate. Una tappa uniforme può mantenere una sola continuità fino
all'arrivo; una tappa articolata espone i propri cambi reali.

## Fondazione implementata

`trip/route_form.py` descrive le macrosezioni come campate neutre e ricava
eventi di partenza, cambio di profilo, vetta, valle, lacuna osservativa e
arrivo. Distanza, tempo attivo, dislivello e pendenza restano misure del
viaggio. La descrizione è conservata nella configurazione risolta e nello
snapshot del runtime, senza modificare la musica.

Il rilevamento non assegna significati a nomi di famiglia configurabili e
non usa soglie percentuali della distanza totale. Vetta e valle richiedono
un'inversione diretta del dislivello fra macrosezioni persistenti.

La riduzione strutturale legge da `settings/desnivel.toml` rapporti locali
configurabili. Una breve
inversione resta subordinata quando occupa una parte minore della distanza e
del dislivello delle due continuità concordi che la circondano e la parte
successiva recupera almeno il dislivello perso. Un limite fisico di distanza
permette di conservare come continuità autonoma una contropendenza comunque
percepibile. Il risultato conserva misure e indici delle campate riunite;
non elimina l'osservazione originale. Le pause annotano il tempo sorgente ma
non interrompono la forma altimetrica.

## Interpretazione musicale prevista

Un livello successivo in `music/` potrà tradurre gli eventi in indicazioni
come continuità, trasformazione, preparazione o risoluzione. Questa
traduzione dovrà:

- dichiarare quali generatori e controlli interessa;
- mantenere separati eventi del percorso e decisioni musicali;
- conservare provenienza e intensità di ogni contributo;
- rispettare stato `stage`/`accept`, reset e riproducibilità;
- non creare sezioni artificiali quando il profilo non offre un confine.

L'arrivo è un evento reale della tappa. La futura conclusione musicale non
richiede che l'ultimo tratto cambi pendenza e non deve essere ottenuta
ritagliando una percentuale finale del percorso.

## Contesti complementari

Meteo e superficie non appartengono alla forma altimetrica. Restano sorgenti
`ContextSource` indipendenti:

- il meteo può contribuire a variazioni locali quando i dati sono disponibili
  e l'interpretazione è attiva;
- la superficie deriva da un'associazione spaziale con OpenStreetMap e non ha
  ancora una traduzione musicale approvata;
- dati mancanti o ambigui non producono valori sostitutivi.

Questi contesti possono arricchire una lunga continuità, ma non spostano i
confini delle macrosezioni né inventano vette, valli o arrivi.

## Passi successivi

1. Mostrare campate ed eventi della forma nelle analisi di tappe reali.
2. Verificare inversioni, pianure intermedie, lacune e percorsi uniformi.
3. Definire una prima interpretazione musicale di continuità, punto di svolta
   e arrivo, indipendente da progressioni specifiche.
4. Collegare generatori e progressioni soltanto dopo l'approvazione delle
   regole d'ascolto.
