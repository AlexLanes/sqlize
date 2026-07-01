# std
from typing import Self, Protocol
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
# internal
from sqlize.parameters import *
from sqlize.shared import SequenceAny, ManySequenceAny, DataSQL, quote
from sqlize.expression import Expression, OrderableExpression, AliasedExpression
from sqlize.column import Column, AliasedColumn
from sqlize.table import Table

@dataclass
class Data:
    """`@dataclass` of private attributes combined with `SupportParameters`"""

    quote_info: tuple[bool, str] | None = None
    """Used as `enforce, char_quote` and `None` for `"` if contains space"""
    parameter = POSITIONAL_PARAMETERS["?"]
    """Positional Parameter
    - `Default: ?`"""

    table: Table | None = None

    where: Expression | None = None
    def data_where (self, table_alias=True) -> DataSQL | None:
        if self.where is None: return
        sql = self.where.to_sql(table_alias=table_alias, quote_info=self.quote_info)
        sql.sqls.insert(0, "WHERE")
        return sql

    orderby: list[OrderableExpression] = field(default_factory=list)
    def data_orderby (self) -> DataSQL | None:
        if not self.orderby:
            return

        sqls, params = [], []
        info = self.quote_info

        for order in self.orderby:
            sql = order.to_sql(quote_info=info)
            sqls.append(sql.join())
            params.extend(sql)

        return DataSQL("ORDER BY " + ", ".join(sqls), params)

    paging: list[tuple[int, str, int]] = field(default_factory=list)
    """`[(order weight, "SQL {}", value)]`"""
    def data_paging (self) -> DataSQL | None:
        if not self.paging:
            return

        sqls, params = [], []
        for _, sql, value in sorted(self.paging, key=lambda x: x[0]):
            sqls.append(sql)
            params.append(value)
        return DataSQL("\n".join(sqls), params)

    returning: list[str | Column | AliasedColumn | AliasedExpression] = field(default_factory=list)
    def data_returning (self, table_alias=False) -> DataSQL | None:
        if not self.returning:
            return

        sqls, params = [], []
        quote_info = self.quote_info

        for column in self.returning:
            if isinstance(column, str):
                sqls.append(quote(column, quote_info))
            else:
                sql = column.to_sql(table_alias=table_alias, quote_info=quote_info)
                sqls.append(sql.join())
                params.extend(sql)

        return DataSQL(
            "RETURNING " + ", ".join(sqls),
            params
        )

    output: list[str | Column | AliasedColumn | AliasedExpression] = field(default_factory=list)
    def data_output (self, table_alias=False) -> DataSQL | None:
        if not self.output:
            return

        sqls, params = [], []
        quote_info = self.quote_info

        for column in self.output:
            if isinstance(column, str):
                sqls.append(quote(column, quote_info))
            else:
                sql = column.to_sql(table_alias=table_alias, quote_info=quote_info)
                sqls.append(sql.join())
                params.extend(sql)

        return DataSQL(
            "OUTPUT " + ", ".join(sqls),
            params
        )

class SupportsData (Protocol):
    data: Data

class SupportsWhere (SupportsData):

    def __init__ (self) -> None:
        super().__init__()

    def Where (self, expression: Expression) -> Self:
        """Apply `WHERE {expression}`
        #### A `Column` can build `Expression`
        #### See `E` docstring for more info

        # Examples
        `users = T.users`  
        `Where(users.id == 1)`  
        `Where( (users.id % 2 == 0) )`  
        `Where( (users.role == "admin").Not() )`  
        `Where( (users.role == "admin") & (users.name != None) )`  
        """
        self.data.where = expression
        return self

class SupportsOrderBy (SupportsData):

    def __init__ (self) -> None:
        super().__init__()

    def OrderBy (self, *orderable: OrderableExpression) -> Self:
        """Apply `ORDER BY {order, ...}`

        ### Example
        ```
        Select(T.users.All())
        .From(T.users)
        .OrderBy(
            T.users.id.ASC,
            T.users.name.DESC.NULLS_FIRST,
            (T.users.id % 2).DESC
        )
        ```
        """
        self.data.orderby.extend(orderable)
        return self

class SupportsPaging (SupportsData):

    def __init__ (self) -> None:
        super().__init__()

    def Limit (self, value: int | None) -> Self:
        """Apply `LIMIT {value}`
        - `None` do nothing
        #### Supported By: `SQLite` `PostgreSQL` `MySQL`"""
        if value is None:
            return self
        if value <= 0:
            raise ValueError(f"{self.__class__.__name__}().Limit({value}) should be >= 1")
        self.data.paging.append((1, "LIMIT {}", value))
        return self

    def Offset (self, value: int | None) -> Self:
        """Apply `OFFSET {value}`
        - `None` do nothing
        #### Supported By: `SQLite` `PostgreSQL` `MySQL`"""
        if value is None:
            return self
        if value < 0:
            raise ValueError(f"{self.__class__.__name__}().Offset({value}) should be >= 0")
        self.data.paging.append((2, "OFFSET {}", value))
        return self

    def OffsetRows (self, value: int | None) -> Self:
        """Apply `OFFSET {value} ROWS`
        - `None` do nothing
        #### Supported By: `PostgreSQL` `Oracle` `MicrosoftSQL`"""
        if value is None:
            return self
        if value < 0:
            raise ValueError(f"{self.__class__.__name__}().OffsetRows({value}) should be >= 0")
        self.data.paging.append((2, "OFFSET {} ROWS", value))
        return self

    def FetchNextRowsOnly (self, value: int | None) -> Self:
        """Apply `FETCH NEXT {value} ROWS ONLY`
        - `None` do nothing
        #### Supported By: `PostgreSQL` `Oracle` `MicrosoftSQL`"""
        if value is None:
            return self
        if value <= 0:
            raise ValueError(f"{self.__class__.__name__}().FetchNextRowsOnly({value}) should be >= 1")
        self.data.paging.append((3, "FETCH NEXT {} ROWS ONLY", value))
        return self

    def FetchFirstRowsOnly (self, value: int | None) -> Self:
        """Apply `FETCH FIRST {value} ROWS ONLY`
        - `None` do nothing
        #### Supported By: `PostgreSQL` `Oracle`"""
        if value is None:
            return self
        if value <= 0:
            raise ValueError(f"{self.__class__.__name__}().FetchFirstRowsOnly({value}) should be >= 1")
        self.data.paging.append((3, "FETCH FIRST {} ROWS ONLY", value))
        return self

class SupportsReturning (SupportsData):

    def __init__ (self) -> None:
        super().__init__()

    def Returning (self, *columns: str | Column | AliasedColumn | AliasedExpression) -> Self:
        """Apply `RETURNING {Columns}`
        #### Supported By: `SQLite` `PostgreSQL`
        `.Returning("*")`  
        `.Returning(A.All())`  
        `.Returning(T.users.All())`  
        `.Returning(T.users.id, A.name, "last_name")`  
        `.Returning(A.first_name.Concat(A.last_name).As("full_name"))`
        ### PostgreSQL
        `.Returning(T.old.name.As("old_name"), T.new.name.As("new_name"))`"""
        self.data.returning.extend(columns)
        return self

    def Output (self, *columns: str | Column | AliasedColumn | AliasedExpression) -> Self:
        """Apply `OUTPUT {Columns}`
        #### Supported By: `MicrosoftSQL`
        `.Output(T.inserted.All())`  
        `.Output(T.deleted.name.As("old_name"), T.inserted.name.As("new_name"))`"""
        self.data.output.extend(columns)
        return self

class SupportParameters (SupportsData):

    data: Data

    def __init__ (self) -> None:
        super().__init__()
        self.data = Data()

    def set_parameter (self, positional: Positionals | type[IPositionalParameter],
                             quote_info: tuple[bool, str] | None = None) -> Self:
        """Change `PositionalParameter` and `quote_info`"""
        if not hasattr(self, "data"):
            self.data = Data()

        self.data.quote_info = quote_info

        if not isinstance(positional, str):
            self.data.parameter = positional
            return self
        if p := POSITIONAL_PARAMETERS.get(positional):
            self.data.parameter = p
            return self

        name = self.__class__.__name__
        raise ValueError(f"Unexpected Positional Parameter for {name}().set_parameter({positional!r})")

class ExecutableStatement (ABC, SupportParameters):

    def __init__ (self) -> None:
        super().__init__()

    @abstractmethod
    def to_sql (self) -> tuple[str, SequenceAny | ManySequenceAny]:
        """`SQL: Parameterized` as `(sql, params)`"""
        ...

__all__ = [
    "Data",

    "SupportsWhere",
    "SupportsPaging",
    "SupportsOrderBy",
    "SupportsReturning",

    "SupportParameters",
    "ExecutableStatement",
]