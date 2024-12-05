import openai

from cora.llms.base import LLMBase

_client = openai.OpenAI()


def call_openai(model_name, messages, *, temperature, top_p, max_tokens):
    resp = _client.chat.completions.create(
        model=model_name,
        messages=messages,
        temperature=temperature,
        top_p=top_p,
        max_completion_tokens=max_tokens,
    )
    return resp.choices[0].message.content


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
