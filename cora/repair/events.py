from enum import Enum, unique

from cora.utils.event import EventEmitter


@unique
class IssueRepaEvents(Enum):
    EVENT_START = "start"
    EVENT_FINISH = "finish"
    EVENT_GEN_PATCH_START = "gen_patch_start"
    EVENT_GEN_PATCH_FINISH = "gen_patch_finish"
    EVENT_EVAL_PATCH_START = "eval_patch_start"
    EVENT_EVAL_PATCH_FINISH = "eval_patch_finish"
    EVENT_NEXT_ROUND = "next_round"


class IssueRepaCallbacks:
    def on_start(self, **kwargs):
        pass

    def on_finish(self, **kwargs):
        pass

    def on_gen_patch_start(self, **kwargs):
        pass

    def on_gen_patch_finish(self, **kwargs):
        pass

    def on_eval_patch_start(self, **kwargs):
        pass

    def on_eval_patch_finish(self, **kwargs):
        pass

    def on_next_round(self, **kwargs):
        pass

    def register_to(self, x: EventEmitter):
        for k, v in IssueRepaEvents.__members__.items():
            x.on(v.value, getattr(self, f"on_{v.value}"))
