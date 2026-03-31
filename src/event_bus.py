import logging
from collections import defaultdict
from typing import Any, Callable

logger = logging.getLogger(__name__)

Handler = Callable[[Any], None]


class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: Handler) -> None:
        self._subscribers[event_name].append(handler)

    def unsubscribe(self, event_name: str, handler: Handler) -> None:
        self._subscribers[event_name].remove(handler)

    def publish(self, event_name: str, data: Any = None) -> None:
        for handler in self._subscribers.get(event_name, []):
            try:
                handler(data)
            except Exception:
                logger.exception(f"Error in handler for event '{event_name}'")
