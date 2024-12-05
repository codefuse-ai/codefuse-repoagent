from abc import abstractmethod, ABC
from typing import List, Optional


class RetrieverBase(ABC):
    def __init__(self):
        self.agent: Optional["RAGBase"] = None

    def inject_agent(self, agent: "RAGBase"):
        self.agent = agent

    @abstractmethod
    def retrieve(self, query: str, **kwargs) -> List[str]: ...


class GeneratorBase(ABC):
    def __init__(self):
        self.agent: Optional["RAGBase"] = None

    def inject_agent(self, agent: "RAGBase"):
        self.agent = agent

    @abstractmethod
    def generate(self, query: str, context: List[str], **kwargs) -> any: ...


class RAGBase:
    def __init__(
        self,
        name: str,
        *,
        retriever: RetrieverBase,
        generator: GeneratorBase,
    ):
        self.name = name
        self.retriever = retriever
        self.generator = generator
        self.retriever.inject_agent(self)
        self.generator.inject_agent(self)

    def run(
        self,
        query: str,
        retrieving_args: Optional[dict] = None,
        generation_args: Optional[dict] = None,
    ) -> any:
        return self.generate(
            query,
            self.retrieve(query, **(retrieving_args or {})),
            **(generation_args or {}),
        )

    def before_retrieving(self, query: str, **kwargs):
        pass

    def retrieve(self, query: str, **kwargs) -> List[str]:
        self.before_retrieving(query, **kwargs)
        context = self.retriever.retrieve(query, **kwargs)
        self.after_retrieving(query, context, **kwargs)
        return context

    def after_retrieving(self, query: str, context: List[str], **kwargs):
        pass

    def before_generate(self, query: str, context: List[str], **kwargs):
        pass

    def generate(self, query: str, context: List[str], **kwargs) -> any:
        self.before_generate(query, context, **kwargs)
        response = self.generator.generate(query, context, **kwargs)
        self.after_generate(query, context, response, **kwargs)
        return response

    def after_generate(self, query: str, context: List[str], response: any, **kwargs):
        pass
