from dataclasses import replace
from functools import partial
import json
from pathlib import Path
import pytest

from desnivel.music.director import MusicalContext
from desnivel.music.phrases import Note, Phrase
from desnivel.music.sequence.material import compose
from desnivel.music.sequence.settings import ROLES
from desnivel.adapters.snake_control import bank_parameters

CONTEXT = MusicalContext(0, 'level', 60, 'minor')
SOURCE = Phrase(4, (Note(0, 67, .5, 90), Note(1, 70, 2, 85)))
CONFIG = json.loads((Path(__file__).resolve().parents[3]/'presets/snake.json').read_text())
DEFAULTS = {role: {**spec['parameters'], 'pulse': spec['pulse']['slowest']}
            for role, spec in CONFIG['music']['roles'].items()}
compose = partial(compose, phrasing=CONFIG['music']['phrasing'])
bank_parameters = partial(bank_parameters, paths=CONFIG['paths'])


def test_roles_change_register_gate_activity_and_duration_without_device_dependencies():
    material = {role: compose(CONTEXT, role, DEFAULTS[role]) for role in ROLES}
    assert sum(material['melody'].gates) > sum(material['bass_line'].gates) > sum(material['sustained_texture'].gates)
    assert min(material['bass_line'].notes) < min(material['melody'].notes) < min(material['sustained_texture'].notes)
    assert material['sustained_texture'].lengths_ms[0] > material['melody'].lengths_ms[0]
    assert material['melody'] == compose(CONTEXT, 'melody', DEFAULTS['melody'])


@pytest.mark.parametrize('role', ROLES)
def test_autonomous_and_coordinated_are_independent_of_role_and_silent_sources_are_explicit(role):
    independent = compose(CONTEXT, role, DEFAULTS[role])
    coordinated = compose(CONTEXT, role, DEFAULTS[role], coordinated=True, source=SOURCE)
    assert coordinated != independent
    assert {n % 12 for n in coordinated.notes} <= {7, 10}
    assert not any(compose(CONTEXT, role, DEFAULTS[role], coordinated=True, source=Phrase(4, ())).gates)
    with pytest.raises(ValueError, match='sorgente'):
        compose(CONTEXT, role, DEFAULTS[role], coordinated=True)


def test_length_bank_conversion_and_midi_offset_do_not_change_original_material():
    material = compose(CONTEXT, 'melody', DEFAULTS['melody'])
    material = replace(material, lengths_ms=(100., 500.)*8)
    params = bank_parameters(material)
    assert params['Note_01'] == material.notes[0]-24
    assert params['Length_Min_ms'] == 100 and params['Length_Max_ms'] == 500
    assert params['Length_01'] == 0 and params['Length_02'] == 127
    assert params['Velocity_01'] == material.velocities[0]
    with pytest.raises(ValueError, match='MIDI'):
        bank_parameters(replace(material, notes=(10,)*16))


@pytest.mark.parametrize('field,value', [('activity', float('nan')), ('length_ms', 0), ('velocity', 128), ('octave', 1.5)])
def test_invalid_controls_are_rejected(field, value):
    with pytest.raises(ValueError):
        compose(CONTEXT, 'melody', {**DEFAULTS['melody'], field:value})


@pytest.mark.parametrize('movement', (0., .3, .5, .7, 1.))
def test_snake_paths_preserve_the_composed_note_gate_velocity_and_length_order(movement):
    from desnivel.adapters.snake_sequence import SHAPES, SPEEDS, Lane, SnakeState, predict
    material=compose(CONTEXT,'melody',{**DEFAULTS['melody'],'movement':movement})
    params=bank_parameters(material)
    shape=params['Notes_Sequencer_Snake_Shape']+1
    path=SHAPES[shape-1]
    assert tuple(params[f'Note_{cell+1:02}']+24 for cell in path)==material.notes
    assert tuple(params[f'Gate_{cell+1:02}'] for cell in path)==material.gates
    assert tuple(params[f'Velocity_{cell+1:02}'] for cell in path)==material.velocities
    low,high=params['Length_Min_ms'],params['Length_Max_ms']
    lengths=tuple(low+params[f'Length_{i:02}']/127*(high-low) for i in range(1,17))
    assert tuple(lengths[cell] for cell in path)==pytest.approx(material.lengths_ms,abs=(high-low)/127)
    speed=list(SPEEDS)[params['Notes_Sequencer_Speed']]
    lane=Lane(shape,speed,16,'forwards',0.)
    state=SnakeState(tuple(params[f'Note_{i:02}']+24 for i in range(1,17)),
        tuple(params[f'Gate_{i:02}'] for i in range(1,17)),
        tuple(params[f'Velocity_{i:02}'] for i in range(1,17)), lengths,lane,lane,lane,120.,0)
    phrase=predict(state,16*material.step_beats)
    assert [n.pitch for n in phrase.notes]==[n for n,g in zip(material.notes,material.gates) if g]
    assert [n.velocity for n in phrase.notes]==[v for v,g in zip(material.velocities,material.gates) if g]


@pytest.mark.parametrize('role', ('melody','bass_line'))
def test_coordinated_articulation_uses_source_dynamics_and_lengths(role):
    source=Phrase(4,(Note(0,67,.25,40),Note(1,67,2.,110)))
    uniform=Phrase(4,(Note(0,67,1.,75),Note(1,67,1.,75)))
    a=compose(CONTEXT,role,DEFAULTS[role],source=source,coordinated=True)
    b=compose(CONTEXT,role,DEFAULTS[role],source=uniform,coordinated=True)
    assert a.notes==b.notes and a.gates==b.gates
    assert a.velocities!=b.velocities and a.lengths_ms!=b.lengths_ms


@pytest.mark.parametrize('steps', [3,10,16,31])
@pytest.mark.parametrize('movement', [0.,.5,1.])
def test_opening_gates_preserves_existing_attack_positions_and_closing_reverses_it(steps, movement):
    positions = []
    for count in range(steps+1):
        material = compose(CONTEXT,'melody',{**DEFAULTS['melody'],'activity':count/steps,'movement':movement},steps=steps)
        active = {i for i,gate in enumerate(material.gates) if gate}
        assert len(active) == count
        if positions:
            assert positions[-1] < active
        positions.append(active)
    for before, after in zip(reversed(positions), reversed(positions[:-1])):
        assert after < before


@pytest.mark.parametrize('role', ROLES)
@pytest.mark.parametrize('coordinated', [False,True])
def test_silent_cells_do_not_skip_notes_dynamics_or_articulation(role, coordinated):
    # Un banco interamente aperto rende udibile l'ordine musicale completo.
    # Diradandolo, gli attacchi devono conservarne la progressione iniziale.
    reference = compose(CONTEXT,role,{**DEFAULTS[role],'activity':1.},source=SOURCE,coordinated=coordinated)
    expected = [(n,v,d) for n,g,v,d in zip(reference.notes,reference.gates,reference.velocities,reference.lengths_ms) if g]
    for activity in (.125,.25,.5,.75):
        material = compose(CONTEXT,role,{**DEFAULTS[role],'activity':activity},source=SOURCE,coordinated=coordinated)
        actual = [(n,v,d) for n,g,v,d in zip(material.notes,material.gates,material.velocities,material.lengths_ms) if g]
        assert actual == expected[:len(actual)]


def _render_snake(material, phase):
    from desnivel.adapters.snake_sequence import SPEEDS, Lane, SnakeState, predict
    params = bank_parameters(material)
    lane = Lane(params['Notes_Sequencer_Snake_Shape']+1,
                tuple(SPEEDS)[params['Notes_Sequencer_Speed']],16,'forwards',phase)
    low,high = params['Length_Min_ms'],params['Length_Max_ms']
    state = SnakeState(tuple(params[f'Note_{i:02}']+24 for i in range(1,17)),
        tuple(params[f'Gate_{i:02}'] for i in range(1,17)),
        tuple(params[f'Velocity_{i:02}'] for i in range(1,17)),
        tuple(low+params[f'Length_{i:02}']/127*(high-low) for i in range(1,17)),
        lane,lane,lane,120.,0)
    return predict(state,8.)


@pytest.mark.parametrize('role', ROLES)
@pytest.mark.parametrize('movement', [0.,.5,1.])
@pytest.mark.parametrize('phase', [0.,.5,2.25])
@pytest.mark.parametrize('coordinated', [False,True])
def test_equivalent_grids_preserve_audible_motif_accents_and_attack_times_after_snake_translation(role, movement, phase, coordinated):
    # Con il motivo di quattro note e la sorgente di due, il ciclo più corto
    # può ancora rappresentare tutto il materiale: 8 gate/8n e 4 gate/16n.
    # Il basso coordinato dirada ulteriormente: qui si confronta il materiale
    # risultante dalla composizione, compensando la riduzione comune.
    source = SOURCE if coordinated else None
    activity = (.5,.25)
    if coordinated and role == 'bass_line':
        reduction = 1-.5*2/16
        activity = tuple(value/reduction for value in activity)
    slow,fast = (compose(CONTEXT,role,{**DEFAULTS[role],'pulse':pulse,'activity':amount,'movement':movement},
                         source=source,coordinated=coordinated)
                 for pulse,amount in zip(('8n','16n'),activity))
    a,b = _render_snake(slow,phase),_render_snake(fast,phase)
    assert [(n.beat,n.pitch,n.velocity) for n in a.notes] == [(n.beat,n.pitch,n.velocity) for n in b.notes]
    assert [n.duration for n in a.notes] == pytest.approx([n.duration for n in b.notes],abs=.003)
