from pathlib import Path

FilePath = Path


class SnippetPath:
    def __init__(self, path: str):
        self.path = path

        a, b = path.split(":")
        c, d = b.split("-")

        self._file_path = FilePath(a)
        self._start_line = int(c)
        self._end_line = int(d)

    @property
    def file_path(self):
        return self._file_path

    @property
    def start_line(self):
        return self._start_line

    @property
    def end_line(self):
        return self._end_line

    def size(self):
        return self._end_line - self._start_line

    def as_tuple(self):
        return str(self.file_path), self._start_line, self._end_line

    def __str__(self):
        return self.path
