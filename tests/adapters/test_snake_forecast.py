from copy import deepcopy

import pytest

from desnivel.adapters.snake_forecast import SnakeForecast


def packet(serial=1, **changes):
    lane=dict(shape=1,speed='8n',steps=16,direction='forwards',phase_beats=0.)
    value=dict(version=1,observation_version=1,source='device_a',serial=serial,epoch=0,beat=4.,playing=1,
        active_notes=[dict(pitch=72,velocity=70,remaining_ms=3000.)],
        state=dict(notes=list(range(60,76)),gates=[1]*16,velocities=[90]*16,lengths_ms=[250.]*16,
                   notes_lane=dict(lane),gates_lane=dict(lane),velocities_lane=dict(lane),bpm=120.,midi_offset=0,swing=0))
    return {**value,**changes}


def test_projection_uses_observed_phase_and_preserves_held_notes_without_new_attacks():
    forecast=SnakeForecast(clock=lambda:0.)
    data=packet();original=deepcopy(data);forecast.update(data)
    source=forecast.project('melody',6.,4.,beat=4.,bpm=120.)
    assert source.phrase is not None
    assert source.carry_in==1
    assert (source.phrase.notes[0].pitch,source.phrase.notes[0].duration)==(72,4.)
    assert [n.pitch for n in source.phrase.notes[1:]]==list(range(64,72))
    observation=source.observation()
    assert observation.attacks==8 and observation.occupied_ratio==1.
    assert observation.register==(64,72)
    assert data==original


def test_same_pitch_retrigger_ends_a_carried_note_at_the_observed_future_attack():
    forecast=SnakeForecast(clock=lambda:0.)
    data=packet();data['active_notes'][0]['pitch']=66
    forecast.update(data)
    source=forecast.project('bass_line',6.,4.,beat=4.,bpm=120.)
    assert source.phrase.notes[0].duration==1.
    assert source.observation().attacks==8


def test_duplicate_packets_do_not_refresh_age_and_invalidation_requires_new_telemetry():
    now=[0.];forecast=SnakeForecast(clock=lambda:now[0])
    forecast.update(packet());now[0]=1.;forecast.update(packet())
    assert 'scaduta' in forecast.project('melody',6,4,beat=4,bpm=120).unavailable_reason
    forecast.update(None);forecast.update(packet())
    assert forecast.packet is None
    forecast.update(packet(2))
    assert forecast.project('melody',6,4,beat=4,bpm=120).phrase is not None


@pytest.mark.parametrize('change', [dict(playing=0),dict(error='Shift deve essere 1'),
    dict(observation_version=0),dict(active_notes=[dict(pitch=200,velocity=80,remaining_ms=500)])])
def test_unsupported_state_is_unavailable_instead_of_a_silent_phrase(change):
    forecast=SnakeForecast(clock=lambda:0.)
    forecast.update(packet(**change))
    source=forecast.project('sustained_texture',6,4,beat=4,bpm=120)
    assert source.phrase is None and source.unavailable_reason


def test_bpm_and_transport_mismatch_are_explicit():
    forecast=SnakeForecast(clock=lambda:0.);forecast.update(packet())
    assert 'BPM' in forecast.project('melody',6,4,beat=4,bpm=90).unavailable_reason
    assert 'posizione' in forecast.project('melody',12,4,beat=10,bpm=120).unavailable_reason
