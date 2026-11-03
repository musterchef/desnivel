'use strict';
const DesnivelMusic = (() => {
  const kinds = {ascent: 'salita', descent: 'discesa', level: 'pianura'};
  const roles = {melody: 'melodia', bass_line: 'basso', sustained_texture: 'tessitura', percussion: 'drums'};
  const format = value => typeof value === 'number'
    ? value.toLocaleString('it-IT', {maximumFractionDigits: 3}) : String(value);
  function node(tag, text, className) {
    const item = document.createElement(tag);
    if (text !== undefined) item.textContent = text;
    if (className) item.className = className;
    return item;
  }
  function planCard(title, plan, empty) {
    const card = node('article', undefined, 'plan-card');
    card.append(node('p', title, 'eyebrow'));
    if (!plan) {card.append(node('p', empty, 'muted')); return card;}
    card.append(node('h3', kinds[plan.section] || plan.section));
    card.append(node('p', `beat ${format(plan.start)}–${format(plan.start + plan.length_beats)} · root MIDI ${plan.root} · ${plan.scale}`, 'muted'));
    const parts = plan.local_trip?.parts;
    if (parts?.length) card.append(node('p', `km ${format(parts[0].start_distance_m / 1000)}–${format(parts.at(-1).end_distance_m / 1000)}`, 'muted'));
    return card;
  }
  function parameter(name, control) {
    const row = node('div', undefined, 'music-parameter');
    const label = node('dt', (control.label || name).toLowerCase());
    label.title = control.description || name;
    const value = node('dd');
    const choices = control.choices || [];
    const choice = choices.find(item => item[0] === control.value);
    value.append(node('span', choice ? choice[1].toLowerCase() : format(control.value)));
    const auto = control.automation;
    if (auto && !control.manual && auto.target !== control.value)
      value.append(node('span', ` → ${format(auto.target)}`, 'parameter-target'));
    const mode = control.manual === true ? 'manual' : control.manual === false ? 'auto' : 'configurato';
    value.append(node('small', mode, 'parameter-mode'));
    row.append(label, value);
    if (auto) row.title = `base ${format(auto.base)} · obiettivo ${format(auto.target)} · ${auto.reason}`;
    if (control.inactive_reason) row.append(node('p', control.inactive_reason, 'muted'));
    if (control.value_hint) row.append(node('p', `ultimo piano inviato: ${control.value_hint}`, 'muted'));
    return row;
  }
  let voiceSignature = '';
  function weatherSummary(voices, stale) {
    const entries = Object.entries(voices).filter(([, voice]) => voice.weather);
    const weather = entries[0]?.[1].weather;
    let text = 'stato non disponibile';
    if (weather) {
      const active = entries.filter(([, voice]) => voice.weather.status === 'active')
        .map(([id, voice]) => voice.name || id);
      const pending = entries.some(([, voice]) => voice.weather.pending);
      if (!weather.configured) text = 'non caricato';
      else if (!weather.enabled) text = pending ? 'disattivazione in coda' : 'disattivato';
      else {
        text = pending ? 'attivazione in coda' : active.length ? 'abilitato'
          : 'abilitato · nessuno strumento con nuovi contributi nel piano corrente';
      }
      if (active.length) text += ` · in uso su ${active.join(', ')}`;
    }
    return `${stale ? 'ultimo stato · ' : ''}meteo: ${text}`;
  }
  function render(state, stale) {
    const current = state.planning?.current;
    const upcoming = state.planning?.upcoming || [];
    document.getElementById('music-clock').textContent = `Live ${state.transport?.playing ? 'play' : 'stop'} · beat ${format(state.transport?.beat || 0)}`;
    document.getElementById('music-plans').replaceChildren(
      planCard('in esecuzione · piano inviato', current, 'Nessun piano in esecuzione.'),
      planCard('a seguire · già preparato', upcoming[0], 'Nessun piano futuro in coda.'));
    document.getElementById('music-notice').textContent = stale
      ? 'Dati non aggiornati: è mostrato l’ultimo stato ricevuto.'
      : 'La posizione segue il clock di Live; lo stato dei piani non conferma l’uscita audio. Valori effettivi → obiettivi automatici.';
    document.getElementById('weather-summary').textContent = weatherSummary(state.voices || {}, stale);
    const signature = JSON.stringify([state.voices, current?.start, state.adaptation_enabled]);
    if (signature === voiceSignature) return;
    voiceSignature = signature;
    const container = document.getElementById('music-voices');
    const open = new Set(Array.from(container.querySelectorAll('details[open]')).map(item => item.dataset.voice));
    const cards = Object.entries(state.voices || {}).map(([id, voice]) => {
      const card = node('article', undefined, 'voice-card');
      const heading = node('div', undefined, 'voice-heading');
      heading.append(node('h3', voice.name || id), node('span', voice.connected ? 'collegato' : 'scollegato', `connection ${voice.connected ? 'connected' : ''}`));
      card.append(heading);
      const phrase = current?.voices?.[id];
      const soundingRole = phrase ? roles[phrase.role] || phrase.role : 'nessuna frase corrente';
      const attacks = phrase ? ` · ${phrase.notes.length} ${phrase.notes.length === 1 ? 'nota' : 'note'} nella finestra` : '';
      card.append(node('p', soundingRole + attacks, 'voice-role'));
      card.append(node('p', `${id} · organico attuale: ${voice.active ? 'presente' : 'fuori'} · ruolo ${roles[voice.role] || voice.role || 'nessuno'}`, 'muted'));
      const weather = voice.weather;
      card.append(node('p', `meteo: ${weather?.label || 'stato non disponibile'}`, `weather-state weather-${weather?.status || 'unknown'}`));
      if (weather?.blocked_parameters?.length)
        card.append(node('p', `contributi esclusi da manual: ${weather.blocked_parameters.join(', ')}`, 'muted'));
      if (voice.presence) card.append(node('p', `presenza ${format(voice.presence.effective * 100)}% · auto ${format(voice.presence.automatic * 100)}% × ${format(voice.presence.multiplier)}`, 'muted'));
      if (phrase?.composition?.summary) card.append(node('p', phrase.composition.summary, 'composition-summary'));
      const adaptive = node('dl', undefined, 'parameter-list');
      const configured = node('dl', undefined, 'parameter-list');
      for (const [name, control] of Object.entries(voice.controls || {}))
        (control.automation || control.manual ? adaptive : configured).append(parameter(name, control));
      if (adaptive.childElementCount) card.append(adaptive);
      const details = node('details');
      details.dataset.voice = id;
      details.open = open.has(id);
      details.append(node('summary', 'configurazione e dettagli'));
      details.append(node('p', `preset: ${voice.preset || 'nessuno/custom'}`, 'muted'));
      if (!state.adaptation_enabled) details.append(node('p', 'Adattamento locale non attivo.', 'muted'));
      details.append(configured);
      card.append(details);
      return card;
    });
    container.replaceChildren(...cards);
  }
  function markStale() {
    document.getElementById('music-notice').textContent = 'Collegamento interrotto: è mostrato l’ultimo stato ricevuto.';
    const summary = document.getElementById('weather-summary');
    if (!summary.textContent.startsWith('ultimo stato')) summary.textContent = 'ultimo stato · '+summary.textContent;
  }
  return {render, markStale};
})();
if (typeof module !== 'undefined') module.exports = DesnivelMusic;
