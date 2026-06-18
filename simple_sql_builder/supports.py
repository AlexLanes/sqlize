# std
from typing import Self
# internal
from simple_sql_builder.connection import Connection, ResultSQL
from simple_sql_builder.column import Column, AliasedColumn

class SupportsExecute:
    def __init__ (self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
    
    def to_raw_sql (self) -> str:
        """Raw `SQL: Statement` version"""
        raise NotImplementedError

    def execute (self, connection: Connection, **kwargs) -> ResultSQL:
        """Execute Statement for `Connection`
        - `kwargs` additional params `execute()` or `executemany()` accepts"""
        return connection.cursor().execute(self.to_raw_sql(), **kwargs)

class SupportsReturning:
    def __init__ (self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.data_returning = list[Column | AliasedColumn]()

    def Returning (self, *value: Column | AliasedColumn) -> Self:
        """Apply `RETURNING {Columns}`  
        `.Returning(A.All())`  
        `.Returning(T.users.id, A.name)`"""
        self.data_returning = list(value)
        return self

__all__ = [
    "SupportsExecute",
    "SupportsReturning",
]