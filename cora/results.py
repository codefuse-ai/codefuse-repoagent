from pathlib import Path

import pyjson5 as json5

from cora.retrv.events import RetrieverCallbacks


class CfarResult(RetrieverCallbacks):
    def __init__(self, res_file: Path):
        self.res_file = res_file
        self.result = {}

    def on_qrw_finish(self, **kwargs):
        self.add_interm_res("qrw", kwargs)

    def on_edl_finish(self, **kwargs):
        self.add_interm_res("edl", kwargs)

    def on_kws_finish(self, **kwargs):
        self.add_interm_res("kws", kwargs)

    def on_fte_finish(self, **kwargs):
        self.add_interm_res("fte", kwargs)

    def on_fps_finish(self, **kwargs):
        self.add_interm_res("fps", kwargs)

    def on_scr_finish(self, **kwargs):
        self.add_interm_res("scr", kwargs)

    def on_finish(self, **kwargs):
        self.add_interm_res("all", kwargs)

    def add_interm_res(self, phase: str, phase_res: dict):
        with self.res_file.open("w") as fou:
            try:
                # We use JSON5 as some like sets are not serializable
                result = {**self.result, phase: phase_res}
                fou.write(json5.dumps(result))
            except json5.Json5Exception | TypeError:
                # Let's fall back to string for failed cases
                result = {**self.result, phase: str(phase_res)}
                fou.write(json5.dumps(result))
            finally:
                self.result = result
