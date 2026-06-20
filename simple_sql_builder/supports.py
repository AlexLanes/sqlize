# std
from typing import Self
# internal
from simple_sql_builder.expression import Expression
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

class SupportsWhere:

    data_expression: Expression | None

    def __init__ (self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.data_expression = None

    def Where (self, expression: Expression) -> Self:
        """Apply `WHERE {expression}`
        #### A `Column` is a `Expression`
        #### See `E` docstring for more info
        <br>

        ### Examples
        `users = T.users`  
        `Where(users.id == 1)`  
        `Where( (users.id % 2 == 0) )`  
        `Where( (users.role == "admin").Not() )`  
        `Where( (users.role == "admin") & (users.name != None) )`  
        """
        self.data_expression = expression
        return self

class SupportsReturning:

    data_returning: list[Column | AliasedColumn]

    def __init__ (self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.data_returning = list[Column | AliasedColumn]()

    @property
    def data_returning_sql (self) -> str | None:
        """`SQL` version of `RETURNING`
        - `None` if empty"""
        if not self.data_returning:
            return

        return "RETURNING " + ", ".join(
            column.name
            if isinstance(column, Column)
            else column.alias

            for column in self.data_returning
        )

    def Returning (self, *value: Column | AliasedColumn) -> Self:
        """Apply `RETURNING {Columns}`  
        `.Returning(A.All())`  
        `.Returning(T.users.id, A.name)`"""
        self.data_returning = list(value)
        return self

__all__ = [
    "SupportsWhere",
    "SupportsExecute",
    "SupportsReturning",
]