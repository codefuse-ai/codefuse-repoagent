from typing import TypeVar, Generic, cast

ThisClass = TypeVar("ThisClass")


class CastSelfToThis(Generic[ThisClass]):
    @property
    def this(self) -> ThisClass:
        return cast(ThisClass, self)
