from typing import List

from cofa.base.paths import SnippetPath, FilePath
from cofa.splits.splitter import Splitter


class LineSpl(Splitter):
    """A line-based text splitter without overlapping"""

    def __init__(self, file: FilePath, snippet_size: int = 15):
        super().__init__(file)
        self._snippet_size = snippet_size

    def _do_split(self) -> List[SnippetPath]:
        t = len(self.content.splitlines())
        s = self._snippet_size
        return [SnippetPath(self.file, i, min(i + s, t)) for i in range(0, t, s)]
