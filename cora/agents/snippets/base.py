from abc import ABC, abstractmethod
from typing import Tuple, Generator

from cora.repo.repo import Repository


class SnipRelDetmBase(ABC):
    @abstractmethod
    def is_debugging(self) -> bool: ...

    @abstractmethod
    def disable_debugging(self): ...

    @abstractmethod
    def enable_debugging(self): ...

    @abstractmethod
    def determine(
        self, query: str, snippet_path: str, snippet_content: str, *args, **kwargs
    ) -> Tuple[bool, str]: ...


class SnipFinderBase(ABC):
    def __init__(self, repo: Repository, determ: SnipRelDetmBase):
        self.repo = repo
        self.determ = determ

    def disable_debugging(self):
        self.determ.disable_debugging()

    def enable_debugging(self):
        self.determ.enable_debugging()

    @abstractmethod
    def find(
        self, query: str, file_path: str, *args, **kwargs
    ) -> Generator[Tuple[str, str], None, None]: ...
