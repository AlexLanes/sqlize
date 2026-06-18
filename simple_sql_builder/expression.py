# std
from __future__ import annotations
from datetime import datetime, date
from typing import (
    Any, Self,
    Iterable, Literal, NoReturn
)
# internal
from simple_sql_builder.shared import (
    quote,
    OrderableExpression,
    AliasedColumn as _AliasedColumn
)

type ExpOrValue = Expression  | Any
type ExpOrString = Expression | str

NOT_SET = object()
OPERATORS_FOR_PARENTESIS = {
    "IN", "NOT", "AND", "OR",
    "/", "*"
}

def to_sql_str (value: object) -> str:
    match value:
        case Expression() | AliasedColumn(): return value.to_sql()

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
        self.alias = quote(alias)
        self.expression = expression

    def __repr__ (self) -> str:
        return f"<AliasedColumn => {self.to_sql()}>"

    def to_sql (self) -> str:
        """`SQL: ({Expression}) AS {alias}`"""
        return f"({self.expression.to_sql()}) AS {self.alias}"

class Orderable (OrderableExpression):
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

    def __bool__(self) -> NoReturn:
        raise TypeError(
            "SQL expressions cannot be used as bool. "
            "Consider using .Not() for negation"
        )

    def to_sql (self) -> str:
        raise NotImplementedError

    #---------------#
    # AliasedColumn #
    #---------------#

    def Value (self, value: Any) -> LiteralExpression:
        """Create a `Expression` from a Literal `value`"""
        if isinstance(value, Expression):
            raise TypeError(f"Expression.Value(value) should be a Literal Value not a Expression")
        return LiteralExpression(value)

    def As (self, alias: str) -> _AliasedColumn:
        """Apply `(Expression) AS {alias}` to `Select()` as a Column
        - `Select( (T.orders.quantity * T.orders.value).As("Total") )`"""
        return AliasedColumn(self, alias)

    #--------------------#
    # Logical Expression #
    #--------------------#

    def __or__ (self, exp: Expression) -> Expression:
        """Apply `(self OR {exp})`"""
        return BinaryExpression(self, "OR", exp)

    def Or (self, exp: Expression) -> Expression:
        """Apply `(self OR {exp})`
        - Same as `self | exp`"""
        return BinaryExpression(self, "OR", exp)

    def __and__ (self, exp: Expression) -> Expression:
        """Apply `(self AND {exp})`"""
        return BinaryExpression(self, "AND", exp)

    def And (self, exp: Expression) -> Expression:
        """Apply `(self AND {exp})`
        - Same as `self & exp`"""
        return BinaryExpression(self, "AND", exp)

    def Not (self) -> Expression:
        """Apply `NOT ({expression})`"""
        return UnaryExpression("NOT", self)

    #-----------------------#
    # Arithmetic Expression #
    #-----------------------#

    def __add__ (self, other: ExpOrValue) -> Expression:
        """Apply `self + {other}`"""
        return BinaryExpression(self, "+", other)

    def __sub__ (self, other: ExpOrValue) -> Expression:
        """Apply `self - {other}`"""
        return BinaryExpression(self, "-", other)

    def __mul__ (self, other: ExpOrValue) -> Expression:
        """Apply `self * {other}`"""
        return BinaryExpression(self, "*", other)

    def __truediv__ (self, other: ExpOrValue) -> Expression:
        """Apply `self / {other}`"""
        return BinaryExpression(self, "/", other)

    def __mod__ (self, other: ExpOrValue) -> Expression:
        """Apply `self % {other}`"""
        return BinaryExpression(self, "%", other)

    #-----------------------#
    # Comparable Expression #
    #-----------------------#

    def __eq__ (self, other: ExpOrValue) -> Expression: # type: ignore
        """Apply `self = {other}`"""
        if other is None:
            return BinaryExpression(self, "IS", None)
        return BinaryExpression(self, "=", other)

    def __ne__ (self, other: ExpOrValue) -> Expression: # type: ignore
        """Apply `self != {other}`"""
        if other is None:
            return BinaryExpression(self, "IS NOT", None)
        return BinaryExpression(self, "!=", other)

    def __gt__ (self, other: ExpOrValue) -> Expression:
        """Apply `self > {other}`"""
        return BinaryExpression(self, ">", other)

    def __lt__ (self, other: ExpOrValue) -> Expression:
        """Apply `self < {other}`"""
        return BinaryExpression(self, "<", other)

    def __ge__ (self, other: ExpOrValue) -> Expression:
        """Apply `self >= {other}`"""
        return BinaryExpression(self, ">=", other)

    def __le__ (self, other: ExpOrValue) -> Expression:
        """Apply `self <= {other}`"""
        return BinaryExpression(self, "<=", other)

    def In (self, values: Iterable[ExpOrValue]) -> Expression:
        """Apply `self IN {(values)}`"""
        return BinaryExpression(self, "IN", tuple(values))

    def Like (self, t: ExpOrString) -> Expression:
        """Apply `self LIKE {t}`
        - Use `.As(alias)` to Select as a Column"""
        return BinaryExpression(self, "LIKE", t)

    def ILike (self, t: ExpOrString) -> Expression:
        """Apply `self ILIKE {t}`
        - Use `.As(alias)` to Select as a Column"""
        return BinaryExpression(self, "ILIKE", t)

    def Between (self, low: ExpOrValue, high: ExpOrValue) -> Expression:
        """Apply `self BETWEEN {low} AND {high}`
        - Use `.As(alias)` to Select as a Column"""
        return BetweenExpression(self, low, high)

    def Case (self) -> CaseExpression:
        """Builder of `CASE {Expression} WHEN`"""
        return CaseExpression(self)

    #-----------#
    # Orderable #
    #-----------#

    @property
    def ASC (self) -> Orderable:
        """Apply `(Expression) ASC` for `Select.Orderby`"""
        return Orderable("ASC", self)

    @property
    def DESC (self) -> Orderable:
        """Apply `(Expression) DESC` for `Select.Orderby`"""
        return Orderable("DESC", self)

    #-----------#
    # Constants #
    #-----------#

    @property
    def CURRENT_DATE (self) -> Expression:
        """Constant `CURRENT_DATE`"""
        return ConstantExpression("CURRENT_DATE")

    @property
    def CURRENT_TIME (self) -> Expression:
        """Constant `CURRENT_TIME`"""
        return ConstantExpression("CURRENT_TIME")

    @property
    def CURRENT_TIMESTAMP (self) -> Expression:
        """Constant `CURRENT_TIMESTAMP`"""
        return ConstantExpression("CURRENT_TIMESTAMP")

    @property
    def LOCAL_TIME (self) -> Expression:
        """Constant `LOCALTIME`"""
        return ConstantExpression("LOCALTIME")

    @property
    def LOCAL_TIMESTAMP (self) -> Expression:
        """Constant `LOCALTIMESTAMP`"""
        return ConstantExpression("LOCALTIMESTAMP")

    #-----------#
    # Functions #
    #-----------#

    def Upper (self) -> Expression:
        """Apply `UPPER(Expression)`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("UPPER", self)

    def Lower (self) -> Expression:
        """Apply `LOWER(Expression)`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("LOWER", self)

    def Length (self) -> Expression:
        """Apply `LENGTH(Expression)`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("LENGTH", self)

    def Trim (self) -> Expression:
        """Apply `TRIM(Expression)`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("TRIM", self)

    def Substring (self, start: int, length: int | None = None) -> Expression:
        """Apply `SUBSTRING(Expression, start, [length])`
        - Use `.As(alias)` to Select as a Column"""
        args = (start,) if length is None else (start, length)
        return NamedFunctionExpression("SUBSTRING", self, *args)

    def Coalesce (self, default: ExpOrValue) -> Expression:
        """Apply `COALESCE(Expression, default)`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("COALESCE", self, default)

    def Replace (self, search: ExpOrString, replacement: ExpOrString) -> Expression:
        """Apply `REPLACE(Expression, search, replacement)`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("REPLACE", self, search, replacement)

    def Concat (self, *v: ExpOrValue) -> Expression:
        """Apply `CONCAT(self, v...)`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("CONCAT", self, *v)

    def ConcatWithChar (self, *v: ExpOrValue, char: Literal["||", "+"] | str = "||") -> Expression:
        """Apply `self {char} v...)`
        - Use `.As(alias)` to Select as a Column"""
        return ConcatExpression(char, self, *v)

    #-------------------#
    # Numeric Functions #
    #-------------------#

    def Abs (self) -> Expression:
        """Apply `ABS(Expression)`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("ABS", self)

    def Ceil (self) -> Expression:
        """Apply `CEIL(Expression)`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("CEIL", self)

    def Floor (self) -> Expression:
        """Apply `FLOOR(Expression)`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("FLOOR", self)

    def Round (self, n: int | Expression) -> Expression:
        """Apply `ROUND(Expression, {n})`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("ROUND", self, n)

    #-----------------#
    # Group Functions #
    #-----------------#

    def Count (self) -> Expression:
        """Apply `COUNT(Expression)`
        - `T.column.All().Count()` to `COUNT(*)`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("COUNT", self)

    def Min (self) -> Expression:
        """Apply `MIN(Expression)`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("MIN", self)

    def Max (self) -> Expression:
        """Apply `MAX(Expression)`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("MAX", self)

    def Sum (self) -> Expression:
        """Apply `SUM(Expression)`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("SUM", self)

    def Avg (self) -> Expression:
        """Apply `AVG(Expression)`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("AVG", self)

class LiteralExpression (Expression):
    def __init__ (self, value: Any) -> None:
        self.value = value

    def to_sql (self) -> str:
        return to_sql_str(self.value)

class ConstantExpression (Expression):
    def __init__ (self, name: str) -> None:
        self.name = name

    def to_sql (self) -> str:
        return self.name

class ConcatExpression (Expression):
    def __init__ (self, char: str, *args: ExpOrValue) -> None:
        self.char = char
        self.args = args

    def to_sql (self) -> str:
        return f" {self.char} ".join(
            to_sql_str(arg)
            for arg in self.args
            if arg is not E
        )

class CaseExpression (Expression):
    def __init__ (self, exp: Expression) -> None:
        self.exp = exp
        self._cases = list[tuple[ExpOrValue, ExpOrValue]]()
        self._default = NOT_SET

    def When (self, when: ExpOrValue, then: ExpOrValue) -> CaseExpression:
        """Apply `WHEN {when} THEN {then}`"""
        self._cases.append((when, then))
        return self

    def Else (self, value: ExpOrValue) -> Expression:
        """Apply `ELSE {value}`
        - Use `.As(alias)` to Select as a Column"""
        self._default = value
        return self

    def to_sql (self) -> str:
        return " ".join(
            line
            for line in (
                f"CASE {to_sql_str(self.exp)}"
                if self.exp is not E
                else "CASE",

                *[f"WHEN {to_sql_str(when)} THEN {to_sql_str(then)}"
                  for when, then in self._cases],

                "" if self._default is NOT_SET
                else f"ELSE {to_sql_str(self._default)}",

                "END"
            )
            if line
        )

class NamedFunctionExpression (Expression):
    def __init__ (self, name: str, *args: ExpOrValue) -> None:
        self.name = name
        self.args = args

    def to_sql (self) -> str:
        args = ", ".join(
            to_sql_str(arg)
            for arg in self.args
            if arg is not E
        )
        return f"{self.name}({args})"

class UnaryExpression (Expression):
    def __init__ (self, operator: str, right: ExpOrValue) -> None:
        self.right = right
        self.operator = operator

    def to_sql (self) -> str:
        r = to_sql_str(self.right)
        return (
            f"{self.operator} ({r})"
            if self.operator in OPERATORS_FOR_PARENTESIS
            else f"{self.operator} {r}"
        )

class BinaryExpression (Expression):
    def __init__ (self, left: ExpOrValue, operator: str, right: ExpOrValue) -> None:
        self.operator = operator
        self.left, self.right = left, right

    def to_sql (self) -> str:
        l, r = map(to_sql_str, [self.left, self.right])

        sql = f"{l} {self.operator} {r}"
        return (
            f"({sql})"
            if self.operator in OPERATORS_FOR_PARENTESIS
            else sql
        )

class BetweenExpression (Expression):
    def __init__ (self, exp: Expression, low: ExpOrValue, high: ExpOrValue) -> None:
        self.exp = exp
        self.low = low
        self.high = high

    def to_sql (self) -> str:
        return " ".join((
            f"({to_sql_str(self.exp)}",
            f"BETWEEN {to_sql_str(self.low)}",
            f"AND {to_sql_str(self.high)})",
        ))

type EmptyExpression = Expression
E: EmptyExpression = Expression()
"""Build a `Expression` from a empty state
#### A `Column` is a `Expression`
<br>

## Arithmetic `Expressions`
`+ - * / %`

## Comparable `Expressions`
**Operators** `==` `!=` `>` `<` `>=` `<=`  
**Methods** `In()` `Like()` `ILike()` `Between()` `Case()`

## Logical `Expressions`
**OR**  `(exp) | (exp)` `exp.Or(exp)`  
**AND** `(exp) & (exp)` `exp.And(exp)`  
**NOT** `exp.Not()`

## Functions `Expressions`
`Upper()` `Lower()` `Length()` `Trim()`   
`Substring()` `Coalesce()` `Replace()` `Concat()`  
`Abs()` `Ceil()` `Floor()` `Round()`

## Group `Expressions`
`Count()`  
`Min()` `Max()`  
`Sum()` `Avg()`

## Constants `Expression`
`CURRENT_DATE` `CURRENT_TIME` `CURRENT_TIMESTAMP`  
`LOCAL_TIME` `LOCAL_TIMESTAMP`
"""

__all__ = ["Expression", "E", "to_sql_str"]