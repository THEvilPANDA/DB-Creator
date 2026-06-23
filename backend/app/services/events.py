from dataclasses import dataclass, field
from typing import Any


@dataclass
class DomainEvent:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)


class EventPublisher:
    def __init__(self):
        self.events: list[DomainEvent] = []
        self._handlers: dict[str, list] = {}

    def subscribe(self, event_name: str, handler) -> None:
        self._handlers.setdefault(event_name, []).append(handler)

    def publish(self, event: DomainEvent) -> None:
        self.events.append(event)
        for handler in self._handlers.get(event.name, []):
            handler(event)


publisher = EventPublisher()
