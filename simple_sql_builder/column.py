# std
from __future__ import annotations
from typing import Any, Self, Literal, override
# internal
from simple_sql_builder.shared import (
    quote,
    OrderableExpression,
    AliasedColumn as _AliasedColumn
)
from simple_sql_builder.expression import Expression, LiteralExpression

class Orderable (OrderableExpression):
    def __init__(self, order: Literal["ASC", "DESC"], column: Column | AliasedColumn) -> None:
        self.nulls = None
        self.order = order
        self.column = column

    def __repr__ (self) -> str:
        return f"<Orderable => {self.to_sql()}>"

    @property
    def NullsFirst (self) -> Self:
        self.nulls = "FIRST"
        return self

    @property
    def NullsLast (self) -> Self:
        self.nulls = "LAST"
        return self

    def to_sql (self) -> str:
        """`SQL: (alias|ta.name) ASC|DESC [NULLS FIRST|LAST]` version"""
        name = (
            self.column.alias
            if isinstance(self.column, AliasedColumn)
            else self.column.to_sql()
        )
        return (
            f"{name} {self.order}"
            if self.nulls is None else
            f"{name} {self.order} NULLS {self.nulls}"
        )

class AliasedColumn (_AliasedColumn, Expression):
    def __init__(self, column: Column | None, alias: str) -> None:
        self.column = column
        self.alias = quote(alias)

    def __repr__ (self) -> str:
        return f"<AliasedColumn => {self.to_sql()}>"

    def to_sql (self) -> str:
        """`SQL: [{Column} AS] {alias}`"""
        return (
            f"{self.column.to_sql()} AS {self.alias}"
            if self.column is not None
            else self.alias
        )

    #-----------#
    # Orderable #
    #-----------#

    @property
    def ASC (self) -> Orderable: # type: ignore
        """Apply `{alias} ASC` for `Select.Orderby`"""
        return Orderable("ASC", self)

    @property
    def DESC (self) -> Orderable: # type: ignore
        """Apply `{alias} DESC` for `Select.Orderby`"""
        return Orderable("DESC", self)

class ColumnWithValue (LiteralExpression):

    column: Column

    def __init__ (self, value: Any, column: Column) -> None:
        super().__init__(value)
        self.column = column

    def __repr__(self) -> str:
        return f"<ColumnWithValue {self.column.name}={self.value}>"

class Column (Expression):
    def __init__ (self, name: str, table_alias: str) -> None:
        self.name = name
        self.ta = table_alias

    def __repr__ (self) -> str:
        return f"<Column => {self.to_sql()}>"

    def __hash__ (self) -> int:
        return hash((self.name, self.ta))

    def to_sql (self) -> str:
        """`SQL: table_alias.name` version"""
        return f"{self.ta}.{quote(self.name)}"

    @override
    def Value (self, value: Any) -> ColumnWithValue:
        """Create a `Value` for the `Column`"""
        return ColumnWithValue(value, self)

    def As (self, alias: str) -> AliasedColumn:
        """Apply `able_alias.name AS alias`"""
        return AliasedColumn(self, alias)

    #-----------#
    # Orderable #
    #-----------#

    @property
    def ASC (self) -> Orderable: # type: ignore
        """Apply `{ta.name} ASC` for `Select.Orderby`"""
        return Orderable("ASC", self)

    @property
    def DESC (self) -> Orderable: # type: ignore
        """Apply `{ta.name} DESC` for `Select.Orderby`"""
        return Orderable("DESC", self)

class AliasedColumnBuilder:
    def __call__ (self, alias: str) -> AliasedColumn:
        return AliasedColumn(None, alias)

    def __getattr__ (self, alias: str) -> AliasedColumn:
        return self.__call__(alias)

    def All (self) -> AliasedColumn:
        """`*`"""
        return self.__call__("*")

A = AliasedColumnBuilder()
"""Creator of `AliasedColumn`  
Can be used on `Select` `Where` `GroupBy` `OrderBy` to reference a `Column(name).As(alias)`

`A.All()`  
`A.custom_name`  
`A("custom name")`
"""

__all__ = ["Column", "A", "ColumnWithValue"]