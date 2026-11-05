"""Collega analisi neutra del percorso, direzione musicale e configurazione."""
from copy import deepcopy
import json
from pathlib import Path

from desnivel.trip.analysis import analyze_track
from desnivel.trip.sections import group_zones
from desnivel.trip.profile import describe_profile, section_intensity
from desnivel.music.harmony import validate_palettes, validate_context, select_palette, choose_context, pitch_classes
from desnivel.music.melodic.route import route_motif, validate_motif
from desnivel.music.automation import AdaptiveContext, bounded


def adaptive_context(local_trip):
    """Interpreta le misure locali come indicazioni musicali normalizzate."""
    profile = local_trip.get('profile', {})
    if local_trip.get('status') != 'available' or profile.get('status') != 'available':
        return AdaptiveContext(unavailable_reason=local_trip.get('reason') or profile.get('reason') or 'profile_incomplete')
    change = profile['slope_change_ratio']
    persistence = profile['zone_persistence_m']
    return AdaptiveContext(
        bounded(profile['mean_absolute_slope_ratio']/.08, 0, 1),
        bounded(abs(change)/.04, 0, 1) if change is not None else None,
        bounded(persistence/profile['slope_window_m'], 0, 1) if persistence is not None else None)


def _validate_override(data, palette_ids):
    if not isinstance(data, dict) or data.keys()-{'palette', 'root', 'scale', 'motif_degrees'}:
        raise ValueError('override musicale: campi ammessi palette, root, scale e motif_degrees')
    validate_context(data)
    if 'palette' in data and (not isinstance(data['palette'], str) or data['palette'] not in palette_ids):
        raise ValueError('override della tavolozza sconosciuto')
    if 'motif_degrees' in data:
        validate_motif(data['motif_degrees'])


def _resolve(track, path):
    path = Path(path)
    definition = json.loads(path.read_text(encoding='utf-8'))
    required = {'analysis', 'grouping', 'families'}
    if not isinstance(definition, dict) or required-definition.keys() or definition.keys()-required-{'automatic_music'}:
        raise ValueError('la direzione richiede analysis, grouping, families ed eventuale automatic_music')
    for key in ('analysis', 'grouping'):
        if not isinstance(definition[key], str) or not definition[key]:
            raise ValueError(f'{key} deve indicare un file JSON')
    analysis_config = json.loads((path.parent/definition['analysis']).read_text(encoding='utf-8'))
    grouping_config = json.loads((path.parent/definition['grouping']).read_text(encoding='utf-8'))
    analysis = analyze_track(track, analysis_config)
    grouping = group_zones(analysis, grouping_config)
    arrangements = definition['families']
    if not isinstance(arrangements, dict) or set(arrangements) != set(grouping_config['families']):
        raise ValueError('ogni famiglia configurata richiede un assetto musicale, senza famiglie aggiuntive')
    automatic = definition.get('automatic_music')
    if 'automatic_music' in definition and automatic is None:
        raise ValueError('automatic_music deve essere una configurazione, non null')
    for family, arrangement in arrangements.items():
        if (not isinstance(arrangement, dict) or 'assignments' not in arrangement
                or arrangement.keys()-{'root', 'scale', 'assignments'}
                or automatic is None and set(arrangement) != {'root', 'scale', 'assignments'}):
            raise ValueError(f'{family}: richiesti assignments e, senza automatic_music, root e scale')
        validate_context(arrangement)
        if not isinstance(arrangement['assignments'], dict):
            raise ValueError(f'{family}: assignments deve contenere le assegnazioni delle voci')
    if automatic is None:
        return [{**deepcopy(arrangements[s['kind']]), 'name': s['kind'], 'from_progress': s['from_progress'],
                 'trip': deepcopy(s)} for s in grouping['sections']], None, analysis
    required = {'palettes', 'switch_margin', 'motif'}
    if (not isinstance(automatic, dict) or required-automatic.keys()
            or automatic.keys()-required-{'override', 'stage_overrides'}):
        raise ValueError('automatic_music richiede palettes, switch_margin e motif; override facoltativi')
    validate_palettes(automatic['palettes'], automatic['switch_margin'])
    motif = automatic['motif']
    if not isinstance(motif, dict) or set(motif) != {'generators', 'points', 'span_degrees'}:
        raise ValueError('motif richiede generators, points e span_degrees')
    targets = motif['generators']
    if (not isinstance(targets, list) or not targets or any(not isinstance(t, str) or not t for t in targets)
            or len(set(targets)) != len(targets)):
        raise ValueError('generators del motivo deve contenere identificativi distinti')
    palette_ids = {p['id'] for p in automatic['palettes']}
    override = automatic.get('override', {})
    stage_overrides = automatic.get('stage_overrides', {})
    _validate_override(override, palette_ids)
    if not isinstance(stage_overrides, dict) or any(not isinstance(k, str) or not k for k in stage_overrides):
        raise ValueError('stage_overrides richiede identificativi di tappa non vuoti')
    for values in stage_overrides.values():
        _validate_override(values, palette_ids)
    effective_override = {**override, **stage_overrides.get(track.stage_id, {})}
    profile = describe_profile(analysis, motif['points'])
    generated_motif = route_motif(profile['shape_normalized'], motif['span_degrees'])
    degrees = deepcopy(effective_override.get('motif_degrees', generated_motif))
    palette = select_palette(automatic['palettes'], profile['mean_absolute_slope_ratio'], effective_override.get('palette'))
    decision = {'stage': track.stage_id, 'profile': profile, 'palette': palette['id'],
                'palette_source': 'override' if 'palette' in effective_override else 'profile',
                'threshold': palette['from_mean_absolute_slope_ratio'],
                'motif_degrees': degrees, 'generated_motif_degrees': generated_motif,
                'motif_source': 'override' if 'motif_degrees' in effective_override else 'profile',
                'motif_generators': list(targets), 'overrides': deepcopy(effective_override)}
    sections, previous, previous_effective = [], None, None
    for source in grouping['sections']:
        local = section_intensity(analysis, source)
        target = min(1., local/(2*profile['mean_absolute_slope_ratio'])) if profile['mean_absolute_slope_ratio'] else 0.
        state = choose_context(palette, target, previous, automatic['switch_margin'])
        section = deepcopy(arrangements[source['kind']])
        sources = {key: 'family' if key in section else 'profile' for key in ('root', 'scale')}
        for key in ('root', 'scale'):
            section.setdefault(key, state[key])
            if key in effective_override:
                section[key] = effective_override[key]
                sources[key] = 'stage_override' if key in stage_overrides.get(track.stage_id, {}) else 'override'
        common = sorted(pitch_classes(*previous_effective) & pitch_classes(section['root'], section['scale'])) if previous_effective else []
        section.update(name=source['kind'], from_progress=source['from_progress'], trip=deepcopy(source),
                       direction={'palette': palette['id'], 'state': state['id'], 'target_intensity': target,
                                  'mean_absolute_slope_ratio': local, 'automatic_root': state['root'],
                                  'automatic_scale': state['scale'], 'sources': sources, 'common_pitch_classes': common})
        sections.append(section)
        previous, previous_effective = state, (section['root'], section['scale'])
    return sections, decision, analysis


def load_trip_sections(track, path):
    """Sezioni risolte per report e chiamanti che richiedono soltanto i contesti."""
    return _resolve(track, path)[0]


def prepare_trip_config(track, config, path):
    """Risolve sezioni e materiale della tappa senza modificare gli ingressi."""
    sections, decision, analysis = _resolve(track, path)
    resolved = deepcopy(config)
    resolved['sections'] = sections
    resolved['trip_analysis'] = analysis
    if 'arrangement' in config:
        for section in sections:
            section['assignments'] = deepcopy(config['arrangement'])
        if decision is not None:
            decision['motif_generators'] = [name for name, spec in config['generators'].items()
                                            if spec['type'] == 'motif']
    if decision is not None:
        for name in decision['motif_generators']:
            if name not in resolved['generators'] or resolved['generators'][name]['type'] != 'motif':
                raise ValueError(f'generatore del motivo automatico sconosciuto o non supportato: {name}')
            resolved['generators'][name]['degrees'] = list(decision['motif_degrees'])
        resolved['trip_music'] = decision
    return resolved
