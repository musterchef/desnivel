'use strict';
const DesnivelMusic = (() => {
  const kinds = {ascent: 'salita', descent: 'discesa', level: 'pianura'};
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
      : 'La posizione segue il clock di Live; lo stato dei piani non conferma l’uscita audio.';
    document.getElementById('weather-summary').textContent = weatherSummary(state.voices || {}, stale);
  }

  function markStale() {
    document.getElementById('music-notice').textContent = 'Collegamento interrotto: è mostrato l’ultimo stato ricevuto.';
    const summary = document.getElementById('weather-summary');
    if (!summary.textContent.startsWith('ultimo stato')) summary.textContent = 'ultimo stato · '+summary.textContent;
  }
  return {render, markStale};
})();
if (typeof module !== 'undefined') module.exports = DesnivelMusic;
