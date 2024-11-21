from abc import abstractmethod
from functools import cached_property
from typing import Type, Dict, List

from swell.splits.ftypes import parse_ftype


class FilePreview:
    _PREVIEW_SPLITTER = " | "
    _PREVIEW_DICT: Dict[str, Type["FilePreview"]] = {}

    def __init__(self, file_type: str, file_name: str, file_content: str):
        self.file_type = file_type
        self.file_name = file_name
        self.file_content = file_content

    @cached_property
    def file_lines(self):
        return self.file_content.splitlines()

    @classmethod
    def register(cls, file_types: List[str]):
        def register_inner(preview_cls: Type["FilePreview"]):
            for ft in file_types:
                assert (
                    ft not in cls._PREVIEW_DICT
                ), f"Conflicted previewers: {preview_cls} and {cls._PREVIEW_DICT[ft]} are both requesting for {ft}."
                cls._PREVIEW_DICT[ft] = preview_cls
            return preview_cls

        return register_inner

    @classmethod
    def of(cls, file_name: str, file_content: str) -> str:
        file_type = parse_ftype(file_name)
        return cls._PREVIEW_DICT.get(file_type, _FileContent)(
            file_type, file_name, file_content
        ).get_preview()

    @abstractmethod
    def get_preview(self) -> str: ...

    @classmethod
    def preview_line(cls, line_number, line_content):
        return str(line_number) + cls._PREVIEW_SPLITTER + line_content

    @classmethod
    def parse_preview_line(cls, preview_line):
        index = preview_line.find(cls._PREVIEW_SPLITTER)
        if index != -1:
            try:
                line_number = int(preview_line[:index])
                line_content = preview_line[index + len(cls._PREVIEW_SPLITTER) :]
            except ValueError:
                line_number = None
                line_content = preview_line
        else:
            line_number = None
            line_content = preview_line
        return line_number, line_content

    @classmethod
    def spacing_for_line_number(cls, line_number):
        return " " * (len(str(line_number)) + len(cls._PREVIEW_SPLITTER))

    @staticmethod
    def indentation_of_line(line):
        return " " * (len(line) - len(line.lstrip()))


class _FileContent(FilePreview):
    def get_preview(self, min_line: int = 5, max_line: int = -1) -> str:
        return "\n".join(
            [self.preview_line(i, line) for i, line in enumerate(self.file_lines)]
        )
