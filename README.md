# Desnivel

*Ascoltare la forma di un viaggio.*

Desnivel è un progetto di musica generativa che trasforma i dati di un viaggio reale in composizione sonora.  
Nasce da un percorso in bicicletta compiuto nel **2025 da Torino a Castel del Monte**: giorni di pedalata, lentezza, fatica fisica e paesaggi che mutano da nord a sud dell'Italia.

L'idea alla base del progetto è semplice: **il corpo in movimento misura il mondo**. La traccia registrata durante il cammino non è un semplice archivio di coordinate geografiche, ma una **partitura latente** che racchiude ritmi, gradienti di sforzo, pause e cambiamenti di territorio. Desnivel non illustra il viaggio con una musica di sottofondo: ne ascolta la struttura interna e la traduce in suono.

---

## I tre livelli di lettura

### 1. Dal cammino al suono (L'esperienza umana)
Pedalare per ore al giorno trasforma la percezione del tempo: la velocità si riduce e ogni dislivello diventa fatica corporea, ogni discesa respiro, ogni sosta silenzio o sospensione.  
Desnivel traduce questi contrasti:
- **La salita e lo sforzo** intensificano la densità musicale e la tensione armonica.
- **La pianura e la velocità** aprono lo spazio ritmico e distendono le durate.
- **Le soste** diradano gli eventi sonori, lasciando spazio a silenzi o risonanze prolungate.

### 2. Architettura polifonica e composizione (La musica)
Il sistema è concepito per governare un insieme di voci musicali coordinate che dialogano in tempo reale:
- **Linee guida del territorio**: le tappe definiscono ambienti sonori, scale musicali (modi dorici, frigi, lidii o pentatonici) e percorsi armonici che si evolvono con l'avanzamento geografico.
- **Contrappunto e reattività**: le voci non procedono per semplice raddoppio, ma ascoltano il contesto e si distribuiscono compiti diversi (sostegno armonico, risposte ritmiche negli spazi lasciati liberi da altre linee, oppure incastri poliritmici).
- **Intervento esecutivo**: la composizione generativa ammette modulazioni dinamiche durante l'ascolto per variare densità, mobilità degli intervalli, registri e articolazione.

### 3. Struttura del sistema (La tecnologia)
Il motore è organizzato in strati indipendenti:
1. **Analisi del viaggio (`trip`)**: legge FIT e GPX, seleziona i tratti osservati, ricampiona i punti e calcola velocità, quota, pendenza e stima di sforzo. Nei FIT usa gli eventi di pausa e ripresa registrati; nei GPX può usare un FIT corrispondente come riferimento temporale.
2. **Motore compositivo (`music`)**: traduce le metriche fisiche e le relazioni tra le parti in strutture musicali astratte (`Pattern`, `Phrase`), indipendenti dallo strumento finale.
3. **Adattatori e trasporto (`adapters`, `sinks`)**: traducono i modelli musicali nei protocolli di controllo richiesti dalle destinazioni (OSC, MIDI).
4. **Ambiente di ascolto**: il clock musicale (BPM) è gestito dal sistema sonoro ricevente ed è svincolato dalla velocità di replay del viaggio. Come primo banco di prova per ascoltare il sistema in esecuzione, il progetto utilizza attualmente Ableton Live con un sequencer di riferimento per la linea melodica e un generatore per la linea di basso.

---

## Per iniziare

- [Comandi rapidi e installazione](doc/COMANDI.md): come configurare l'ambiente, avviare il replay di una tappa e provare le sessioni di ascolto.
- [Guida pratica ai device](doc/GUIDA-DEVICE.md): quali valori impostare per ottenere i comportamenti musicali desiderati.
- [Le tappe e i percorsi modali](doc/TAPPE-E-PRESET.md): guida all'ascolto delle tappe (Levanto, Firenze, Sabaudia, Peschici) e delle loro evoluzioni armoniche.
- [Architettura del sistema](doc/ARCHITETTURA.md): organizzazione dei package, flusso dati e contratti.
- [Indice completo della documentazione](doc/README.md).
