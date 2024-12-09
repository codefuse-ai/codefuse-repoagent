from pathlib import Path

from cora.utils.event import gen_event_and_callback_classes

if __name__ == "__main__":
    gen_event_and_callback_classes(
        emitter="IssueRepa",
        events=[
            "start",
            "finish",
            "gen_patch_start",
            "gen_patch_finish",
            "eval_patch_start",
            "eval_patch_finish",
            "next_round",
        ],
        to_file=Path(__file__).parent / "events.py",
    )
