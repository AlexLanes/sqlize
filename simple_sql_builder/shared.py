# std
from typing import Protocol

class AliasedColumn (Protocol):
    """Inteface for a `Column` or `Expression` with alias `AS`"""
    alias: str
    def to_sql (self) -> str: ...

def quote (s: str) -> str:
    """Quote `s` if contains space"""
    return f'"{s}"' if " " in s else s

__all__ = [
    "quote",
    "AliasedColumn",
]