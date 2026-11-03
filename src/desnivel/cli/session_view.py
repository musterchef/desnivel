"""Vista globale del terminale, aggiornata anche senza cambi di stato."""
import sys
import shutil
import textwrap
import time


def _time(seconds):
    seconds = int(seconds)
    return f'{seconds//3600:02d}:{seconds//60%60:02d}:{seconds%60:02d}'


def _value(value):
    return value if isinstance(value, str) else f'{value:.3g}'


def render_session(state):
    trip, transport = state['trip'], state['transport']
    decision = state['decisions']['director']
    rows = [f"DESNIVEL | {state['state']} | Live {'PLAY' if transport['playing'] else 'STOP'} | beat {transport['beat']:.2f}",
            f"Viaggio {trip['progress']:.2%} | {_time(trip['elapsed_s'])} / {_time(trip['duration_s'])} | {trip['distance_m']/1000:.2f} km | replay {trip['speed']:g}x",
            f"ADESSO · director: {decision['section']} | root MIDI {decision['root']} | {decision['scale']}"]
    weather = state.get('controls', {}).get('contexts', {}).get('weather')
    weather_label = 'non caricato' if weather is None else 'attivo' if weather['enabled'] else 'disattivato'
    rows.append(f'METEO: {weather_label} | M: attiva/disattiva dalle prossime finestre da pianificare')
    if state.get('timeline'):
        timeline = state['timeline']
        rows[1] = (f"Viaggio {trip['progress']:.2%} | {trip['distance_m']/1000:.2f} km | "
                   f"timeline {timeline['beat']:g} / {timeline['total_beats']:g} beat")
        if timeline.get('beats_per_km') is not None:
            rows[1] += f" | {timeline['beats_per_km']:g} beat/km"
    section_source = state.get('section', {}).get('trip')
    if 'current' in state.get('planning', {}):
        current = state['planning']['current']
        rows.append((f"IN ESECUZIONE · {current['section']} | beat {current['start']:g}–"
                     f"{current['start']+current['length_beats']:g} | root MIDI {current['root']} | {current['scale']}")
                    if current else 'IN ESECUZIONE · nessun piano corrente')
    if state.get('trip_music'):
        music = state['trip_music']
        rows.append(f"  Identità GPX: {music['palette']} ({music['palette_source']}) | "
                    f"pendenza assoluta media {music['profile']['mean_absolute_slope_ratio']:.2%} | "
                    f"motivo {music['motif_degrees']} ({music['motif_source']})")
        direction = state.get('section', {}).get('direction')
        if direction:
            rows.append(f"  Armonia: {direction['state']} | root {direction['sources']['root']} | "
                        f"scala {direction['sources']['scale']}")
    if section_source:
        rows.append(f"  Macrosezione {section_source['index']+1}: {section_source['kind']} | "
                    f"km {section_source['start_distance_m']/1000:.2f}–{section_source['end_distance_m']/1000:.2f} | "
                    f"{len(section_source['zone_indices'])} zone interne")
    # I blocchi vengono ordinati alla fine: contesto, piano inviato, voci, dettagli.
    voice_start = len(rows)
    parameter_rows = []
    for name, voice in state['voices'].items():
        connection = 'collegato' if voice['connected'] else 'SCOLLEGATO'
        if voice['active']:
            activity = 'in organico'
        elif voice.get('next_entry_progress') is not None:
            activity = f"fuori organico; ingresso al {voice['next_entry_progress']:.0%}"
        else:
            activity = 'fuori organico di questa sezione'
        origin = 'manuale' if voice['role_mode'] == 'manual' else 'da sezione'
        rows.append(f"  {name} ({voice['name']}): {connection} | {activity} | {voice['role'] or 'nessun ruolo'} ({origin})")
        values = ' · '.join(f"{key}={_value(control['value'])}"
                           + (f" → {_value(control['automation']['target'])}"
                              if not control.get('manual') and control.get('automation')
                              and control['automation']['target'] != control['value'] else '')
                           for key, control in voice['controls'].items())
        manual = [key for key, control in voice['controls'].items() if control.get('manual')]
        mode = 'auto' if not manual else 'manual: ' + ', '.join(manual)
        presence = voice.get('presence')
        summary = f"    {mode}"
        if presence is not None:
            summary += (f" | presenza {presence['effective']:.0%}"
                        f" (auto {presence['automatic']:.0%} × {presence['multiplier']:g})")
        changing = [f"{key}={_value(control['value'])}"
                    + (f" → {_value(control['automation']['target'])}"
                       if control.get('automation') and not control.get('manual')
                       and control['automation']['target'] != control['value'] else '')
                    for key, control in voice['controls'].items()
                    if control.get('automation') or control.get('manual')]
        if changing:
            summary += ' | ' + ' · '.join(changing)
        rows.append(summary)
        parameter_rows.append(f"  {name} | preset: {voice['preset'] or 'nessuno/custom'} | {values}")
    voice_end = len(rows)
    plan = state['decisions']['coordinator']
    if plan is None:
        rows.append('Coordinator: nessun piano in attesa.')
    else:
        end = plan['start']+plan['length_beats']
        phase = ('preparato in anticipo' if transport['beat'] < plan['start'] else
                 'intervallo corrente' if transport['beat'] < end else 'intervallo concluso')
        rows.append(f"Coordinator: piano inviato [{plan['start']:g}, {end:g}] beat | sezione {plan['section']} | {phase}")
        local = plan.get('local_trip')
        if local and local['status'] == 'available':
            parts = local['parts']
            slope = local.get('profile', {}).get('slope_ratio')
            measure = f"pendenza {slope:+.1%}" if slope is not None else 'pendenza non disponibile'
            rows.append(f"  Tratto pianificato: km {parts[0]['start_distance_m']/1000:.2f}–"
                        f"{parts[-1]['end_distance_m']/1000:.2f} | {measure}")
        elif local:
            rows.append(f"  Contesto locale non disponibile: {local['reason']}")
        observation = plan.get('observation')
        if observation:
            rows.append(f"  Osservazione musicale: {observation['available_beats']:g} / "
                        f"{observation['lookback_beats']:g} beat accettati disponibili")
        if plan.get('trip'):
            rows.append(f"  Assetto della macrosezione {plan['trip']['index']+1}: {plan['trip']['kind']}")
        rows.append('  Ordine generatori: ' + (' -> '.join(plan['order']) or 'nessuna voce attiva'))
        plan_summary_end = len(rows)
        for name in plan['order']:
            voice = plan['voices'][name]
            notes = voice['notes']
            composition = voice.get('composition')
            if composition:
                rows.append(f"  Composizione {name}: {composition['summary']}")
            preview = ', '.join(f"{n['pitch']}@{n['beat']:g}" for n in notes[:8])
            if len(notes) > 8:
                preview += ', ...'
            rows.append(f"  {name}: {voice['role']} | riferimenti: {', '.join(voice['dependencies']) or 'nessuno'} | {len(notes)} note MIDI@beat: {preview or 'silenzio'}")
        rows.append('  Piano inviato; non è una conferma audio dello strumento.')
    if plan is None:
        plan_summary_end = len(rows)
    rows = (rows[:voice_start] + ['', 'PIANO · coordinator']
            + rows[voice_end:plan_summary_end] + ['', 'VOCI · valori effettivi · → obiettivo auto']
            + rows[voice_start:voice_end]
            + ['', 'PARAMETRI · configurazione completa'] + parameter_rows
            + (['', 'DETTAGLI DEL PIANO'] + rows[plan_summary_end:] if plan else []))
    if state['error']:
        rows.append('ERRORE: ' + state['error'])
    if state.get('control_error'):
        rows.append('COMANDO: ' + state['control_error'])
    if state['state'] == 'finished':
        rows.append('Tappa conclusa. Premi R per tornare a zero, poi Play per ripartire.')
    rows.append('C: collega tutte le Voice | Spazio: pausa/riprendi | R: torna a zero | M: meteo | Ctrl+C: chiudi.')
    return '\n'.join(rows)


def fit_terminal(frame, width, height):
    """Impagina senza wrap implicito e conserva stato, voci, errori e comandi."""
    width, height = max(1, width-1), max(1, height-1)
    rows = frame.splitlines()
    wrapped = [line for row in rows for line in textwrap.wrap(
        row, width=width, subsequent_indent='  ', replace_whitespace=False) or ['']]
    if len(wrapped) <= height:
        return '\n'.join(wrapped)
    # Riduce prima i dettagli; stato, collegamenti, errori e comandi restano visibili.
    required = {i for i, row in enumerate(rows) if i < 3 or row.startswith((
        'IN ESECUZIONE', 'Coordinator:', 'ERRORE:', 'COMANDO:', 'Tappa conclusa.', 'C:'))
        or ' | in organico | ' in row or ' | fuori organico' in row}
    selected = {i: [textwrap.shorten(rows[i], width=width, placeholder='…')] for i in required}
    available = height-len(selected)-1
    for i, row in enumerate(rows):
        if i in selected:
            continue
        lines = textwrap.wrap(row, width=width, subsequent_indent='  ', replace_whitespace=False) or ['']
        if len(lines) <= available:
            selected[i] = lines
            available -= len(lines)
    compact = [line for i in sorted(selected) if i != len(rows)-1 for line in selected[i]]
    footer = [textwrap.shorten('Dettagli ridotti: ampliare il terminale; stato completo nel file JSON.',
                               width=width, placeholder='…'),
              textwrap.shorten(rows[-1], width=width, placeholder='…')]
    if len(compact)+len(footer) > height:
        # Terminali estremamente bassi: precedenza agli errori e ai comandi.
        errors = [textwrap.shorten(row, width=width, placeholder='…') for row in rows
                  if row.startswith(('ERRORE:', 'COMANDO:'))]
        compact = compact[:max(0, height-len(footer)-len(errors))]+errors
    return '\n'.join((compact+footer)[-height:])


class TerminalSessionView:
    def __init__(self, stream=None, clock=time.monotonic, interval=1.):
        self.stream = stream if stream is not None else sys.stdout
        self.clock, self.interval = clock, interval
        self.last_refresh = None

    def update(self, state):
        now = self.clock()
        if self.last_refresh is not None and now-self.last_refresh < self.interval:
            return
        frame = render_session(state)
        if self.stream.isatty():
            size = shutil.get_terminal_size()
            frame = fit_terminal(frame, size.columns, size.lines)
            self.stream.write('\x1b[H\x1b[2J'+frame+'\x1b[J')
        else:
            self.stream.write(frame+'\n\n')
        self.stream.flush()
        self.last_refresh = now
