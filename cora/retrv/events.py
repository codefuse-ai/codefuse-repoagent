from enum import Enum, unique

from cora.utils.event import EventEmitter


@unique
class RetrieverEvents(Enum):
    EVENT_START = "start"
    EVENT_FINISH = "finish"
    EVENT_QRW_START = "qrw_start"
    EVENT_QRW_FINISH = "qrw_finish"
    EVENT_EDL_START = "edl_start"
    EVENT_EDL_FINISH = "edl_finish"
    EVENT_KWS_START = "kws_start"
    EVENT_KWS_FINISH = "kws_finish"
    EVENT_FTE_START = "fte_start"
    EVENT_FTE_FINISH = "fte_finish"
    EVENT_FPS_START = "fps_start"
    EVENT_FPS_FINISH = "fps_finish"
    EVENT_SCR_START = "scr_start"
    EVENT_SCR_FINISH = "scr_finish"


class RetrieverCallbacks:
    def on_start(self, **kwargs):
        pass

    def on_finish(self, **kwargs):
        pass

    def on_qrw_start(self, **kwargs):
        pass

    def on_qrw_finish(self, **kwargs):
        pass

    def on_edl_start(self, **kwargs):
        pass

    def on_edl_finish(self, **kwargs):
        pass

    def on_kws_start(self, **kwargs):
        pass

    def on_kws_finish(self, **kwargs):
        pass

    def on_fte_start(self, **kwargs):
        pass

    def on_fte_finish(self, **kwargs):
        pass

    def on_fps_start(self, **kwargs):
        pass

    def on_fps_finish(self, **kwargs):
        pass

    def on_scr_start(self, **kwargs):
        pass

    def on_scr_finish(self, **kwargs):
        pass

    def register_to(self, x: EventEmitter):
        for k, v in RetrieverEvents.__members__.items():
            x.on(v.value, getattr(self, f"on_{v.value}"))
