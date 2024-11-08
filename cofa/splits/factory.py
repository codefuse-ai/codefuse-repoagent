from typing import Dict, Type, List

from cofa.base.paths import FilePath
from cofa.splits.code_ import ASTSpl
from cofa.splits.ftypes import parse_ftype
from cofa.splits.splitter import Splitter
from cofa.splits.text_ import LineSpl


class SplFactory:
    _additional_splitters: Dict[str, Type[Splitter]] = {}

    @classmethod
    def register(cls, file_types: List[str]):
        def register_inner(spl_cls: Type[Splitter]):
            for ft in file_types:
                assert (
                    ft not in cls._additional_splitters
                ), f"Cannot register {spl_cls} for {ft}; it was already registered by {cls._additional_splitters[ft]}"
                cls._additional_splitters[ft] = spl_cls
            return spl_cls

        return register_inner

    @classmethod
    def create(cls, file: FilePath) -> Splitter:
        file_type = parse_ftype(file.name)
        # We are a registered type
        if file_type in cls._additional_splitters:
            return cls._additional_splitters[file_type](file)
        try:
            # We might be a code file; we split by AST
            return ASTSpl(file)
        except Exception:
            # We fall back to a text splitter; we split by lines
            return LineSpl(file)

    @staticmethod
    def get_splitter():
        pass
