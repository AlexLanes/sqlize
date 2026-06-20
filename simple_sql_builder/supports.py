# std
from typing import Self
from abc import ABC, abstractmethod
# internal
from simple_sql_builder.shared import *
from simple_sql_builder.parameters import *
from simple_sql_builder.expression import Expression
from simple_sql_builder.column import Column, AliasedColumn

class SupportParameters (ABC):

    def __init__ (self) -> None:
        super().__init__()

    @abstractmethod
    def to_sql (self) -> tuple[str, SequenceAny | ManySequenceAny]:
        """`SQL: Parameterized` as `(sql, params)`"""
        ...

    parameter = POSITIONAL_PARAMETERS["?"]
    """Positional Parameter
    - `Default: ?`"""

    def set_parameter (self, positional: DefaultsPositional) -> Self:
        """Change `PositionalParameter`
        - `Default: ?`"""
        if p := POSITIONAL_PARAMETERS.get(positional):
            self.parameter = p
            return self

        name = self.__class__.__name__
        raise ValueError(f"Unexpected Positional Parameter for {name}().set_parameter({positional!r})")

class SupportsWhere:

    data_where: Expression | None

    def __init__ (self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.data_where = None

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
        self.data_where = expression
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
    "SupportsReturning",
    "SupportParameters",
]