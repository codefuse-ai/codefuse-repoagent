from pathlib import Path

FilePath = Path


class SnippetPath:
    def __init__(self, file: FilePath, start: int, end: int):
        self._file_path = file
        self._start_line = start
        self._end_line = end

    @staticmethod
    def from_str(snp_path) -> "SnippetPath":
        f, t = snp_path.split(":")
        s, e = t.split("-")
        return SnippetPath(FilePath(f), int(s), int(e))

    @property
    def file_path(self) -> FilePath:
        return self._file_path

    @property
    def start_line(self) -> int:
        return self._start_line

    @property
    def end_line(self) -> int:
        return self._end_line

    def size(self):
        return self._end_line - self._start_line

    def as_tuple(self):
        return str(self.file_path), self._start_line, self._end_line

    def __eq__(self, other):
        if not isinstance(other, SnippetPath):
            return False
        return str(self) == str(other)

    def __str__(self):
        return f"{self.file_path}:{self.start_line}-{self.end_line}"
