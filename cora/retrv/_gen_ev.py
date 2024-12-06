from pathlib import Path

from cora.utils.event import gen_event_and_callback_classes

if __name__ == "__main__":
    gen_event_and_callback_classes(
        emitter="Retriever",
        events=[
            "start",
            "finish",
            "qrw_start",
            "qrw_finish",
            "edl_start",
            "edl_finish",
            "kws_start",
            "kws_finish",
            "fte_start",
            "fte_finish",
            "fps_start",
            "fps_finish",
            "scr_start",
            "scr_finish",
        ],
        to_file=Path(__file__).parent / "events.py",
    )
