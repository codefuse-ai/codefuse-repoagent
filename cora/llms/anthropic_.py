import anthropic

from cora.llms.base import LLMBase

_client = anthropic.Anthropic()


def call_anthropic(model_name, messages, *, temperature, top_p, max_tokens, system):
    resp = _client.messages.create(
        model=model_name,
        messages=messages,
        system=system,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
    )
    return resp.content[0].text


class Anthropic(LLMBase):
    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model

    def do_query(self) -> str:
        messages = [m.to_json() for m in self.history]
        if messages[0]["role"] == "system":
            system_prompt = messages[0]["content"]
            messages = messages[1:]
        else:
            system_prompt = anthropic.NOT_GIVEN
        return call_anthropic(
            self.model,
            messages=messages,
            temperature=self.temperature,
            top_p=self.top_p,
            max_tokens=self.max_tokens,
            system=system_prompt,
        )
