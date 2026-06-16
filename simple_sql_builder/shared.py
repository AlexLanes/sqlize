# std
from typing import (
    Any, Self,
    Literal, Protocol,
    Sequence, Iterable, Mapping
)

type SequenceAny = Sequence[Any]
type MappingAny = Mapping[str, Any]
type ManyMappingAny = Iterable[MappingAny]
type ManySequenceAny = Iterable[SequenceAny]

def quote (s: str) -> str:
    """Quote `s` if contains space"""
    return f'"{s}"' if " " in s else s

class OrderableExpression (Protocol):
    """Interface for a `Column` or `Expression` to be `ORDER BY`"""

    order: Literal["ASC", "DESC"]
    nulls: Literal["FIRST", "LAST"] | None

    @property
    def NullsFirst (self) -> Self:
        """Apply `NULLS FIRST`"""
        ...

    @property
    def NullsLast (self) -> Self:
        """Apply `NULLS LAST`"""
        ...

    def to_sql (self) -> str:
        ...

class AliasedColumn (Protocol):
    """Inteface for a `Column` or `Expression` with alias `AS`"""

    alias: str
    """Quoted `alias`"""

    def to_sql (self) -> str:
        """`SQL: {Column|Expression} AS {alias}`"""
        ...

__all__ = [
    "quote",
    "AliasedColumn",
    "OrderableExpression",

    "MappingAny",
    "SequenceAny",
    "ManyMappingAny",
    "ManySequenceAny",
]