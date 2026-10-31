# Coordinamento ritmico delle voci

Stato: direzione musicale confermata; primo blocco operativo descritto in
[Dialogo ritmico](../DIALOGO-MUSICALE.md). Sono implementati riferimento,
adesione, struttura percussiva e scambio ritmico storico. La
[selezione dello stile](../STILI-PERCUSSIVI.md) è operativa; influenze
multiple e ulteriori relazioni restano da implementare.
Le drums definiscono il riferimento
ritmico; basso e melodia hanno adesione regolabile. Questo documento
definisce la specializzazione ritmica dei
[contratti per le relazioni musicali](RELAZIONI-MUSICALI.md). Tempo, gesti,
memoria, causalità e accettazione dei piani seguono quei contratti.

## Responsabilità

| Componente | Responsabilità |
|---|---|
| Direzione della sessione | Contesto armonico, organico, presenza e parametri della sezione |
| Modulo percussivo | Stile selezionato, groove, appoggi e suddivisioni; struttura e complementi della frase drums |
| Basso | Relazione ritmica con il groove e scelta delle altezze dal contesto e dalla frase melodica |
| Melodia | Motivo, sviluppo e fraseggio, con adesione regolabile al groove |
| Tessitura | Sostegno armonico, con eventuale influenza di una sorgente intonata |
| Coordinator | Trasmissione dei contesti musicali e ordinamento delle dipendenze |
| Device e trasporto | Controlli, collegamento e riproduzione delle frasi |

Genere e regole delle drums appartengono al modulo percussivo. Il
Coordinator riceve dati musicali neutrali: non contiene nomi di generi,
strumenti o regole specifiche delle voci.

## Riferimento ritmico e frase delle drums

Il riferimento ritmico è prodotto dal modulo percussivo prima delle
frasi delle altre voci. Contiene posizioni degli appoggi, relativi pesi,
suddivisioni con il loro timing e fase del ciclo. Non contiene note MIDI
fittizie né nomi di strumenti per trasmettere queste informazioni.

La frase drums contiene i colpi effettivamente suonati: struttura del
groove più complementi. I complementi possono rispondere a basso e
melodia. Non modificano retroattivamente il riferimento già utilizzato
da quelle voci.

Per ogni finestra il riferimento è immutabile, calcolato una sola volta
e condiviso da tutti i generatori. Il collegamento alla voce che lo
produce è esplicito nella configurazione, senza identificativi di parti
incorporati nel Coordinator.

## Ordine di generazione

1. Risolvere contesto armonico, organico, parametri e stile della finestra.
2. Selezionare dallo snapshot storico i gesti di riferimento e risolvere gli intervalli delle interazioni.
3. Preparare il riferimento ritmico dal modulo percussivo.
4. Ordinare le voci secondo dipendenze tecniche e relazioni attive sulla finestra corrente; rifiutare i cicli prima della generazione.
5. Generare le voci nell'ordine risolto, applicando la presenza prima di consegnarne il risultato alle voci dipendenti.
6. Validare e accettare insieme frasi, gesti e stati successivi, quindi consegnare le frasi alle destinazioni.

La presenza viene applicata alla frase di ogni voce prima di passarla alle
voci dipendenti, come nel sistema attuale. Le drums guidano attraverso il
riferimento preparato al punto 3, non attraverso la propria frase finale.
Il basso può leggere
la melodia e i complementi drums possono leggere entrambe le parti; altre
relazioni possono cambiare l'ordine senza cambiare il riferimento ritmico.
Le risposte alla storia consentono reciprocità fra intervalli successivi.
Non esistono dipendenze circolari né iterazioni per far convergere le voci.

## Legame ritmico di basso e melodia

Il nuovo controllo `groove_follow`, da 0 a 1, ha lo stesso significato per
entrambi i generatori: peso del riferimento ritmico nella scelta degli
attacchi. Zero conserva la generazione ritmica autonoma; uno attribuisce
al riferimento il massimo peso. Non indica la percentuale di note da
duplicare dalle drums.

Il numero di note, il materiale melodico e la dinamica rimangono governati
dai rispettivi controlli. L'adesione può produrre coincidenze, anticipazioni
e incastri: le posizioni sono scelte rispetto al groove secondo le regole
della voce. Il basso conserva la funzione di `syncopation`; la melodia
conserva motivo, fasi dello sviluppo e pause.

`groove_follow` non sostituisce `rhythm_follow` del basso: quest'ultimo
descrive oggi il rapporto con la frase melodica e influenza anche durate
e accenti. L'implementazione deve mantenere distinti i riferimenti, senza
riutilizzare la stessa chiave attribuendole un significato diverso.
Con `groove_follow = 0` il riferimento nuovo non modifica il risultato.
`groove_follow` è la vista utente di una relazione verso il riferimento
ritmico. Le influenze concorrenti seguono il contratto comune per aspetto;
non vengono applicate una seconda volta dopo la composizione della voce.

Un legame positivo richiede un produttore di riferimento configurato e
valido; l'assenza va segnalata prima dell'esecuzione. Non si ignora il
controllo e non si sceglie implicitamente un'altra voce.

## Tessitura

Il riferimento principale è il contesto armonico della sezione. La
modalità predefinita sostiene il grado configurato. La sorgente aggiuntiva
può essere il basso o la melodia: la sua influenza riguarda gli appoggi
armonici, non la copia di ogni altezza o attacco.

Si definiscono una scelta esplicita della sorgente intonata e un grado
di influenza armonica da 0 a 1. Zero usa il sostegno di sezione; uno dà
massimo peso alle altezze rilevanti della sorgente, mantenendo il registro
configurato e la continuità. L'adesione ritmica agli ingressi resta una
dimensione separata dall'influenza armonica.

Per la relazione armonica della tessitura si propone `on_unavailable:
independent`: se la sorgente intonata è inattiva o silenziosa, la tessitura
usa l'appoggio di sezione e lo dichiara nella decisione. Il suo silenzio è
governato dalla propria presenza e dalle proprie regole musicali. Questo modifica il
contratto attuale di `follow_source = 1`, che produce silenzio con la
sorgente: richiede migrazione esplicita di configurazioni e preset e non
deve entrare come cambiamento implicito dell'attuale switch.

## Tempo, pause e cambi

- Il trasporto della sessione continua a fornire beat e BPM. Le drums
  guidano le scelte ritmiche, non il clock.
- Il riferimento conserva fase e andamento anche quando la parte drums
  è fuori organico, esclusa dalla presenza o sospesa da `silence`. Le altre
  voci possono mantenere il groove durante una pausa della batteria.
- Una frase melodica o di basso silenziosa rimane una frase vuota per
  chi la riceve. I complementi drums rispettano questa informazione.
- Le variazioni dei parametri valgono dalle finestre ancora da pianificare.
  Tutte le voci di una finestra ricevono lo stesso stato risolto.
- Stop, restart e discontinuità azzerano insieme i riferimenti temporali
  e lo stato dei generatori. Un normale cambio di sezione non azzera la fase.
- Preparare il riferimento non consuma due volte il periodo percussivo.
  Ripetere la stessa richiesta non fa avanzare la composizione.

## Collegamento al codice esistente

`PlanningRequest` passa oggi contesto armonico, frasi dipendenti, ruolo e
parametri. Deve acquisire un riferimento ritmico opzionale, indipendente
da `Phrase`. L'assenza resta valida per generatori che non lo utilizzano.
La preparazione del riferimento è una funzione esposta dal generatore
registrato, collegata dalla CLI; non aggiunge un'uscita MIDI o una traccia
artificiale al Live Set.

`MusicCoordinator` continua a ordinare le dipendenze e a passare i dati.
La preparazione e la finalizzazione delle drums devono utilizzare lo
stesso materiale risolto, seed e fase: non due generazioni indipendenti.
`variation` distingue riferimento regolare e sviluppo
della parte percussiva; non diventa l'adesione ritmica delle altre voci.

## Criteri di accettazione

- Nessun cambiamento con stili disattivati e nuovi legami a zero.
- Stesse richieste, parametri e seed producono le stesse frasi.
- Nessun ciclo di dipendenze, doppio avanzamento o riallineamento a ogni finestra.
- Pausa delle drums senza perdita del riferimento per le altre voci.
- Maggiore adesione riconoscibile confrontando una voce a parità degli altri parametri.
- Identità melodica, vincoli armonici, registro e articolazione rispettati.
- Controlli inattivi, sorgenti utilizzate e sostituzione armonica nei silenzi visibili nello stato.
- Configurazioni e preset migrati esplicitamente, senza reinterpretazioni silenziose.

Il [design degli stili percussivi](STILI-PERCUSSIVI.md) specifica i profili
di genere e le influenze multiple. La loro selezione non sostituisce i
controlli di adesione delle singole voci.
