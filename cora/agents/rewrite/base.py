from abc import abstractmethod, ABC

from cora.repo.repo import Repository


class RewriterBase(ABC):
    def __init__(self, repo: Repository):
        self.repo = repo

    @abstractmethod
    def rewrite(self, query: str) -> str: ...
