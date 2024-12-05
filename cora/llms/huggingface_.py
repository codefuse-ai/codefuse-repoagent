from cora.llms.base import LLMBase

# TODO: make thread-safe
_CACHED_MODELS = {}


def call_huggingface(model_id, messages, *, temperature, top_p, max_tokens):
    # TODO: directly use pipeline
    raise NotImplementedError("HuggingFace")


class HuggingFace(LLMBase):
    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model

    def do_query(self) -> str:
        return call_huggingface(
            self.model,
            [m.to_json() for m in self.history],
            temperature=self.temperature,
            top_p=self.top_p,
            max_tokens=self.max_tokens,
        )
