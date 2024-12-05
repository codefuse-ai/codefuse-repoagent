from abc import abstractmethod
from typing import Protocol, Dict, List


class EventReceiver(Protocol):
    @abstractmethod
    def __call__(self, **kwargs):
        pass


class EventEmitter:
    def __init__(self):
        self.event_receivers: Dict[str, List[EventReceiver]] = {}

    def on(self, event: str, receiver: EventReceiver):
        if event not in self.event_receivers:
            self.event_receivers[event] = []
        self.event_receivers[event].append(receiver)

    def emit(self, event, **kwargs):
        for recv in self.event_receivers.get(event, []):
            recv(**kwargs)
