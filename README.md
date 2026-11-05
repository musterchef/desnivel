# Desnivel

*Ascoltare la forma di un viaggio.*

Desnivel è un motore di musica generativa multivoce basato sulle
registrazioni FIT/GPX di un viaggio in bicicletta del 2025, da Torino a
Castel del Monte. Interpreta il percorso attraverso armonia, ritmo,
dinamica e relazioni fra le voci.

## Funzionamento

1. **Viaggio (`trip`)**: legge le registrazioni, seleziona i tratti osservati
   e calcola distanza, quota, pendenza, velocità e stima di sforzo.
2. **Composizione (`music`)**: genera pattern e frasi indipendenti dai
   dispositivi. La direzione del percorso sceglie armonia, motivo e assetti;
   le voci sviluppano il materiale e reagiscono al contesto musicale.
3. **Adattatori e trasporto (`adapters`, `sinks`)**: traducono le strutture
   musicali nei protocolli delle destinazioni e trasmettono i messaggi.
4. **Sessione (`cli`, `viewer`)**: governa replay e pianificazione, espone
   stato e controlli nel terminale e nel pannello web locale, con una vista
   separata del viaggio sulla mappa.

Il launcher avvia una sessione vuota e permette di aggiungere voci dal
terminale o dal pannello web, associandole alle tracce con controllo Desnivel
in Ableton Live. Le due interfacce usano gli stessi comandi e lo stesso stato;
il motore può funzionare senza interfaccia web.
L’organico di esempio comprende melodia, basso, tessitura e percussioni. Il trasporto di Live fornisce il clock musicale;
il viaggio avanza con replay lineare oppure timeline allocata in beat.
Il meteo storico può contribuire ai controlli automatici. La sessione
permette anche di preparare e registrare tracce audio e MIDI in Live.
Snake può partecipare alla sessione tramite il suo controllo dedicato;
il player del basso resta disponibile come banco di prova separato.

## Per iniziare

- [Sessione guidata](doc/SESSIONE-GUIDATA.md): aggiunta delle voci e associazione delle tracce Live.
- [Comandi e launcher](doc/COMANDI.md): installazione, scelta della tappa e avvio.
- [Sessione multivoce](doc/SESSIONE-MULTIVOCE.md): device, trasporto, dashboard e registrazione.
- [Guida ai controlli](doc/GUIDA-DEVICE.md): valori di partenza per le quattro voci.
- [Stato del progetto](doc/STATO.md): capacità operative e limiti.
- [Architettura](doc/ARCHITETTURA.md): componenti e responsabilità.
- [Indice della documentazione](doc/README.md): riferimenti tecnici, proposte e archivio.
