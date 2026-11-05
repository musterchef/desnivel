import pytest

from desnivel.adapters.live_devices import LiveDevices


def announcement(instance='a', device_id='endpoint_a', port=10001, track_id=11, index=0):
    return dict(version=1, action='discover', instance=instance, device_id=device_id,
                reply_port=port, device_kind='voice', playing=0,
                track=dict(id=track_id, index=index, name='synth'))


def test_inventory_tracks_renames_and_reordering_without_changing_binding_identity():
    now, sent = [0.], []
    inventory = LiveDevices(lambda *args: sent.append(args), clock=lambda: now[0])
    message = announcement()
    inventory.observe(message)
    message['track'].update(name='renamed', index=4)
    inventory.observe(message)
    inventory.bind('endpoint_a', 'melody', 9006)
    assert inventory.available()[0]['track']['name'] == 'renamed'
    assert inventory.available()[0]['track']['index'] == 4
    assert sent[-1][0] == 10001
    assert sent[-1][2]['voice'] == 'melody'
    assert sent[-1][2]['device_id'] == 'endpoint_a'
    now[0] = 3
    assert not inventory.available()
    with pytest.raises(ValueError, match='assente'):
        inventory.bind('endpoint_a', 'melody', 9006)


@pytest.mark.parametrize('changes,reason', [
    ({'device_id': 'endpoint_a'}, 'identità duplicata'),
    ({'port': 10001}, 'porta Receive duplicata'),
    ({'track_id': 11}, 'stessa traccia'),
])
def test_ambiguous_devices_cannot_be_bound(changes, reason):
    inventory = LiveDevices(lambda *args: pytest.fail('nessun invio a destinazioni ambigue'))
    inventory.observe(announcement())
    args = dict(instance='b', device_id='endpoint_b', port=10002, track_id=12)
    args.update(changes)
    inventory.observe(announcement(**args))
    assert reason in inventory.available()[0]['error']
    with pytest.raises(ValueError, match='ambiguo'):
        inventory.bind('endpoint_a', 'melody', 9006)


def test_existing_controls_remain_visible_until_they_send_the_inventory():
    now = [0.]
    inventory = LiveDevices(lambda *a: None, clock=lambda: now[0])
    control = dict(version=1, action='hello', instance='a', voice='voice_01', reply_port=9101, serial=1)
    inventory.observe_control(control)
    assert inventory.unannounced()[0]['voice'] == 'voice_01'
    inventory.observe(announcement())
    assert not inventory.unannounced()
    now[0] = 4
    assert not inventory.available() and not inventory.unannounced()
