from pathlib import Path

import pyjson5 as json5

from cora.repair.events import IssueRepaCallbacks
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
        try:
            # We use JSON5 as some like sets are not serializable
            json5.dumps(phase_res)
            new_phase_res = phase_res
        except json5.Json5Exception | TypeError:
            # Let's fall back to string for failed cases
            new_phase_res = str(phase_res)
        self.result[phase] = new_phase_res
        with self.res_file.open("w") as fou:
            fou.write(json5.dumps(self.result))


class IssueRepaResult(IssueRepaCallbacks):
    def __init__(self, res_file: Path):
        self.res_file = res_file
        self.result = {"rounds": [], "num_rounds": None}
        self.curr_round = -1

    def on_finish(self, **kwargs):
        self.curr_round = -1
        self.add_interm_res("result", kwargs)

    def on_next_round(self, **kwargs):
        if not self.result["num_rounds"]:
            self.result["num_rounds"] = kwargs["num_rounds"]
        self.curr_round += 1
        self.result["rounds"].append({})

    def on_gen_patch_finish(self, **kwargs):
        self.add_interm_res("gen_patch", kwargs)

    def on_eval_patch_finish(self, **kwargs):
        self.add_interm_res("eval_patch", kwargs)

    def add_interm_res(self, phase: str, phase_res: dict):
        try:
            # We use JSON5 as some like sets are not serializable
            json5.dumps(phase_res)
            new_phase_res = phase_res
        except json5.Json5Exception | TypeError:
            # Let's fall back to string for failed cases
            new_phase_res = str(phase_res)
        self.result["rounds"][self.curr_round][phase] = new_phase_res
        with self.res_file.open("w") as fou:
            fou.write(json5.dumps(self.result))
