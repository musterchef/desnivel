import pytest
from desnivel.music.sources import MusicalSource
from desnivel.music.phrases import Note, Phrase
from desnivel.music.coordinator import MusicCoordinator, Voice
from desnivel.music.interactions import VoicePlan
from desnivel.music.director import MusicalContext, MusicDirector
from desnivel.music.arrangement import Assignment
from desnivel.music.automation import AdaptiveContext, ParameterTarget


def test_sources_are_visible_to_generators_and_adaptation_by_role_without_polluting_history():
    requests=[]
    def adapt(request):
        requests.append(request)
        return {'density':ParameterTarget(sum(p.attacks_per_beat for p in request.peers('melody')),'melodic peers')}
    staged=[]
    def stage(request):
        staged.append(request)
        return VoicePlan(Phrase(4,()))
    coordinator=MusicCoordinator({'line':Voice(lambda r:None,supported_roles=('bass_line',),
        stage=stage,accept=lambda p:None,adapt=adapt)})
    phrase=Phrase(4,(Note(0,60,2.,90),Note(2,67,2.,80)))
    external={'external_a':MusicalSource('melody',phrase,carry_in=1),
              'external_b':MusicalSource('sustained_texture',None,unavailable_reason='stale')}
    coordinator.plan(0,4,MusicalContext(0,'level',60,'minor'),
        assignments={'line':Assignment('bass_line',{'density':1.})},adaptive_context=AdaptiveContext(),external_sources=external)
    assert requests[0].peers('melody')[0].attacks==1
    assert requests[0].peers('sustained_texture')==()
    assert staged[0].external_sources['external_a'].phrase==phrase
    assert 'external_a' not in coordinator.last_plan['observation']['voices']
    assert coordinator.last_plan['external_sources']['external_a']['carry_in']==1
    assert coordinator.last_plan['external_sources']['external_b']['notes'] is None
    assert coordinator.last_plan['automation']['line']['density']['target']==.25
    director=MusicDirector([dict(from_progress=0,name='level',root=60,scale='minor')])
    assert director.decision_at(0,external_sources=external)['external_sources']['external_a']['role']=='melody'


def test_external_names_and_intervals_cannot_shadow_generated_voices():
    coordinator=MusicCoordinator({'a':Voice(lambda r:Phrase(4,()))})
    with pytest.raises(ValueError,match='occupati'):
        coordinator.plan(0,4,external_sources={'a':MusicalSource('melody',Phrase(4,()))})
    with pytest.raises(ValueError,match='finestra'):
        coordinator.plan(0,4,external_sources={'b':MusicalSource('melody',Phrase(8,()))})
