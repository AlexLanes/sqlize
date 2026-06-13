# std
from __future__ import annotations
from typing import Any, Self, Iterable, Literal
from datetime import datetime, date
# internal
from simple_sql_builder.shared import (
    quote,
    Orderable as _Orderable,
    AliasedColumn as _AliasedColumn
)

def to_sql_str (value: object) -> str:
    match value:
        case AliasedColumn(): return value.to_sql()
        case Expression(): return (
            sql
            if (sql := value.to_sql())[0] == "("
            else f"({sql})"
        )

        case None:  return "NULL"
        case True:  return "TRUE"
        case False: return "FALSE"
        case str(): return repr(value)

        case date():
            return repr(value.isoformat())
        case datetime():
            return repr(value.isoformat(sep=" "))

        case list() | tuple() | set():
            values = ", ".join(map(to_sql_str, value))
            return f"({values})"

        case _: return str(value)

class AliasedColumn (_AliasedColumn):
    def __init__ (self, expression: Expression, alias: str) -> None:
        self.alias = alias
        self.expression = expression

    def __repr__ (self) -> str:
        return f"<AliasedColumn => {self.to_sql()}>"

    def to_sql (self) -> str:
        """`SQL: ({Expression}) AS {alias}`"""
        alias = quote(self.alias)
        sql = self.expression.to_sql()
        return (
            f"{sql} AS {alias}"
            if sql[0] == "(" else
            f"({sql}) AS {alias}"
        )

class Orderable (_Orderable):
    def __init__(self, order: Literal["ASC", "DESC"], expression: Expression | AliasedColumn) -> None:
        self.nulls = None
        self.order = order
        self.expression = expression

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
        """`SQL: ({Expression}) ASC|DESC [NULLS FIRST|LAST]` version"""
        sql = f"({self.expression.to_sql()}) {self.order}"
        return (
            f"{sql} NULLS {self.nulls}"
            if self.nulls is not None
            else sql
        )

class Expression:
    def __repr__ (self) -> str:
        return f"<Expression => {self.to_sql()}>"

    def to_sql (self) -> str:
        raise NotImplementedError

    #--------------------#
    # Logical Expression #
    #--------------------#

    def __or__ (self, expression: Expression) -> Expression:
        """Apply `(self OR {expression})`"""
        return BinaryExpression(self, "OR", expression)

    def __and__ (self, expression: Expression) -> Expression:
        """Apply `(self AND {expression})`"""
        return BinaryExpression(self, "AND", expression)

    def Not (self) -> Expression:
        """Apply `NOT ({expression})`"""
        return UnaryExpression("NOT", self)

    #-----------------------#
    # Comparable Expression #
    #-----------------------#

    def __eq__ (self, other: object) -> Expression: # type: ignore
        """Apply `self = {other}`"""
        if other is None:
            return BinaryExpression(self, "IS", None)
        return BinaryExpression(self, "=", other)

    def __ne__ (self, other: object) -> Expression: # type: ignore
        """Apply `self != {other}`"""
        if other is None:
            return BinaryExpression(self, "IS NOT", None)
        return BinaryExpression(self, "!=", other)

    def __gt__ (self, other: object) -> Expression:
        """Apply `self > {other}`"""
        return BinaryExpression(self, ">", other)

    def __lt__ (self, other: object) -> Expression:
        """Apply `self < {other}`"""
        return BinaryExpression(self, "<", other)

    def __ge__ (self, other: object) -> Expression:
        """Apply `self >= {other}`"""
        return BinaryExpression(self, ">=", other)

    def __le__ (self, other: object) -> Expression:
        """Apply `self <= {other}`"""
        return BinaryExpression(self, "<=", other)

    def In (self, values: Iterable[Any]) -> Expression:
        """Apply `self IN {(values)}`"""
        return BinaryExpression(self, "IN", tuple(values))

    #-----------------------#
    # Arithmetic Expression #
    #-----------------------#

    def __add__ (self, other: object) -> Expression:
        """Apply `self + {other}`"""
        return BinaryExpression(self, "+", other)

    def __sub__ (self, other: object) -> Expression:
        """Apply `self - {other}`"""
        return BinaryExpression(self, "-", other)

    def __mul__ (self, other: object) -> Expression:
        """Apply `self * {other}`"""
        return BinaryExpression(self, "*", other)

    def __truediv__ (self, other: object) -> Expression:
        """Apply `self / {other}`"""
        return BinaryExpression(self, "/", other)

    def __mod__ (self, other: object) -> Expression:
        """Apply `self % {other}`"""
        return BinaryExpression(self, "%", other)

    #-----------#
    # Orderable #
    #-----------#

    @property
    def ASC (self) -> Orderable:
        """Apply `({Expression}) ASC` for `Select.Orderby`"""
        return Orderable("ASC", self)

    @property
    def DESC (self) -> Orderable:
        """Apply `({Expression}) DESC` for `Select.Orderby`"""
        return Orderable("DESC", self)

    #---------------#
    # AliasedColumn #
    #---------------#

    def As (self, alias: str) -> _AliasedColumn:
        """Apply `(expression) AS {alias}` to `Select()` as a Column
        - `Select( (T.orders.quantity * T.orders.value).As("Total") )`"""
        return AliasedColumn(self, alias)

class UnaryExpression (Expression):
    def __init__ (self, operator: str, right: Any) -> None:
        self.right = right
        self.operator = operator

    def to_sql (self) -> str:
        r = to_sql_str(self.right)
        return f"NOT ({r})"

class BinaryExpression (Expression):
    def __init__ (self, left: Any, operator: str, right: Any) -> None:
        self.operator = operator
        self.left, self.right = left, right

    def to_sql (self) -> str:
        l, r = map(to_sql_str, [self.left, self.right])

        sql = f"{l} {self.operator} {r}"
        return (
            f"({sql})"
            if self.operator in {"AND", "OR"}
            else sql
        )

__all__ = ["Expression"]