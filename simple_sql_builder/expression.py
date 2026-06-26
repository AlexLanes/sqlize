# std
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import (
    Any, Self, override,
    Iterable, Literal, NoReturn
)
# internal
from simple_sql_builder.shared import (
    DataSQL,
    quote, indent,
)

type ExpOrValue  = Expression | Any
type ExpOrString = Expression | str

NOT_SET = object()
OPERATORS_FOR_PARENTESIS = {
    "NOT", "AND", "OR",
    "IN",  "/", "*"
}

def to_sql (value: object, *, table_alias=True) -> DataSQL:
    match value:
        case AbstractExpression():
            return value.to_sql(table_alias=table_alias)

        case list() | tuple() | set():
            all_params = []
            sqls_parts = list[str]()

            for item in value:
                sql = to_sql(item, table_alias=table_alias)
                sqls_parts.append(str(sql))
                all_params.extend(sql.params)

            return DataSQL(f"({ ", ".join(sqls_parts) })", all_params)

        case _: return DataSQL("{}", [value])

class AbstractExpression (ABC):

    values: tuple[Any, ...]

    def __init__ (self, *values: Any) -> None:
        self.values = tuple(
            value
            for value in values
            if value is not E
        )

    def __repr__ (self) -> str:
        sql = self.to_sql()
        name = self.__class__.__name__
        return f"<{name} => {sql.params} {sql}>"

    @abstractmethod
    def to_sql (self, *, table_alias=True) -> DataSQL:
        """`SQL: Parameterized` as `(sql, params)`
        - `table_alias` used to remove the table alias from columns
        - Formatted as Python Positional Parameter `{}` to `self.values`"""
        ...

class OrderableExpression (AbstractExpression):

    order: Literal["ASC", "DESC"]
    nulls: Literal["FIRST", "LAST"] | None = None
    expression: AbstractExpression

    def __init__(self, order: Literal["ASC", "DESC"], expression: AbstractExpression) -> None:
        super().__init__()
        self.nulls = None
        self.order = order
        self.expression = expression

    @property
    def NULLS_FIRST (self) -> Self:
        self.nulls = "FIRST"
        return self

    @property
    def NULLS_LAST (self) -> Self:
        self.nulls = "LAST"
        return self

    @override
    def to_sql (self, *, table_alias=True):
        """`SQL: ({ Expression }) ASC|DESC [NULLS FIRST|LAST]` version"""
        sql = to_sql(self.expression, table_alias=table_alias)
        params = sql.params

        sql = f"({ sql }) {self.order}"
        return DataSQL(
            f"{sql} NULLS {self.nulls}"
            if self.nulls is not None
            else sql,

            params
        )

class Expression (AbstractExpression):
    def __init__ (self, *values: Any) -> None:
        super().__init__(*values)

    def __bool__ (self) -> NoReturn:
        raise TypeError(
            "SQL expressions cannot be used as bool. "
            "Consider using .Not() for negation"
        )

    #---------------#
    # AliasedColumn #
    #---------------#

    def Value (self, value: Any) -> LiteralExpression:
        """Create a `Expression` from a Literal `value`"""
        if isinstance(value, AbstractExpression):
            raise TypeError(
                "Column.Value(value) should be a Literal Value not an Expression. "
                "Consider using (Expression).As(alias)"
            )
        return LiteralExpression(value)

    def As (self, alias: str) -> AliasedExpression:
        """Apply `({ Expression }) AS {alias}` to `Select()` as a Column
        - `Select(( T.orders.quantity * T.orders.value ).As("Total"))`"""
        return AliasedExpression(self, alias)

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
        """Apply `NOT ({ Expression })`"""
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
        """Apply `(self * {other})`"""
        return BinaryExpression(self, "*", other)

    def __truediv__ (self, other: ExpOrValue) -> Expression:
        """Apply `(self / {other})`"""
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

    def In (self, values: Iterable[ExpOrValue] | Select | Union) -> Expression:
        """Apply `self IN ({ values })`"""
        return (
            SubqueryExpression(self, "IN", values)
            if isinstance(values, Queryable)
            else BinaryExpression(self, "IN", tuple(values))
        )

    def Exists (self, subquery: Select | Union) -> Expression:
        """Apply `EXISTS ({ subquery })`"""
        return SubqueryExpression(None, "EXISTS", subquery)

    def Like (self, t: ExpOrString) -> Expression:
        """Apply `self LIKE {t}`
        - Use `.As(alias)` to Select as a Column"""
        return BinaryExpression(self, "LIKE", t)

    def ILike (self, t: ExpOrString) -> Expression:
        """Apply `self ILIKE {t}`
        - Use `.As(alias)` to Select as a Column"""
        return BinaryExpression(self, "ILIKE", t)

    def Between (self, low: ExpOrValue, high: ExpOrValue) -> Expression:
        """Apply `(self BETWEEN {low} AND {high})`
        - Use `.As(alias)` to Select as a Column"""
        return BetweenExpression(self, low, high)

    def Case (self) -> CaseExpression:
        """Builder of `CASE {Expression} WHEN`"""
        return CaseExpression(self)

    #-----------#
    # Orderable #
    #-----------#

    @property
    def ASC (self) -> OrderableExpression:
        """Apply `({ Expression }) ASC` for `OrderBy`"""
        return OrderableExpression("ASC", self)

    @property
    def DESC (self) -> OrderableExpression:
        """Apply `({ Expression }) DESC` for `OrderBy`"""
        return OrderableExpression("DESC", self)

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
        """Apply `UPPER({ Expression })`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("UPPER", self)

    def Lower (self) -> Expression:
        """Apply `LOWER({ Expression })`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("LOWER", self)

    def Length (self) -> Expression:
        """Apply `LENGTH({ Expression })`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("LENGTH", self)

    def Trim (self) -> Expression:
        """Apply `TRIM({ Expression })`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("TRIM", self)

    def Cast (self, as_type: str) -> Expression:
        """Apply `CAST({Expression} AS {as_type})`
        - Use `.As(alias)` to Select as a Column"""
        return CastExpression(self, as_type)

    def Substring (self, start: int, length: int | None = None) -> Expression:
        """Apply `SUBSTRING({ Expression }, start, [length])`
        - Use `.As(alias)` to Select as a Column"""
        args = (start,) if length is None else (start, length)
        return NamedFunctionExpression("SUBSTRING", self, *args)

    def Coalesce (self, default: ExpOrValue) -> Expression:
        """Apply `COALESCE({ Expression }, default)`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("COALESCE", self, default)

    def Replace (self, search: ExpOrString, replacement: ExpOrString) -> Expression:
        """Apply `REPLACE({ Expression }, search, replacement)`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("REPLACE", self, search, replacement)

    def Concat (self, *v: ExpOrValue) -> Expression:
        """Apply `CONCAT({ Expression }, v...)`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("CONCAT", self, *v)

    def ConcatWithChar (self, *v: ExpOrValue, char: Literal["||", "+"] | str = "||") -> Expression:
        """Apply `self {char} v...`
        - Use `.As(alias)` to Select as a Column"""
        return ConcatExpression(char, self, *v)

    #-------------------#
    # Numeric Functions #
    #-------------------#

    def Abs (self) -> Expression:
        """Apply `ABS({ Expression })`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("ABS", self)

    def Ceil (self) -> Expression:
        """Apply `CEIL({ Expression })`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("CEIL", self)

    def Floor (self) -> Expression:
        """Apply `FLOOR({ Expression })`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("FLOOR", self)

    def Round (self, n: int | Expression) -> Expression:
        """Apply `ROUND({ Expression }, n)`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("ROUND", self, n)

    #-----------------#
    # Group Functions #
    #-----------------#

    def Count (self) -> Expression:
        """Apply `COUNT({ Expression })`
        - `T.column.All().Count()` to `COUNT(*)`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("COUNT", self)

    def Min (self) -> Expression:
        """Apply `MIN({ Expression })`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("MIN", self)

    def Max (self) -> Expression:
        """Apply `MAX({ Expression })`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("MAX", self)

    def Sum (self) -> Expression:
        """Apply `SUM({ Expression })`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("SUM", self)

    def Avg (self) -> Expression:
        """Apply `AVG({ Expression })`
        - Use `.As(alias)` to Select as a Column"""
        return NamedFunctionExpression("AVG", self)

class AliasedExpression (Expression):
    """`Expression` with alias `AS`"""

    alias: str
    """Quoted `alias`"""

    def __init__ (self, expression: Expression, alias: str) -> None:
        super().__init__()
        self.alias = quote(alias)
        self.expression = expression

    @override
    def to_sql (self, *, table_alias=True):
        """`SQL: ({ Expression }) AS {alias}`"""
        sql = to_sql(self.expression, table_alias=table_alias)
        return DataSQL(f"({ sql }) AS {self.alias}", sql.params)

class LiteralExpression (Expression):
    @override
    def to_sql (self, *, table_alias=True):
        return DataSQL("{}", self.values)

class ConstantExpression (Expression):
    @override
    def to_sql (self, *, table_alias=True):
        return DataSQL(str(self.values[-1]), [])

class ConcatExpression (Expression):

    char: str

    def __init__ (self, char: str, *values: ExpOrValue) -> None:
        super().__init__(*values)
        self.char = char

    @override
    def to_sql (self, *, table_alias=True):
        sqls, params = [], []
        generator = (to_sql(v, table_alias=table_alias) for v in self.values)

        for sql in generator:
            sqls.extend(sql.sqls)
            params.extend(sql)

        return DataSQL(
            f" {self.char} ".join(sqls),
            params
        )

class CaseExpression (Expression):

    exp: Expression
    data_cases: list[tuple[ExpOrValue, ExpOrValue]]
    default_case: Any

    def __init__ (self, exp: Expression) -> None:
        super().__init__()
        self.exp = exp
        self.data_cases = []
        self.default_case = NOT_SET

    def When (self, when: ExpOrValue, then: ExpOrValue) -> CaseExpression:
        """Apply `WHEN {when} THEN {then}`
        - Can be applied multiple times"""
        self.data_cases.append((when, then))
        return self

    def Else (self, value: ExpOrValue) -> Expression:
        """Apply `ELSE {value}`
        - Use `.As(alias)` to Select as a Column"""
        self.default_case = value
        return self

    @override
    def to_sql (self, *, table_alias=True):
        if not self.data_cases:
            raise ValueError(f"Expression().Case().When() should be called at least once")

        exp = to_sql(self.exp, table_alias=table_alias)
        sql = DataSQL(
            f"CASE {exp}"
            if self.exp is not E
            else "CASE",
            exp.params
        )

        for when, then in self.data_cases:
            when = to_sql(when, table_alias=table_alias)
            then = to_sql(then, table_alias=table_alias)
            sql.extend(
                f"WHEN {when} THEN {then}",
                [*when, *then],
            )

        if self.default_case is NOT_SET:
            sql.extend(to_sql(self.default_case, table_alias=table_alias))

        return sql

class CastExpression (Expression):

    as_type: str
    exp: Expression

    def __init__ (self, exp: Expression, as_type: str) -> None:
        super().__init__()
        self.exp = exp
        self.as_type = as_type

    @override
    def to_sql (self, *, table_alias=True) -> DataSQL:
        sql = self.exp.to_sql(table_alias=table_alias)
        return DataSQL(
            f"CAST({ sql } AS { self.as_type })",
            sql.params
        )

class NamedFunctionExpression (Expression):

    name: str

    def __init__ (self, name: str, *values: ExpOrValue) -> None:
        super().__init__(*values)
        self.name = name

    @override
    def to_sql (self, *, table_alias=True):
        all_params = []
        sql_parts = list[str]()

        for value in self.values:
            sql = to_sql(value, table_alias=table_alias)
            sql_parts.extend(sql.sqls)
            all_params.extend(sql)

        return DataSQL(f"{self.name}({ ", ".join(sql_parts) })", all_params)

class UnaryExpression (Expression):

    operator: str
    right: ExpOrValue

    def __init__ (self, operator: str, right: ExpOrValue) -> None:
        super().__init__()
        self.right = right
        self.operator = operator

    @override
    def to_sql (self, *, table_alias=True):
        sql = to_sql(self.right, table_alias=table_alias)
        return DataSQL(
            f"{self.operator} ({ sql })"
            if self.operator in OPERATORS_FOR_PARENTESIS
            else f"{self.operator} {sql}",
            sql.params
        )

class BinaryExpression (UnaryExpression):

    left: ExpOrValue

    def __init__ (self, left: ExpOrValue, operator: str, right: ExpOrValue) -> None:
        super().__init__(operator, right)
        self.left = left

    @override
    def to_sql (self, *, table_alias=True):
        left = to_sql(self.left, table_alias=table_alias)
        right = to_sql(self.right, table_alias=table_alias)
        sql = (
            f"({left} {self.operator} {right})"
            if self.operator in OPERATORS_FOR_PARENTESIS
            else f"{left} {self.operator} {right}"
        )
        return DataSQL(sql, [*left, *right])

class SubqueryExpression (Expression):

    left: ExpOrValue | None
    operator: str
    subquery: Queryable

    def __init__ (self, left: ExpOrValue | None, operator: str, subquery: Select | Union) -> None:
        if subquery.collect_ctes():
            raise ValueError("CTEs not supported on Expression.Exists(subquery)")

        super().__init__()
        self.left = left
        self.operator = operator
        self.subquery = subquery

    @override
    def to_sql (self, *, table_alias=True):
        sql_parts, all_params = [], []

        if self.left is not None:
            sql = to_sql(self.left, table_alias=table_alias)
            sql_parts.extend(sql.sqls)
            all_params.extend(sql)

        sql_parts.append(self.operator)

        sql, params = self.subquery.to_sql(render_cte=False, use_parameter=False)
        sql_parts.append(f"(\n{ indent(sql) }\n)")
        all_params.extend(params)

        return DataSQL.from_parts(sql_parts, all_params)

class BetweenExpression (Expression):

    exp:  Expression
    low:  ExpOrValue
    high: ExpOrValue

    def __init__ (self, exp: Expression, low: ExpOrValue, high: ExpOrValue) -> None:
        super().__init__()
        self.exp = exp
        self.low = low
        self.high = high

    @override
    def to_sql (self, *, table_alias=True):
        exp, low, high = (to_sql(x, table_alias=table_alias)
                          for x in (self.exp, self.low, self.high))
        sql = " ".join(( "(", str(exp), "BETWEEN", str(low), "AND", str(high), ")" ))
        return DataSQL(sql, [*exp, *low, *high])

class EmptyExpression (Expression):
    @override    
    def to_sql (self, *, table_alias=True) -> NoReturn:
        raise NotImplementedError("Invalid use of E: EmptyExpression")

E = EmptyExpression()
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

# Avoids Circular Reference
from .select import Select, Union, Queryable

__all__ = [
    "E",
    "to_sql",
    "Expression",
]