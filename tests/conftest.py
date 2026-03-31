import pytest

from src.event_bus import EventBus


@pytest.fixture
def event_bus():
    return EventBus()
