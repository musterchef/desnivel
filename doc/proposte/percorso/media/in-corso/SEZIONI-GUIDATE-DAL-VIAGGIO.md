# Sezioni guidate dal viaggio

Stato: separazione delle responsabilità approvata; analisi del profilo e
raggruppamento delle zone in macrosezioni e assegnazione degli assetti musicali
implementati. Il contesto locale alimenta le politiche adattive delle voci.
Nuovi eventi geografici e gestione degli intervalli incerti restano proposti.

L'obiettivo è rendere percepibile l'evoluzione del viaggio nella composizione,
mantenendo disponibile la modalità con sezioni manuali.

La struttura concordata separa:

1. Analisi neutra del percorso: zone, posizione e misure che le motivano.
2. Assegnazioni musicali configurabili in JSON: interpretazione delle zone
   mediante voci, ruoli e parametri effettivamente supportati dai generatori.
3. Esecuzione: Director e Coordinator applicano le assegnazioni e coordinano
   le voci attraverso le interfacce musicali generiche.

L'[analisi disponibile](../../../../ANALISI-PERCORSO.md) classifica il profilo per
pendenza e persistenza. Un passaggio separato raggruppa le zone adiacenti
secondo famiglie configurabili; il report mostra macrosezioni e dettaglio.
Il [collegamento alla sessione musicale](../../../../SESSIONE-MULTIVOCE.md) assegna un
assetto configurato a ciascuna famiglia. L'eventuale assorbimento di brevi interruzioni, il riconoscimento di
scollinamenti e altri eventi restano da definire.

Gli assetti delle macrosezioni sono definiti in un JSON separato e applicati
alla prossima finestra da pianificare. La configurazione d'ascolto fornita
propone comportamenti differenti per le famiglie; tali scelte sono modificabili.

La direzione concordata distingue un assetto musicale della macrosezione
(voci, ruoli e impostazioni di base) dalle variazioni interne associate alle
fasce originali. Il primo livello è operativo. Le regole approvate di
[direzione adattiva](../../alta/in-corso/DIREZIONE-ADATTIVA.md) definiscono responsabilità,
controllo manuale e ritorno all'automazione. Le mappature e le transizioni
implementate sono descritte in [Direzione musicale](../../../../DIREZIONE-MUSICALE.md#adattamento-dei-parametri).
Le ulteriori regole delle sezioni seguenti rimangono proposte.

## Pause interne e impegno altimetrico

Stato: criteri concordati; disponibile soltanto la misura del contesto
locale nel [report di analisi](../../../../ANALISI-PERCORSO.md). La selezione delle
pause, il nuovo raggruppamento e il punteggio altimetrico non sono implementati.

Per una pianura tra due salite o tra due discese, il riferimento locale è
la media armonica delle lunghezze dei due tratti adiacenti della stessa
famiglia. Entrambi i confronti sono disponibili nel report. Il rapporto tra lunghezza della
pianura e riferimento sarà confrontato con una soglia configurabile, ancora
da calibrare sui percorsi. Sotto la soglia la pianura potrà essere una pausa
interna; alla soglia o sopra rimarrà autonoma. Le sezioni originali e i loro
riferimenti devono essere conservati; la valutazione precede eventuali
raggruppamenti e l'allocazione finale dei beat.

Separatamente, si propone di riconoscere la salita con maggiore impegno
altimetrico, sommando sui tratti della salita `lunghezza in km × pendenza
positiva percentuale²`. Il calcolo userà le pendenze smussate dell'analisi.
Il punteggio non rappresenta la fatica effettiva del ciclista e non attribuisce
categorie ufficiali. Eventuali classi e conseguenze musicali restano da
valutare dopo il confronto con i percorsi e l'esperienza del viaggio.

## Verifica sulle tappe 1 e 10 per la percussione

Stato: analisi eseguita con le configurazioni correnti; collegamento dei
cambiamenti interni alla generazione percussiva da progettare e implementare.

I report sono riproducibili con `desnivel.cli.analyze_trip`, usando
`analisi-percorso.json`, `macrosezioni-percorso.json` e `organico.json`
per l'allocazione temporale. Questa prima verifica conserva l'asse di
distanza originale, prima dell'esclusione delle deviazioni GPS. I dati seguenti si riferiscono alle quote
interpolate dall'analisi; il dislivello è netto, non ascesa cumulata.

| Caso | Tratto | Lunghezza | Dislivello netto | Pendenza media | Beat allocati |
|---|---|---:|---:|---:|---:|
| Salita finale della tappa 1 | km 85,60–89,68 | 4,08 km | +221 m | 5,42% | 44 |
| Salita della tappa 10 con maggiore dislivello netto fra le macrosezioni `ascent` | km 20,70–25,10 | 4,40 km | +281 m | 6,39% | 24 |

La salita finale della tappa 1 contiene quattro zone: km 85,60–87,60 al
2,40%; 87,60–87,90 al 7,48%; 87,90–88,20 al 3,47%; 88,20–89,68 al
9,47%. Termina con il GPX: il percorso non conferma uno scollinamento
successivo all'arrivo.

La salita selezionata nella tappa 10 contiene tre zone: km 20,70–21,10
al 2,21%; 21,10–24,10 al 7,45%; 24,10–25,10 al 4,86%.

### Collegamento attualmente disponibile

`cli/trip_direction.py` conserva misure e riferimenti alle zone nei metadati
`trip` di ogni macrosezione. `EnsembleRuntime` li espone nello stato e nelle
decisioni. La chiamata al generatore riceve invece `MusicalContext`
(indice, nome, tonica e scala), parametri dell'assegnazione e frasi delle
dipendenze. Le pendenze interne e la posizione all'interno della
macrosezione non vengono trasmesse al generatore.

La direzione corrente assegna alla percussione soltanto un rapporto di
velocity per famiglia. Il materiale percussivo dura 32 beat; la sequenza
di sviluppo avanza per cicli di quel materiale, indipendentemente dalle
zone del percorso. La salita selezionata nella tappa 10 dura 24 beat
allocati: non copre da sola un ciclo completo del materiale.

Le durate dei due casi non sono proporzionali alle rispettive lunghezze:
l'allocatore riserva i minimi e distribuisce il residuo all'interno di
ciascuna tappa. La tappa 1 ha 37 macrosezioni, la tappa 10 ne ha 84.

### Passo proposto

Per ciascuna finestra musicale, collegare la posizione nella timeline al
tratto di percorso rappresentato. In modalità allocata si propone una
progressione uniforme della distanza all'interno di ciascun intervallo
assegnato alla macrosezione; è una scelta di mappatura da verificare, non
la riproduzione del tempo registrato nel GPX.

Un passaggio separato deve interpretare le misure neutre del tratto e
produrre indicazioni musicali configurabili. Director e Coordinator
mantengono interfacce musicali generiche. Il generatore percussivo dovrà
costruire gli attacchi in relazione a tali indicazioni, alle altre voci e
al proprio materiale recente. La scelta del timbro dovrà avvenire durante
la composizione del gesto, superando la lista attuale di colpi già collocati.

I due casi permettono di valutare comportamenti distinti: intensificazione
finale nella tappa 1; persistenza del tratto ripido e successivo
alleggerimento, ancora in salita, nella tappa 10. Le conseguenze sonore e
le regole di scelta restano proposte da definire mediante ascolto. La
generazione non dovrà presumere uno scollinamento soltanto perché una
sezione sta terminando.

## Piano per il contesto interno delle macrosezioni

Stato: piano esteso da revisionare. Il primo insieme di contesto locale
e osservazione musicale è disponibile secondo la
[direzione adattiva](../../alta/in-corso/DIREZIONE-ADATTIVA.md); le politiche adattive dei primi controlli sono implementate. Provenienza
estesa e descrittori del movimento restano da realizzare.
Il piano riguarda tutte le voci e conserva
la separazione tra analisi neutra, interpretazione musicale e composizione.

### 1. Dati disponibili e loro provenienza

Verifica del codice e dei 12 GPX presenti in `gpx/`:

| Informazione | Stato attuale | Lavoro necessario prima dell'uso musicale |
|---|---|---|
| Latitudine e longitudine | Lette dal GPX e ricampionate in `Track` | Controllare discontinuità e conservare i riferimenti ai punti sorgente |
| Quota | Presente in tutti i punti dei 12 GPX; filtrata e ricampionata dal loader | Rendere riconoscibili i valori originali, interpolati e non disponibili |
| Tempi | Presenti e strettamente crescenti in tutti i 12 GPX verificati | Conservare validità, intervalli mancanti e confini dei segmenti |
| Velocità | Calcolata da distanza fra coordinate e differenza dei tempi | Individuare intervalli anomali e definire aggregazione e disponibilità |
| Pendenza | Disponibile sia come canale del loader sia come analisi smussata per distanza | Usare per il terreno la misura dell'analisi, con la sua scala spaziale esplicita |
| Macrosezioni e zone figlie | Disponibili con confini, distanze e misure | Conservare questi riferimenti nel contesto locale |
| Regolarità della velocità e variazioni locali | Non calcolate come descrittori condivisi | Definire intervallo di osservazione, formula e copertura minima |
| Significato dei luoghi | Non disponibile | Eventuali annotazioni geografiche richiedono una sorgente esplicita |

`loader/_parse.py` legge coordinate, quota e tempi; non legge una velocità
da sensore. Nelle tappe 1 e 10 non sono presenti campi aggiuntivi di
velocità. I massimi della velocità derivata fra punti consecutivi sono
circa 2.037,3 km/h nella tappa 1 e 114,3 km/h nella tappa 10. Questi valori
motivano un controllo degli intervalli sorgente prima di trasformare i
campioni in decisioni musicali; non individuano da soli la causa del picco.

`loader/_derive.py` interpola tempi parzialmente mancanti e costruisce
una griglia a un secondo se mancano tutti. `Track.metadata` attualmente
non conserva tale provenienza. Il parser concatena inoltre i trackpoint
dei segmenti GPX. Il nuovo contesto dovrà distinguere dati osservati,
derivati, ricostruiti e non disponibili, senza interpretare una velocità
su tempi ricostruiti come velocità osservata del viaggio.

La stima `effort` già presente combina velocità e pendenza con pesi
configurati: non è una misura della fatica e non sostituisce la lettura
separata di terreno e movimento. Accelerazione, cadenza, potenza,
frequenza cardiaca, ambiente e stato emotivo non sono ingressi disponibili
di questa generazione.

**Consegna:** misure e provenienza ispezionabili nel report, con intervalli
sospetti evidenziati. Criteri di qualità configurabili e motivi di
esclusione visibili; nessuna correzione distruttiva dei GPX o cambiamento
implicito del rilevamento delle zone.

### 2. Una corrispondenza esplicita tra musica e percorso

Riutilizzare `Timeline`, `TimelineManager` e la gestione delle finestre
esistenti. Separare l'indice logico del viaggio dal beat assoluto di Live
e dalla velocità originale della bicicletta.

In modalità allocata, ogni finestra rappresenterà un intervallo di
distanza della macrosezione. La proposta iniziale è ripartire quella
distanza uniformemente fra le finestre assegnate, come già avviene per
la progressione mostrata dal runtime. La pianificazione deve usare la
posizione della finestra futura, non quella attualmente in ascolto.

In modalità lineare, la selezione del tratto seguirà i tempi dei tratti
osservati, con soste prolungate e interruzioni escluse, e il fattore di
replay. L'intervallo sorgente di una finestra richiede una
regola esplicita in relazione al tempo musicale; non può essere ricavato
da `--speed` da solo, perché beat e secondi appartengono ad assi diversi.
Il contratto per entrambi i modi dovrà indicare estremi sorgente e punto
di osservazione, gestendo i confini di macrosezione e le soste.

La stessa funzione di corrispondenza dovrà alimentare runtime e report.
Cambiare BPM o velocità di replay non dovrà cambiare il valore della
velocità originale letto nello stesso punto del viaggio.

**Consegna:** per ogni finestra, beat logico, tratto sorgente, macrosezione
e zone attraversate visibili e verificabili. I valori di analisi non
vengono ricalcolati nel ciclo dei messaggi OSC.

### 3. Descrittori locali neutri riutilizzabili

In `trip/`, affiancare alle misure delle macrosezioni un contesto locale
privo di riferimenti musicali. Usare le finestre spaziali di analisi già
disponibili per la pendenza e i dati temporali validi per il movimento.
Le scale di osservazione vanno espresse in metri o secondi sorgente,
separatamente dalla dimensione delle finestre musicali.

Primo insieme da definire:

- posizione, distanza percorsa e residua nella macrosezione;
- pendenza locale e suo cambiamento rispetto a un intervallo precedente;
- velocità rappresentativa, sua variazione e regolarità nell'intervallo
  osservato, con copertura dei campioni validi;
- distanza su cui persiste l'andamento, per distinguere un cambiamento
  breve da uno sostenuto;
- coordinate e riferimenti alla sorgente, utilizzabili per ispezione o
  per future annotazioni esplicite dei luoghi.

Le formule, le unità e i criteri di disponibilità vanno fissati prima
dell'implementazione. Per esempio, regolarità della velocità significa
dispersione dei valori su un intervallo dichiarato, non una nuova
etichetta priva di misura. Valore zero e dato non disponibile restano
distinti. Non si ricavano categoria ambientale o significato musicale
dalla sola coppia latitudine/longitudine.

**Consegna:** funzioni pure e un contesto locale condiviso. Definizioni e
misure confrontabili sui due casi reali, anche quando una finestra copre
più zone o un intervallo di qualità insufficiente.

### 4. Interpretazione musicale configurabile

Estendere il collegamento esistente in `cli/trip_direction.py`, mantenendo
separata la valutazione delle regole dalla gestione della sessione.
Il passaggio legge misure neutre e produce indicazioni musicali comuni e
parametri per le voci. Director e Coordinator ricevono soltanto contesti
musicali; coordinate, dati GPX e controlli specifici dei dispositivi non
entrano nelle loro responsabilità.

Usare come base `direzione-viaggio.json`, che definisce già gli assetti per
famiglia. La proposta è aggiungervi le regole di variazione, evitando un
nuovo file per ogni fenomeno o strumento. Lo schema andrà introdotto
insieme al suo interprete e alla validazione degli ingressi e delle uscite.

Le regole devono dichiarare misura usata, intervallo di riferimento,
trasformazione, destinazione musicale e durata della transizione. La
normalizzazione deve conservare anche i valori fisici: una variazione
piccola non deve diventare estrema solo perché è la maggiore della tappa.
Pendenza, velocità e persistenza restano dimensioni distinguibili; non
confluiscono obbligatoriamente in un unico indice di energia.

Applicare la precedenza fra assetto, adattamento e intervento manuale
definita nel [contratto della direzione adattiva](../../alta/in-corso/DIREZIONE-ADATTIVA.md).
Il flag `manual` mantiene il singolo parametro; il rilascio lo restituisce
all'automazione dal contesto corrente. Il flag, le politiche dei primi controlli e le transizioni graduali sono
disponibili nella sessione guidata dal GPX.

**Consegna:** report delle indicazioni prodotte dalle regole, prima di
modificare gli algoritmi compositivi. Per ogni cambiamento mostrare dato
sorgente, regola applicata e risultato musicale, compreso il caso di dato
non disponibile. Le regole proposte non rappresentano associazioni
universali fra terreno e musica.

### 5. Generazione con continuità e memoria

Melodia e percussione devono leggere lo stesso contesto musicale, con
interpretazioni proprie delle rispettive responsabilità. Non occorre
avere un compositore unico né duplicare l'analisi del viaggio nelle voci.

Per la melodia, partire dai controlli e dallo sviluppo esistenti;
verificare quali indicazioni possano già influenzare attività,
articolazione e sviluppo. Cambiare parametri richiede preservare la
continuità delle frasi ed evitare che una variazione locale riavvii il
motivo o alteri la fase ritmica in modo involontario.

Per la percussione, sostituire la lista di colpi collocati e la successione
automatica delle trasformazioni con la costruzione di gesti. Le decisioni
su attacchi, accenti, silenzi e timbri devono dipendere da indicazioni
musicali, frasi delle altre voci e storia recente. Il catalogo dei pad
rimane configurazione; avere un suono disponibile non impone di usarlo
periodicamente. La dipendenza non deve ridursi al solo inseguimento degli
attacchi del basso o alla cancellazione vicino alla melodia.

La memoria deve conservare gesti riconoscibili e permettere ripetizione,
trasformazione e risposta. La casualità eventualmente utilizzata deve
essere riproducibile tramite seed e subordinata ai vincoli musicali.
Il significato concreto dei gesti e i criteri di scelta saranno definiti
dopo aver verificato le indicazioni del punto precedente.

**Consegna:** confronto d'ascolto con stesso GPX, timeline, BPM, suoni e
seed; prima una voce per isolare l'effetto, poi il dialogo dell'organico.

### Ordine di lavoro e verifiche

1. Provenienza, qualità e descrittori neutri dei dati, ispezionabili nel
   report, senza cambiare la generazione.
2. Corrispondenza della timeline con il percorso e selezione del contesto
   delle finestre future. Decisione esplicita sui confini e sulla modalità
   lineare prima di collegare il runtime.
3. Regole di interpretazione con anteprima delle indicazioni musicali e
   precedenza dei controlli definita.
4. Collegamento alla melodia e sostituzione della costruzione percussiva,
   con memoria e verifiche d'ascolto separate.

Test essenziali: dati e tempi mancanti, segmenti discontinui e picchi;
intervalli costanti e variazioni note; confini delle finestre e delle
macrosezioni; indipendenza della velocità sorgente da BPM e replay;
stessa richiesta ripetuta senza doppio avanzamento; continuità e limiti
delle frasi MIDI; corrispondenza fra report e runtime.

L'ascolto delle tappe 1 e 10 dovrà verificare intensificazione,
persistenza e alleggerimento, poi il comportamento andrà confrontato con
una pianura e una discesa. A parità di famiglia, modificare i dati locali
validi deve poter cambiare le decisioni secondo le regole configurate;
modificare soltanto la posizione assoluta di Live non deve inventare un
cambiamento nel viaggio. I test automatici verificano tali relazioni,
mentre coerenza espressiva e piacere sonoro richiedono ascolto.

### Prima consegna: ispezione della velocità sorgente

Stato: implementata l'ispezione descritta in
[ANALISI-PERCORSO.md](../../../../ANALISI-PERCORSO.md#ispezione-dei-punti-gpx-originali).
L'esclusione delle deviazioni locali è ora implementata come descritto
nel documento di analisi; i descrittori locali condivisi restano da sviluppare.
I riferimenti di verifica includono anche la tappa 2 per la discesa.

Nella tappa 1, i punti GPX 2814–2815 riportano un passaggio da
45,013097 / 7,669268 a 45,014656 / 7,676121 fra le 09:16:52 e le
09:16:53 UTC del 15 settembre 2025: 565,9 m in un secondo, pari a
2.037,3 km/h derivati. I punti precedenti mostrano uno spostamento
di circa 549,7 m in cinque secondi verso la prima posizione e una
successiva ripetizione della stessa coordinata. La sequenza suggerisce
un'anomalia di posizione; la causa nel dispositivo sorgente non è nota.

Nella tappa 2 il massimo derivato è 451,6 km/h: 250,9 m in due secondi
fra i punti 22773–22774, alle 16:36:53–16:36:55 UTC del 16 settembre
2025. L'intervallo si colloca al km sorgente non corretto 97,005–97,256.
Una discesa di riferimento è la macrosezione km 70,50–74,00, con
dislivello netto −290,4 m e pendenza media −8,30%; è distinta da tale
picco. I confini riportati dipendono dall'analisi e dalla distanza attuali.

Nel solo passaggio di filtraggio, prima della selezione dei tratti
osservati, con il limite configurato a 70 km/h la tappa 1 esclude
il punto 2491 e il gruppo 2813–2814, riconnettendo gli adiacenti a circa
25,7 e 16,6 km/h. La distanza passa da 89,684 a 88,245 km. L'analisi
ricalcolata contiene 35 macrosezioni: nel finale distingue una salita
km 84,10–85,80, un tratto `level` km 85,80–86,20 e una salita fino
all'arrivo km 86,20–88,245. Questi confini sostituiscono quelli della
prima verifica per i prossimi confronti d'ascolto.

Nella tappa 2 nessun punto soddisfa i criteri locali di esclusione.
Tre intervalli restano non risolti e non forniscono misure di movimento;
i relativi punti e distanze sono conservati. Il salto da 451,6 km/h
rimane nel registro originale, ma non è utilizzato come velocità del viaggio.
Nella tappa 10 il punto 24846 è escluso: gli adiacenti 24845–24847
si riconnettono in 42 secondi a circa 3,1 km/h, riducendo la deviazione
dell'83%. Il limite temporale locale del filtro è 60 secondi; confrontando
tutti i 12 GPX con il limite iniziale di 30 secondi, questa è l'unica
esclusione aggiuntiva. Due altri intervalli della tappa 10 restano non risolti.

### Revisione delle interruzioni e possibili gallerie

Stato: elenco delle segnalazioni implementato nel report di tutte le
tappe. La classificazione degli intervalli mediante annotazioni e il
trattamento esteso delle perdite di segnale sono proposte da implementare.

La revisione dei 12 GPX, con i criteri iniziali descritti nel documento
di analisi, produce 42 gruppi di segnalazioni. Gli intervalli con velocità
oltre 70 km/h sono 32; gli altri criteri includono intervalli senza
campioni con spostamento e riprese dopo coordinate quasi ferme. Una parte
dei casi può corrispondere a soste reali. Non sono classificati come
errori o gallerie.

Ogni annotazione dovrà riferirsi all'ID della tappa e ai punti sorgente,
conservando separati indizio automatico, osservazione del ciclista e
trattamento applicato. Il caso discusso della tappa 2 è
`tappa_02:p22773-22774`; l'attraversamento di una galleria è al momento
supportato da un riscontro cartografico coerente. I confini temporali
della perdita di segnale rimangono da confermare.

Per un tratto confermato come galleria o perdita del segnale si propone:

1. Conservare GPX originale, estremi e tempo trascorso nei registri.
   La selezione del viaggio usa un asse attivo che esclude le interruzioni;
   il tratto non è automaticamente interpretato come sosta. Un'eventuale
   durata musicale dell'evento geografico richiederà una scelta distinta.
2. Definire l'intervallo incerto sulla base della revisione: può iniziare
   prima del salto e comprendere coordinate bloccate. Il solo campione
   oltre soglia non identifica l'intero periodo privo di osservazioni.
3. Rendere non disponibili le misure non supportate nel tratto, senza
   introdurre velocità zero, pendenza di pianura o sforzo misurato. Gli
   estremi osservati non determinano distanza effettiva o pendenza interna.
4. Conservare distinta la distanza geometrica fra gli estremi da un
   eventuale percorso ricostruito. Qualsiasi ricostruzione richiederà una
   sorgente esplicita, una decisione separata e l'etichetta di stima.
5. Fare arrivare alla futura interpretazione musicale la disponibilità
   dei dati: l'assenza del segnale non dovrà produrre automaticamente una
   pausa musicale, un'accelerazione o un cambio di terreno.

I confini della perdita di segnale, l'eventuale ricostruzione e il
comportamento musicale durante l'incertezza restano da definire dopo
le annotazioni. La revisione non cambia il filtro già applicato.

### Riscontri cartografici delle gallerie

Stato: verifica eseguita sulle 42 segnalazioni mediante estratti dell'API
ufficiale OpenStreetMap e confronto geometrico con i punti GPX originali.
I risultati sono una verifica del dataset, senza collegamento automatico
al trattamento degli intervalli nel runtime.

Risultato: 12 riscontri forti agli imbocchi, quattro sequenze coerenti
di gallerie da confermare, 25 casi senza riscontro sufficiente e un caso
con copertura parziale. Il confronto usa cartografia attuale; non verifica
lo stato storico e l'accessibilità dei percorsi nel 2025.

Per i riscontri forti sono stati confrontati imbocchi opposti entro
150 metri dagli estremi GPX, scarto delle direttrici entro 30 gradi e
avanzamento proiettato di almeno il 40% lungo la galleria, controllando
l'eventuale senso unico OSM. Le sequenze sono state esaminate separatamente
per geometria, ordine e verso. Gallerie solo ferroviarie o autostradali
vicine e passaggi sotto edifici non costituiscono da soli un riscontro
del percorso ciclistico.

| Tappa e punti sorgente | Riscontro | Fonte OSM |
|---|---|---|
| 2 · 19796–19797 | Forte: Galleria Maria Giuseppa Rossello | [way 122851859](https://www.openstreetmap.org/way/122851859) |
| 2 · 21707–21708 | Forte: Galleria Invrea | [way 39440265](https://www.openstreetmap.org/way/39440265) |
| 2 · 22685–22686 | Sequenza del Lungomare De André | [way 39443024](https://www.openstreetmap.org/way/39443024), [39443014](https://www.openstreetmap.org/way/39443014), [39443303](https://www.openstreetmap.org/way/39443303) |
| 2 · 22773–22774 | Forte: galleria ciclopedonale del Lungomare De André | [way 39443017](https://www.openstreetmap.org/way/39443017) |
| 3 · 10682–10683 | Forte: galleria della Via Aurelia | [way 13857772](https://www.openstreetmap.org/way/13857772) |
| 3 · 13123–13124 | Forte: galleria dell'Aurelia | [way 120832965](https://www.openstreetmap.org/way/120832965) |
| 3 · 15491–15497 | Forte: Gallerie di Sant'Anna | [way 27925576](https://www.openstreetmap.org/way/27925576) |
| 3 · 26011–26042 | Sequenza della ciclopedonale Maremonti | [way 517421834](https://www.openstreetmap.org/way/517421834), [517452870](https://www.openstreetmap.org/way/517452870), [748999086](https://www.openstreetmap.org/way/748999086), [96913876](https://www.openstreetmap.org/way/96913876) |
| 3 · 26180–26208 | Sequenza Maremonti / La Francesca | [way 25681861](https://www.openstreetmap.org/way/25681861), [591046954](https://www.openstreetmap.org/way/591046954) |
| 4 · 6958–6960 | Forte: galleria di Via Litoranea, SP370 | [way 28483169](https://www.openstreetmap.org/way/28483169) |
| 4 · 8372–8373 | Forte: galleria di Via Litoranea, SP370 | [way 42480682](https://www.openstreetmap.org/way/42480682) |
| 4 · 8760–8761 | Forte: galleria di Via delle Cinque Terre, SP370 | [way 42480684](https://www.openstreetmap.org/way/42480684) |
| 8 · 10491–10492 | Forte: Galleria di Tiberio | [way 80978717](https://www.openstreetmap.org/way/80978717) |
| 8 · 11007–11043 | Sequenza Trepani / Flacca / Vannelamare | [way 62118474](https://www.openstreetmap.org/way/62118474), [100396539](https://www.openstreetmap.org/way/100396539), [100396544](https://www.openstreetmap.org/way/100396544) |
| 12 · 377–380 | Forte: galleria sulla SS89 Garganica | [way 26403104](https://www.openstreetmap.org/way/26403104) |
| 12 · 538–539 | Forte: Galleria Montesaraceno, SS688 | [way 38480177](https://www.openstreetmap.org/way/38480177) |

Per il caso `tappa_02:p22773-22774`, le distanze approssimate dagli
imbocchi sono 2 e 12 metri e lo scarto delle direttrici circa 2 gradi.
Per `tappa_03:p10682-10683` sono circa 38 e 33 metri, con scarto di
4 gradi. Questi riscontri sostengono l'attraversamento e l'ipotesi di
segnale degradato; non determinano da soli quando il segnale sia mancato.

Il caso `tappa_07:p4323-4324` è stato verificato agli estremi e su due
sottoaree; l'API ha rifiutato altre aree troppo estese. Il lungo tragitto
intermedio resta indeterminato. L'assenza di un riscontro sufficiente
negli altri casi non dimostra l'assenza di gallerie.

Il report locale `output/tappe/verifica-gallerie.html` conserva tutte le
42 valutazioni, schemi delle geometrie, metriche e collegamenti alle fonti.
Il JSON corrispondente e gli estratti OSM sono nella stessa cartella di
output. La gestione delle gallerie nel contesto musicale resta da
implementare secondo il piano degli intervalli incerti.

### Valutazione geografica dei 25 casi senza riscontro di galleria

Stato: esame dei punti originali e degli estratti cartografici eseguito.
Le cause specifiche rimangono ipotesi da confermare con il ciclista.
L'esame distingue:

- tre deviazioni con ritorno trattate dal filtro: due nella tappa 1 e una
  presso piazza della Costituzione, zona stazione/autostazione di San Severo,
  nella tappa 10;
- sedici gruppi di picchi brevi: alcuni in ambiente urbano e altri su
  discese secondo le quote GPX. Possibili irregolarità di posizione o
  aggiornamento e possibili velocità effettive vicine al limite restano
  distinti. Non sono eliminati punti sulla sola base della prossimità a
  edifici o vegetazione;
- sei lunghi intervalli senza campioni, elencati sotto. Le durate possono
  contenere sia soste sia spostamenti non registrati.

| Caso | Contesto geografico | Intervallo senza campioni | Ipotesi da verificare |
|---|---|---:|---|
| `tappa_01:p12258-12259` | Bra, SS702 / strada Crosassa, area commerciale | 27 min 38 s | Sosta o registrazione sospesa; possibile permanenza in un edificio |
| `tappa_05:p7765-7766` | Via Empolese → Cerbaia in Val di Pesa | 32 min 49 s | Sosta e movimento non registrato |
| `tappa_06:p5784-5785` | Bagnoregio, via Garibaldi / Q8 → viale Agosti | 65 min 31 s | Sosta, visita o registrazione sospesa |
| `tappa_09:p12757-12758` | Benevento, Arco di Traiano → via Gaetano Rummo | 85 min 6 s | Sosta o visita urbana con parte non registrata |
| `tappa_11:p5924-5925` | Vieste, lungomare Cristoforo Colombo → via Santa Maria di Merino | 64 min 4 s | Sosta o visita urbana, registrazione sospesa |
| `tappa_12:p15985-15986` | SS170 dir/A → Castel del Monte | 61 min 37 s | Mancata registrazione di circa 11,4 km fra gli estremi; causa non determinabile |

Il caso di Camerana (`tappa_02:p7475-7476`) presenta un picco a circa
71 km/h dopo valori immediatamente precedenti di 61–66 km/h, in una
discesa secondo le quote GPS. Può essere un breve superamento reale della
soglia: resta una segnalazione, senza esclusione spaziale.

Diversi casi della tappa 5 mostrano coppie di intervalli con velocità
circa doppia su un secondo e circa dimezzata sui due successivi. Per
esempio `p13604-13605` passa da circa 35–36 km/h a 70,3 e poi a 16,8;
la media sui tre secondi è circa 34,6 km/h. La sequenza è compatibile con
aggiornamenti irregolari o distribuzione temporale dei campioni; non si
correggono gli orari sulla base di tale ipotesi.

Il report `output/tappe/casi-aperti-valutazione.html`, con JSON
corrispondente, conserva tutte le 25 valutazioni, riferimenti OSM, strade
e luoghi vicini, descrittori di confronto e domande per il ciclista.
La prossimità a un esercizio non dimostra una visita né la presenza o
l'apertura dello stesso nel 2025. I descrittori di revisione non sono
valori sostitutivi applicati alla generazione musicale.

### Esclusione generale di soste e interruzioni

Stato: implementata nel loader comune a tutte le tappe. Le cause dei
tratti non registrati non sono richieste per escluderli dall'elaborazione.
Non sono presenti condizioni per nomi di tappe o luoghi.

La selezione precede derivazione dei canali e ricampionamento: separa
interruzioni oltre 30 secondi fra campioni, dati strutturalmente non
continui e sequenze quasi ferme per almeno 60 secondi entro 10 metri
dal punto iniziale. I criteri sono configurabili in `GpxConfig`.
Camminata con spostamento rilevabile e brevi soste rimangono nel viaggio.

Ogni tratto conservato viene elaborato separatamente e mantiene i
riferimenti a punti e tempi originali in `Track.segments`. Tempo e
distanza fra tratti separati non vengono inventati né allocati alla
composizione. Anche l'analisi del terreno rispetta le separazioni,
evitando pendenze prodotte dalle differenze di quota ai due estremi.
Il report distingue tempo sorgente e tempo osservato e conserva le
interruzioni nel registro. Le annotazioni geografiche e la loro futura
interpretazione musicale restano distinte da questa selezione.
