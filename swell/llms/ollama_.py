import ollama

from swell.llms.base import LLMBase


def call_ollama(model_name, messages, *, temperature, top_p, max_tokens):
    resp = ollama.chat(
        model_name,
        messages=messages,
        options={"temperature": temperature, "top_p": top_p, "max_tokens": max_tokens},
    )
    return resp["message"]["content"]


class Ollama(LLMBase):
    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model

    def do_query(self) -> str:
        return call_ollama(
            self.model,
            [m.to_json() for m in self.history],
            temperature=self.temperature,
            top_p=self.top_p,
            max_tokens=self.max_tokens,
        )


if __name__ == "__main__":
    model_ = Ollama("qwen2:0.5b-instruct", temperature=0.8, debug_mode=True)
    model_.append_user_message("Hi, I'm Tony! What's your name?")
    model_.query()
