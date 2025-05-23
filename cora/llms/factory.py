from dataclasses import dataclass, field
from typing import Literal

from cora.llms.anthropic_ import Anthropic
from cora.llms.base import LLMBase
from cora.llms.easydeploy_ import EasyDeploy
from cora.llms.huggingface_ import HuggingFace
from cora.llms.ollama_ import Ollama
from cora.llms.openai_ import OpenAI


@dataclass
class LLMConfig:
    provider: Literal["openai", "ollama", "huggingface"]
    llm_name: str
    debug_mode: bool = field(default=False)
    temperature: float = field(default=0)
    top_k: int = field(default=50)
    top_p: float = field(default=0.95)
    max_tokens: int = field(default=1024)

    @property
    def max_completion_tokens(self) -> int:
        return self.max_tokens


class LLMFactory:
    @classmethod
    def create(cls, config: LLMConfig) -> LLMBase:
        return {
            "ollama": Ollama,
            "openai": OpenAI,
            "anthropic": Anthropic,
            "huggingface": HuggingFace,
            "easydeploy": EasyDeploy,
        }[config.provider](
            config.llm_name,
            debug_mode=config.debug_mode,
            temperature=config.temperature,
            top_k=config.top_k,
            top_p=config.top_p,
            max_tokens=config.max_tokens,
        )


if __name__ == "__main__":
    llm = LLMFactory.create(
        LLMConfig(provider="ollama", llm_name="qwen2:0.5b-instruct", debug_mode=True)
    )
    llm.append_user_message("Hi, I'm Simon!")
    llm.query()
