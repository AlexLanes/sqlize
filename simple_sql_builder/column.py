# std
from __future__ import annotations
from typing import Self, Literal
# internal
from simple_sql_builder.shared import (
    quote,
    Orderable as _Orderable,
    AliasedColumn as _AliasedColumn
)
from simple_sql_builder.expression import Expression

class Orderable (_Orderable):
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
            quote(self.column.alias)
            if isinstance(self.column, AliasedColumn)
            else self.column.to_sql()
        )
        return (
            f"{name} {self.order}"
            if self.nulls is None else
            f"{name} {self.order} NULLS {self.nulls}"
        )

class AliasedColumn (_AliasedColumn):
    def __init__(self, column: Column, alias: str) -> None:
        self.alias = alias
        self.column = column

    def __repr__ (self) -> str:
        return f"<AliasedColumn => {self.to_sql()}>"

    def to_sql (self) -> str:
        """`SQL: {Column} AS {alias}`"""
        return f"{self.column.to_sql()} AS {quote(self.alias)}"

    #-----------#
    # Orderable #
    #-----------#

    @property
    def ASC (self) -> Orderable:
        """Apply `{alias} ASC` for `Select.Orderby`"""
        return Orderable("ASC", self)

    @property
    def DESC (self) -> Orderable:
        """Apply `{alias} DESC` for `Select.Orderby`"""
        return Orderable("DESC", self)

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

__all__ = ["Column"]