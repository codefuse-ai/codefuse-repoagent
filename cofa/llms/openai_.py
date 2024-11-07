from cofa.llms.base import LLMBase


def call_openai(model_name, messages, *, temperature, top_p, max_tokens):
    raise NotImplementedError("OpenAI")


class OpenAI(LLMBase):
    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model

    def do_query(self) -> str:
        return call_openai(
            self.model,
            [m.to_json() for m in self.history],
            temperature=self.temperature,
            top_p=self.top_p,
            max_tokens=self.max_tokens,
        )
