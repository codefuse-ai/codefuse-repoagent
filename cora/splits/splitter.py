from abc import abstractmethod
from functools import cached_property
from typing import List

from cora.base.paths import FilePath, SnippetPath


class Splitter:
    def __init__(self, file: FilePath):
        self.file = file

    @cached_property
    def content(self):
        return self.file.read_text(encoding="utf-8", errors="replace")

    def split(self) -> List[SnippetPath]:
        return self._do_split()

    @abstractmethod
    def _do_split(self) -> List[SnippetPath]: ...
