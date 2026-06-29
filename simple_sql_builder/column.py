# std
from __future__ import annotations
from typing import Any, Literal, override, overload
# internal
from simple_sql_builder.shared import quote, DataSQL
from simple_sql_builder.expression import (
    Expression, BinaryExpression, ConstantExpression,
    OrderableExpression, AliasedExpression
)

ESPECIAL_TABLES = {"old", "new", "inserted", "deleted"}

class OrderableColumn (OrderableExpression):

    column: Column | AliasedColumn

    def __init__ (self, order: Literal["ASC", "DESC"], column: Column | AliasedColumn) -> None:
        super().__init__(order, self)
        self.column = column

    def to_sql (self, *, table_alias=True) -> DataSQL:
        """`SQL: (alias|ta.name) ASC|DESC [NULLS FIRST|LAST]` version"""
        name = (
            self.column.alias
            if isinstance(self.column, AliasedColumn)
            else self.column.to_sql(table_alias=table_alias).join()
        )
        return DataSQL(
            f"{name} {self.order}"
            if self.nulls is None else
            f"{name} {self.order} NULLS {self.nulls}",
            []
        )

class AliasedColumn (AliasedExpression):

    alias: str
    """Quoted `alias`"""
    column: Column | None

    def __init__ (self, column: Column | None, alias: str) -> None:
        self.column = column
        self.params = tuple()
        self.alias = quote(alias)

    @override
    def to_sql (self, *, table_alias=True):
        """`SQL: [{Column} AS] {alias}`"""
        if self.column is None:
            return DataSQL(self.alias, [])
        sql = self.column.to_sql(table_alias=table_alias)
        return DataSQL(f"{sql.join()} AS {self.alias}", sql.params)

    #-----------#
    # Orderable #
    #-----------#

    @property
    def ASC (self) -> OrderableColumn:
        """Apply `{alias} ASC` for `Select.Orderby`"""
        return OrderableColumn("ASC", self)

    @property
    def DESC (self) -> OrderableColumn:
        """Apply `{alias} DESC` for `Select.Orderby`"""
        return OrderableColumn("DESC", self)

class ColumnEqualsValue (BinaryExpression):

    left: Column
    right: Any

    def __init__ (self, left: Column, operator: str, right: Any) -> None:
        super().__init__(left, operator, right)

class ColumnWithDefaultValue (ConstantExpression):

    column: Column

    def __init__ (self, name: str, column: Column) -> None:
        super().__init__(name)
        self.column = column

class Column (Expression):

    ta: str
    name: str

    def __init__ (self, name: str, table_alias: str) -> None:
        self.ta = table_alias
        self.name = quote(name)

    def __hash__ (self) -> int:
        return hash((self.name, self.ta))

    @override
    def to_sql (self, *, table_alias=True):
        """`SQL: table_alias.name` version"""
        return DataSQL(
            f"{self.ta}.{self.name}"
            if table_alias or self.ta.lower() in ESPECIAL_TABLES
            else self.name,
            []
        )

    def As (self, alias: str) -> AliasedColumn:
        """Apply `able_alias.name AS alias`"""
        return AliasedColumn(self, alias)

    @overload
    def __eq__ (self, other: Expression) -> BinaryExpression: ... # type: ignore
    @overload
    def __eq__ (self, other: object) -> ColumnEqualsValue: ...
    @override
    def __eq__ (self, other: Expression | Any) -> BinaryExpression | ColumnEqualsValue:
        operator = "IS" if other is None else "="
        cls = BinaryExpression if isinstance(other, Expression) else ColumnEqualsValue
        return cls(self, operator, other)

    @property
    def DEFAULT_VALUE (self) -> ColumnWithDefaultValue:
        return ColumnWithDefaultValue("DEFAULT", self)

    #-----------#
    # Orderable #
    #-----------#

    @property
    def ASC (self) -> OrderableColumn:
        """Apply `{ta.name} ASC` for `Select.Orderby`"""
        return OrderableColumn("ASC", self)

    @property
    def DESC (self) -> OrderableColumn:
        """Apply `{ta.name} DESC` for `Select.Orderby`"""
        return OrderableColumn("DESC", self)

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

__all__ = ["Column", "A"]