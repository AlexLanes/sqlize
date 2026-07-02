# std
from typing import Protocol
# internal
from sqlize.shared import SQLValue
from sqlize.connections import Connection
from sqlize.orm.column import ModelData

class IModel (Protocol):

    __data__: ModelData

    def __init__ (self, **kwargs: SQLValue) -> None: ...

    @staticmethod
    def GetConnection () -> Connection: ...

__all__ = ["IModel"]