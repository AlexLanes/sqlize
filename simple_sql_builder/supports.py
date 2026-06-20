# std
from typing import Self
from abc import ABC, abstractmethod
# internal
from simple_sql_builder.shared import *
from simple_sql_builder.parameters import *
from simple_sql_builder.expression import Expression
from simple_sql_builder.column import Column, AliasedColumn

class SupportParameter:

    parameter = POSITIONAL_PARAMETERS["?"]
    """Positional Parameter
    - `Default: ?`"""

    def set_parameter (self, positional: Positionals) -> Self:
        """Change `PositionalParameter`
        - `Default: ?`"""
        if p := POSITIONAL_PARAMETERS.get(positional):
            self.parameter = p
            return self

        name = self.__class__.__name__
        raise ValueError(f"Unexpected Positional Parameter for {name}().set_parameter({positional!r})")

class StatementWithParameter (ABC, SupportParameter):
    def __init__ (self) -> None:
        super().__init__()

    @abstractmethod
    def to_sql (self) -> tuple[str, SequenceAny | ManySequenceAny]:
        """`SQL: Parameterized` as `(sql, params)`"""
        ...

class SupportsWhere:

    data_where: Expression | None

    def __init__ (self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.data_where = None

    @property
    def data_where_sql (self) -> str | None:
        """`SQL` version of `WHERE`
        - `None` if empty"""
        return (
            f"WHERE {self.data_where.to_sql()}"
            if self.data_where is not None
            else None
        )

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

class SupportsOrderBy:

    data_orderby: list[OrderableExpression]

    def __init__ (self) -> None:
        super().__init__()
        self.data_orderby = []

    @property
    def data_orderby_sql (self) -> str | None:
        """`SQL` version of `ORDER BY`
        - `None` if empty"""
        if self.data_orderby:
            return None
        return "ORDER BY" + ", ".join(o.to_sql() for o in self.data_orderby)

    def OrderBy (self, *order: OrderableExpression) -> Self:
        """Apply `ORDER BY {order, ...}`

        ### Example
        ```
        Select(T.users.All())
        .From(T.users)
        .OrderBy(
            T.users.id.ASC,
            T.users.name.DESC.NullsFirst,
            (T.users.id % 2).DESC
        )
        ```
        """
        self.data_orderby.extend(order)
        return self

class SupportsPaging:

    data_paging: list[tuple[int, str, int]]
    """`[(order weight, "SQL {value}", value)]`"""

    def __init__ (self) -> None:
        super().__init__()
        self.data_paging = []

    @property
    def data_paging_sql (self) -> str | None:
        """`SQL` version of `LIMITS` and `OFFSETS` joined by `\\n`
        - `None` if empty"""
        if not self.data_paging:
            return
        return "\n".join(
            sql.format(value=value)
            for _, sql, value in sorted(self.data_paging, key = lambda x: x[0])
        )

    def Limit (self, value: int | None) -> Self:
        """Apply `LIMIT {value}`
        - `None` do nothing"""
        if value is None:
            return self
        if value <= 0:
            raise ValueError(f"{self.__class__.__name__}().Limit({value}) should be >= 1")
        self.data_paging.append((1, "LIMIT {value}", value))
        return self

    def Offset (self, value: int | None) -> Self:
        """Apply `OFFSET {value}`
        - `None` do nothing"""
        if value is None:
            return self
        if value < 0:
            raise ValueError(f"{self.__class__.__name__}().Offset({value}) should be >= 0")
        self.data_paging.append((2, "OFFSET {value}", value))
        return self

    def OffsetRows (self, value: int | None) -> Self:
        """Apply `OFFSET {value} ROWS`
        - `None` do nothing"""
        if value is None:
            return self
        if value < 0:
            raise ValueError(f"{self.__class__.__name__}().OffsetRows({value}) should be >= 0")
        self.data_paging.append((2, "OFFSET {value} ROWS", value))
        return self

    def FetchNextRowsOnly (self, value: int | None) -> Self:
        """Apply `FETCH NEXT {value} ROWS ONLY`
        - `None` do nothing"""
        if value is None:
            return self
        if value <= 0:
            raise ValueError(f"{self.__class__.__name__}().FetchNextRowsOnly({value}) should be >= 1")
        self.data_paging.append((3, "FETCH NEXT {value} ROWS ONLY", value))
        return self

    def FetchFirstRowsOnly (self, value: int | None) -> Self:
        """Apply `FETCH FRIST {value} ROWS ONLY`
        - `None` do nothing"""
        if value is None:
            return self
        if value <= 0:
            raise ValueError(f"{self.__class__.__name__}().FetchFirstRowsOnly({value}) should be >= 1")
        self.data_paging.append((3, "FETCH FRIST {value} ROWS ONLY", value))
        return self

class SupportsReturning:

    data_returning: list[Column | AliasedColumn]

    def __init__ (self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.data_returning = []

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
        self.data_returning.extend(value)
        return self

__all__ = [
    "SupportsWhere",
    "SupportsPaging",
    "SupportsOrderBy",
    "SupportParameter",
    "SupportsReturning",
    "StatementWithParameter",
]