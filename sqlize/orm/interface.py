# std
from typing import Protocol
# internal
from sqlize.shared import SQLValue, ColumnData
from sqlize.connections import Connection
from sqlize.orm.column import ModelData

class IModel (Protocol):

    __data__: ModelData

    def __init__ (self, **kwargs: SQLValue) -> None: ...

    @staticmethod
    def GetConnection () -> Connection: ...

class ISupportColumnsTable (Protocol):
    def columns (self, table: str) -> list[ColumnData]: ...

class ISupportColumnsWithSchema (Protocol):
    def columns (self, table: str, schema: str | None = None) -> list[ColumnData]: ...

type ISupportColumns = ISupportColumnsTable | ISupportColumnsWithSchema

__all__ = [
    "IModel",
    "ISupportColumns",
]