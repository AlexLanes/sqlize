# std
from __future__ import annotations
from typing import Self, Literal
# internal
from simple_sql_builder.shared import *
from simple_sql_builder.expression import Expression

class OrderColumn:
    def __init__ (self, column: Column, order: Literal["ASC", "DESC"]) -> None:
        self.column = column
        self.order = order
        self.__nulls: Literal["FIRST", "LAST"] | None = None

    def __repr__ (self) -> str:
        return f"<OrderColumn => {self.to_sql()}>"

    @property
    def NullsFirst (self) -> Self:
        """Apply `NULLS FIRST`"""
        self.__nulls = "FIRST"
        return self

    @property
    def NullsLast (self) -> Self:
        """Apply `NULLS LAST`"""
        self.__nulls = "LAST"
        return self

    def to_sql (self) -> str:
        """`SQL: alias|ta.name ASC|DESC [NULLS FIRST|LAST]` version"""
        sql = self.column.to_sql()
        return (
            f"{sql} {self.order}"
            if self.__nulls is None else
            f"{sql} {self.order} NULLS {self.__nulls}"
        )

class ColumnAsAlias (AliasedColumn):
    def __init__(self, column: Column, alias: str) -> None:
        self.alias = alias
        self.column = column

    def to_sql (self) -> str:
        """`SQL: table_alias.name AS alias` version"""
        return f"{self.column.to_sql()} AS {quote(self.alias)}"

class Column (Expression):
    def __init__ (self, name: str, table_alias: str) -> None:
        self.name = name
        self.ta = table_alias

    def __repr__ (self) -> str:
        return f"<Column => {self.to_sql()}>"

    def to_sql (self) -> str:
        """`SQL: table_alias.name` version"""
        return f"{self.ta}.{quote(self.name)}"

    def As (self, alias: str) -> AliasedColumn:
        """Apply `able_alias.name AS alias`"""
        return ColumnAsAlias(self, alias)

    #-------------#
    # OrderColumn #
    #-------------#

    @property
    def ASC (self) -> OrderColumn:
        """Apply `column ASC` for `Select.Orderby`"""
        return OrderColumn(self, "ASC")

    @property
    def DESC (self) -> OrderColumn:
        """Apply `column DESC` for `Select.Orderby`"""
        return OrderColumn(self, "DESC")

__all__ = [
    "Column",
    "OrderColumn"
]