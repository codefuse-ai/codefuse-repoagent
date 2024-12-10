from cora.llms.base import LLMBase


def call_easydeploy(model, messages, *, temperature, top_p, max_tokens) -> str:
    raise NotImplementedError("EasyDeploy")


class EasyDeploy(LLMBase):
    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model

    def do_query(self) -> str:
        return call_easydeploy(
            self.model,
            [m.to_json() for m in self.history],
            temperature=self.temperature,
            top_p=self.top_p,
            max_tokens=self.max_tokens,
        )
