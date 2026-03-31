from src.event_bus import EventBus


def test_subscribe_and_publish():
    bus = EventBus()
    received = []
    bus.subscribe("TestEvent", lambda data: received.append(data))
    bus.publish("TestEvent", {"key": "value"})
    assert received == [{"key": "value"}]


def test_multiple_subscribers():
    bus = EventBus()
    results_a = []
    results_b = []
    bus.subscribe("TestEvent", lambda data: results_a.append(data))
    bus.subscribe("TestEvent", lambda data: results_b.append(data))
    bus.publish("TestEvent", {"x": 1})
    assert results_a == [{"x": 1}]
    assert results_b == [{"x": 1}]


def test_publish_no_subscribers():
    bus = EventBus()
    bus.publish("NoOneListening", {"x": 1})  # should not raise


def test_different_events_isolated():
    bus = EventBus()
    received_a = []
    received_b = []
    bus.subscribe("EventA", lambda data: received_a.append(data))
    bus.subscribe("EventB", lambda data: received_b.append(data))
    bus.publish("EventA", "hello")
    assert received_a == ["hello"]
    assert received_b == []


def test_unsubscribe():
    bus = EventBus()
    received = []
    handler = lambda data: received.append(data)
    bus.subscribe("TestEvent", handler)
    bus.unsubscribe("TestEvent", handler)
    bus.publish("TestEvent", "should not appear")
    assert received == []
