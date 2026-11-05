'use strict';

const TRACK_STATUS = {
  available: 'disponibile', connected: 'associata', connecting: 'collegamento in corso',
  missing: 'non rilevata', conflict: 'da verificare', update_required: 'da aggiornare',
};
const STEP_NAMES = {
  destination: 'Scegli la traccia', name: 'Nome della voce', voice: 'Voce musicale',
  behavior: 'Comportamento', existing_voice: 'Voce da ricollegare', source: 'Sorgente del basso',
  texture_source: 'Sorgente della nota sostenuta', support: 'Sostegno ritmico', answer: 'Sorgente delle risposte',
  snake_source: 'Sorgente di Snake',
};
const RECORD_STATUS = {
  unprepared: 'Da preparare', preparing: 'Preparazione in corso', ready: 'Pronta',
  rewinding: 'Ritorno a zero', starting: 'Avvio in corso', recording: 'Registrazione in corso',
  stopping: 'Arresto in corso', error: 'Errore di registrazione',
};

function sessionModel(payload) {
  const state = payload.session;
  if (!state || typeof state !== 'object') throw new Error('Stato della sessione non valido');
  const setup = state.setup || {};
  const controls = state.controls || {};
  const fresh = Number.isFinite(payload.age_s) && payload.age_s < 3;
  return {
    state, setup, fresh,
    configuration: state.configuration || {name: 'Sessione', path: ''},
    tracks: setup.tracks || [],
    waiting: setup.status === 'waiting',
    editable: fresh && controls.edit_allowed === true,
    transportConnected: fresh && controls.transport_connected === true,
  };
}

async function sendCommand(command, fetcher = fetch) {
  const response = await fetcher('/api/control', {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(command),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Comando non accettato');
  return result;
}

function startSessionPanel() {
  const byId = id => document.getElementById(id);
  let model = null;
  let pending = false;
  let questionKey = '';
  let tracksKey = '';
  let pollTimer = null;

  function text(id, value) { byId(id).textContent = value; }
  function showError(message) {
    text('command-error', message || '');
    byId('command-error').hidden = !message;
  }
  function button(label, command, className = '') {
    const element = document.createElement('button');
    element.type = 'button';
    element.textContent = label;
    element.className = className;
    element.addEventListener('click', () => submit(command));
    return element;
  }
  function cell(content) {
    const element = document.createElement('td');
    element.textContent = content;
    return element;
  }

  function renderTracks() {
    const key = JSON.stringify([model.tracks, model.setup.step]);
    if (key === tracksKey) return;
    tracksKey = key;
    const body = byId('tracks');
    body.replaceChildren();
    for (const track of model.tracks) {
      const row = document.createElement('tr');
      const title = cell(track.name);
      const detail = document.createElement('small');
      detail.textContent = track.position ? `traccia ${track.position}` : track.reason || '';
      title.append(detail);
      const kind = track.kind === 'snake' ? 'Snake' : track.kind === 'voice' ? 'voce Python' : '—';
      const status = cell(TRACK_STATUS[track.status] || track.status);
      if (track.voice_name && track.voice_name !== track.name) {
        const voice = document.createElement('small');
        voice.textContent = track.voice_name;
        status.append(voice);
      }
      const action = cell('');
      if (model.setup.step === 'destination' && track.status === 'available' && track.choice) {
        action.append(button('Scegli', {action: 'setup_reply', value: String(track.choice)}));
      }
      row.append(title, cell(kind), status, action);
      body.append(row);
    }
    if (!model.tracks.length) {
      const row = document.createElement('tr');
      const empty = cell('Nessun controllo rilevato. Apri il set in Ableton e premi Cerca tracce.');
      empty.colSpan = 4;
      empty.className = 'empty';
      row.append(empty);
      body.append(row);
    }
  }

  function renderQuestion() {
    const setup = model.setup;
    const key = JSON.stringify([setup.step, setup.notice, setup.choices, setup.instructions]);
    if (key === questionKey) return;
    questionKey = key;
    const question = byId('question');
    question.replaceChildren();
    text('setup-title', STEP_NAMES[setup.step] || 'Una voce alla volta');
    text('setup-notice', setup.notice || 'Associa una traccia del set per aggiungere una voce musicale.');
    if (setup.step === 'name') {
      const form = document.createElement('form');
      form.className = 'name-form';
      const label = document.createElement('label');
      label.htmlFor = 'voice-name';
      label.textContent = 'Nome della voce · lascia vuoto per mantenere quello della traccia';
      const input = document.createElement('input');
      input.id = 'voice-name';
      input.name = 'voice-name';
      input.maxLength = 100;
      input.autocomplete = 'off';
      const next = document.createElement('button');
      next.type = 'submit';
      next.textContent = 'Continua';
      next.className = 'primary';
      form.addEventListener('submit', event => {
        event.preventDefault();
        submit({action: 'setup_reply', value: input.value});
      });
      form.append(label, input, next);
      question.append(form);
      input.focus();
    } else {
      const choices = document.createElement('div');
      choices.className = 'choices';
      for (const choice of setup.choices || []) {
        choices.append(button(choice.label, {action: 'setup_reply', value: choice.value}));
      }
      if (setup.step === 'destination') {
        choices.append(button('Istruzioni per una nuova traccia in Live', {action: 'setup_reply', value: '0'}));
      }
      for (const line of setup.instructions || []) {
        const item = document.createElement('p');
        item.textContent = line;
        choices.append(item);
      }
      question.append(choices);
    }
  }

  function updateControls() {
    if (!model) return;
    const available = model.fresh && !pending;
    const editing = available && model.editable;
    const busy = ['preparing', 'rewinding', 'starting', 'recording', 'stopping'].includes(model.state.recording?.status);
    const transport = available && model.transportConnected && !model.state.controls.restart_pending;
    for (const element of document.querySelectorAll('[data-action]')) {
      const action = element.dataset.action;
      let enabled = available;
      if (action === 'setup_begin' || action === 'setup_associate') {
        enabled = editing && !model.waiting && model.state.controls.setup_enabled;
      }
      if (action === 'setup_associate') enabled = enabled && Object.keys(model.state.voices || {}).length > 0;
      if (action === 'setup_save' || action === 'scan') enabled = available && !model.waiting;
      if (action === 'setup_cancel') enabled = available && model.waiting;
      if (['pause', 'resume', 'restart'].includes(action)) enabled = transport && !model.waiting;
      if (action === 'record_start') enabled = transport && !model.waiting && model.state.recording?.status === 'ready';
      if (action === 'record_stop') enabled = transport && busy;
      element.disabled = !enabled;
    }
    for (const element of byId('question').querySelectorAll('button, input')) element.disabled = !editing;
    for (const element of byId('tracks').querySelectorAll('button')) element.disabled = !editing;
    byId('record-prepare').disabled = !transport || model.waiting || busy;
    byId('cancel').hidden = !model.waiting;
  }

  function render(payload) {
    model = sessionModel(payload);
    const state = model.state;
    text('connection', model.fresh ? 'Collegato' : 'Stato non aggiornato');
    byId('connection').dataset.connected = String(model.fresh);
    text('session-name', model.configuration.name);
    text('session-file', model.configuration.path);
    text('session-journey', `Viaggio: ${state.trip?.stage || 'in attesa'}`);
    text('live-state', state.transport?.playing ? 'Live PLAY' : 'Live STOP');
    text('beat', `beat ${(state.transport?.beat || 0).toFixed(2)}`);
    byId('play').dataset.action = state.transport?.playing ? 'pause' : 'resume';
    text('play', state.transport?.playing ? 'Pausa' : 'Riprendi');
    const counts = model.setup.counts;
    text('counts', counts ? `${counts.detected} rilevate · ${counts.associated} associate · ${counts.connected} collegate` : 'In attesa dell’inventario.');
    renderTracks();
    renderQuestion();
    DesnivelMusic.render(state, !model.fresh);
    const diagnostics = byId('diagnostics');
    diagnostics.replaceChildren();
    for (const diagnostic of model.setup.diagnostics || []) {
      const line = document.createElement('p');
      line.textContent = diagnostic;
      diagnostics.append(line);
    }
    text('edit-reason', state.controls?.edit_reason || 'Modifica le associazioni a Live fermo.');
    text('record-state', RECORD_STATUS[state.recording?.status] || 'In attesa dello stato');
    const trip = state.trip;
    text('trip-summary', trip ? `${trip.stage} · ${(trip.progress * 100).toFixed(1)}% del viaggio` : 'In attesa del viaggio');
    showError(state.control_error || state.error || state.recording?.error);
    updateControls();
  }

  async function refresh() {
    const abort = new AbortController();
    const timeout = setTimeout(() => abort.abort(), 3000);
    try {
      const response = await fetch('/api/state', {signal: abort.signal});
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || 'Stato non disponibile');
      render(payload);
    } catch (error) {
      text('connection', 'Non collegato');
      DesnivelMusic.markStale();
      byId('connection').dataset.connected = 'false';
      showError(error.message);
      if (model) model.fresh = false;
      updateControls();
    } finally {
      clearTimeout(timeout);
    }
  }

  async function submit(command) {
    if (pending || !model?.fresh) return;
    pending = true;
    updateControls();
    try {
      await sendCommand(command);
      await refresh();
    } catch (error) {
      showError(error.message);
    } finally {
      pending = false;
      updateControls();
    }
  }

  for (const element of document.querySelectorAll('[data-action]')) {
    element.addEventListener('click', () => submit({action: element.dataset.action}));
  }
  byId('record-prepare').addEventListener('click', () => submit({action: 'record_' + byId('record-mode').value}));
  async function poll() {
    await refresh();
    pollTimer = setTimeout(poll, 500);
  }
  window.addEventListener('pagehide', () => clearTimeout(pollTimer), {once: true});
  poll();
}

if (typeof module !== 'undefined' && module.exports) module.exports = {sessionModel, sendCommand};
if (typeof document !== 'undefined') startSessionPanel();
