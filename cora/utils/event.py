import inspect
from abc import abstractmethod
from pathlib import Path
from typing import Protocol, Dict, List, Optional

_EVENTS_CLASS_TEMPLATE = """\
from enum import Enum, unique

from cora.utils.event import EventEmitter


@unique
class {emitter_class}Events(Enum):
{events_code}


class {emitter_class}Callbacks:
{callbacks_code}

    def register_to(self, x: EventEmitter):
        for k, v in {emitter_class}Events.__members__.items():
            x.on(v.value, getattr(self, f"on_{{v.value}}"))

"""


def gen_event_and_callback_classes(emitter: str, events: List[str], *, to_file: Path):
    code_events = []
    for ev in events:
        code_events.append(f'EVENT_{ev.upper()} = "{ev}"')

    code_callbacks = []
    for ev in events:
        code_callbacks.append(f"def on_{ev.lower()}(self, **kwargs):\n        pass")

    with to_file.open("w") as fou:
        fou.write(
            _EVENTS_CLASS_TEMPLATE.format(
                emitter_class=emitter,
                events_code="\n".join(f"    {s}" for s in code_events),
                callbacks_code="\n\n".join(f"    {s}" for s in code_callbacks),
            )
        )


def _inspect_args_in_dict(fn, *, is_method: bool, args: tuple, kwargs: dict):
    fn_args = {**kwargs}
    if not args:
        return fn_args
    # Let's obtain the names of all positional parameters
    sig = inspect.signature(fn)
    positional_params = [
        p.name
        for p in sig.parameters.values()
        if p.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ][1 if is_method else 0 :]
    # Trunk according to the given arguments
    params = positional_params[: len(args)]
    # Insert positional arguments into the dict
    fn_args.update({p: a for p, a in zip(params, args)})
    return fn_args


def hook_method_to_emit_events(
    before_event: Optional[str] = None, after_event: Optional[str] = None
):
    def wrap_method(method):
        def _wrapper(self, *args, **kwargs):
            if before_event or after_event:
                fn_args = _inspect_args_in_dict(
                    method, is_method=True, args=args, kwargs=kwargs
                )
            else:
                fn_args = {}
            if before_event:
                self.emit(before_event, **fn_args)
            res = method(self, *args, **kwargs)
            if after_event:
                self.emit(after_event, **fn_args, result=res)
            return res

        return _wrapper

    return wrap_method


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
