# std
from typing import Protocol
# internal
from sqlize.table import Table

class ITable (Protocol):
    __table__: Table
class ITableStr (Protocol):
    __table__: str

type SQLizerModel = type[ITableStr | ITable]

__all__ = ["SQLizerModel"]