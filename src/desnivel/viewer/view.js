'use strict';
const el = id => document.getElementById(id);
const number = (n, digits = 1) => n.toLocaleString('it-IT', {minimumFractionDigits: digits, maximumFractionDigits: digits});
const duration = s => [Math.floor(s / 3600), Math.floor(s / 60) % 60, Math.floor(s) % 60].map(n => String(n).padStart(2, '0')).join(':');
const states = {playing: 'In viaggio', paused: 'Viaggio in pausa', stopped: 'In pausa', waiting_for_transport: 'In attesa del trasporto', waiting_for_devices: 'In attesa delle voci', finished: 'Viaggio concluso', closed: 'Sessione chiusa', error: 'Errore nella sessione'};
async function getJSON(path) {
  const response = await fetch(path, {signal: AbortSignal.timeout(4000)});
  if (!response.ok) throw new Error(`Dati non disponibili (${response.status})`);
  return response.json();
}
async function start() {
  let paused = false, pendingCommand = false;
  async function command(action) {
    if (pendingCommand) return;
    pendingCommand = true;
    try {
      const response = await fetch('/api/control', {method: 'POST',
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify({action}),
        signal: AbortSignal.timeout(4000)});
      if (!response.ok) throw new Error(`Comando rifiutato (${response.status})`);
      el('command-status').textContent = 'Comando inviato alla sessione.';
    } catch (error) {
      el('command-status').textContent = error.message;
    } finally {
      pendingCommand = false;
    }
  }
  el('pause').onclick = () => command(paused ? 'resume' : 'pause');
  el('restart').onclick = el('restart-finished').onclick = () => command('restart');
  el('record-prepare').onclick = () => command('record_'+el('record-mode').value);
  el('record-start').onclick = () => command('record_start');
  el('record-stop').onclick = () => command('record_stop');
  el('skin').addEventListener('change', event => {
    document.documentElement.dataset.skin = event.target.value;
  });
  const route = await getJSON('/api/route');
  el('stage').textContent = route.stage.replaceAll('_', ' ');
  let map, marker, passed, outline, following = false, position, tileError = false;
  if (typeof L !== 'undefined') {
    map = L.map('map', {scrollWheelZoom: false});
    const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
    tiles.on('tileerror', () => { tileError = true; });
    outline = L.polyline(route.segments.map(points => points.map(p => p.slice(1))), {className: 'route-outline', color: '#647e73', weight: 4, opacity: .65}).addTo(map);
    passed = L.polyline([], {className: 'route-passed', color: '#c45c37', weight: 5}).addTo(map);
    const first = route.segments[0][0].slice(1);
    marker = L.circleMarker(first, {className: 'route-position', radius: 8, color: '#fffdf7', weight: 3, fillColor: '#c45c37', fillOpacity: 1}).addTo(map);
    const fit = () => map.fitBounds(outline.getBounds(), {padding: [35, 50], maxZoom: 15});
    const follow = value => { following = value; el('follow').setAttribute('aria-pressed', String(value)); };
    el('fit').onclick = () => {follow(false); fit();};
    el('follow').onclick = () => {follow(!following); if (following && position) map.panTo(position);};
    map.on('dragstart', () => follow(false));
    const resize = new ResizeObserver(() => map.invalidateSize());
    resize.observe(el('map'));
    fit();
  } else {
    el('map').textContent = 'La libreria della mappa non è disponibile. Controlla la connessione Internet e ricarica la pagina.';
    el('fit').disabled = el('follow').disabled = true;
  }
  async function refresh() {
    try {
      const {session: state, age_s: age} = await getJSON('/api/state');
      const trip = state.trip;
      if (trip.stage !== route.stage) throw new Error('La sorgente dello stato è cambiata: riavvia la vista con la sessione.');
      const stale = age > 3;
      const capture = state.recording;
      const busy = capture && ['preparing','rewinding','starting','stopping','recording'].includes(capture.status);
      el('record-prepare').disabled = stale || !capture || busy || state.state === 'closed';
      el('record-mode').disabled = stale || !capture || busy;
      el('record-start').disabled = stale || capture?.status !== 'ready' || !capture?.tracks?.length || state.state === 'closed';
      el('record-stop').disabled = stale || !capture || ['unprepared','ready'].includes(capture.status);
      const captureLabels = {unprepared:'REC da preparare',preparing:'Preparazione REC…',ready:'REC pronta',
        rewinding:'Ritorno a zero…',starting:'Avvio REC…',recording:'Registrazione in corso',stopping:'Arresto REC…',error:'Errore REC'};
      el('record-status').textContent = capture ? capture.error || `${captureLabels[capture.status]} · ${capture.mode || '—'} · ${capture.tracks.length} tracce` : '';
      DesnivelMusic.render(state, stale);
      paused = state.controls?.paused || false;
      el('pause').textContent = paused ? 'Riprendi' : 'Pausa';
      el('pause').disabled = stale || ['finished', 'closed', 'error'].includes(state.state);
      el('restart').disabled = el('restart-finished').disabled = stale || state.state === 'closed';
      el('finished').hidden = state.state !== 'finished';
      el('status').textContent = stale ? 'Stato non aggiornato' : (states[state.state] || state.state);
      el('notice').textContent = state.error || state.control_error || (stale ? 'La sessione non aggiorna più i dati. È mostrata l’ultima posizione ricevuta.' :
        tileError ? 'Cartografia non disponibile. Il percorso e la posizione restano visibili.' : '');
      el('distance').textContent = number(trip.distance_m / 1000);
      el('total').textContent = number(trip.total_distance_m / 1000);
      el('remaining').textContent = `${number(Math.max(0, trip.total_distance_m - trip.distance_m) / 1000)} km`;
      el('percent').textContent = `${number(trip.progress * 100)}%`;
      el('progress').value = trip.progress;
      el('elapsed').textContent = `${duration(trip.elapsed_s)} / ${duration(trip.duration_s)}`;
      const kinds = {ascent: 'Salita', descent: 'Discesa', level: 'Pianura'};
      el('section').textContent = kinds[state.section.name] || state.section.name;
      el('timing-label').textContent = state.timeline ? 'Timeline' : 'Replay';
      el('timing').textContent = state.timeline ? `${number(state.timeline.beat, 0)} / ${number(state.timeline.total_beats, 0)} beat` : `${number(trip.speed, 0)}×`;
      const frame = DesnivelPosition.frameAt(route.segments, trip.elapsed_s);
      position = frame.position;
      if (position) {
        el('coordinates').textContent = position.map(n => number(n, 5)).join(' · ');
        el('coordinates').href = `https://www.openstreetmap.org/?mlat=${position[0]}&mlon=${position[1]}#map=14/${position[0]}/${position[1]}`;
        if (map) {
          marker.setLatLng(position);
          passed.setLatLngs(frame.completed);
          if (following) map.panTo(position, {animate: false});
        }
      }
    } catch (error) {
      el('record-prepare').disabled = el('record-start').disabled = el('record-stop').disabled = true;
      DesnivelMusic.markStale();
      el('pause').disabled = el('restart').disabled = el('restart-finished').disabled = true;
      el('status').textContent = 'Collegamento interrotto';
      el('notice').textContent = `${error.message}. L’ultima posizione ricevuta resta visibile.`;
    } finally {
      window.setTimeout(refresh, 250);
    }
  }
  refresh();
}
start().catch(error => {el('status').textContent = 'Vista non disponibile'; el('notice').textContent = error.message;});
