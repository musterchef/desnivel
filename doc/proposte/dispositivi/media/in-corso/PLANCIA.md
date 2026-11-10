# Proposta: plancia globale

Stato: realizzazione parziale. La [dashboard della sessione](../../../../SESSIONE-MULTIVOCE.md#mappa-del-viaggio)
mostra mappa, piani correnti e futuri, voci, parametri e meteo; offre controlli
di trasporto e registrazione. Le sezioni seguenti conservano i requisiti
della proposta e le decisioni ancora aperte.

La dashboard legge lo snapshot JSON prodotto da `EnsembleRuntime.snapshot()`.
Il server HTTP accoda i comandi al ciclo della sessione.

## Informazioni da mostrare

- Posizione nel viaggio e sezione corrente.
- Stato Play/Stop ricevuto da Live e collegamento della sorgente del trasporto.
- Parti configurate, attive, collegate o mancanti.
- Ruolo della sezione e ruolo manuale per ciascuna parte.
- Controlli effettivi e frasi pianificate, distinguendoli dall'esecuzione sonora.
- Errori e motivo dell'attesa della sessione.

La prima versione della sessione mantiene il viaggio indipendente dalla numerazione delle battute di Live. Stop sospende replay e suono; Play riprende dal punto raggiunto.

## Decisioni aperte

- Eventuali ulteriori controlli globali oltre a trasporto e registrazione.
- Gestione della selezione di tappa e configurazione prima dell'avvio.
