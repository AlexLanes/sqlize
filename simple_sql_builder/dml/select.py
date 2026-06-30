# std
from __future__ import annotations
from dataclasses import dataclass, field
from typing import (
    Any, Self, Literal,
    Iterable, override
)
# internal
from simple_sql_builder.shared     import SequenceAny, DataSQL, indent
from simple_sql_builder.expression import Expression, AliasedExpression
from simple_sql_builder.column     import Column, AliasedColumn
from simple_sql_builder.table      import Table
from simple_sql_builder.supports   import *

@dataclass
class SelectData (Data):

    distinct: bool = False
    top: int | None = None
    table: Table | CteTable | None = None 

    columns: list[Column | AliasedExpression] = field(default_factory=list)
    def data_columns (self, table_alias=True) -> DataSQL:
        return DataSQL.merge(
            column.to_sql(table_alias=table_alias, quote_info=self.quote_info)
            for column in self.columns
        )

    joins: list[tuple[
        Literal["INNER", "LEFT", "RIGHT", "FULL"],
        Table | CteTable,
        Expression
    ]] = field(default_factory=list)

    groupby: list[Expression | AliasedColumn] = field(default_factory=list)
    def data_groupby (self) -> DataSQL | None:
        if not self.groupby:
            return

        sql_parts, all_params = [], []
        for exp in self.groupby:
            sql = exp.to_sql(quote_info=self.quote_info)
            sql_parts.append(sql.join())
            all_params.extend(sql)

        return DataSQL(
            "GROUP BY " + ", ".join(sql_parts),
            all_params
        )

    having: list[Expression | AliasedColumn] = field(default_factory=list)
    def data_having (self) -> DataSQL | None:
        if not self.having:
            return

        sql_parts, all_params = [], []
        for exp in self.having:
            sql = exp.to_sql(quote_info=self.quote_info)
            sql_parts.append(sql.join())
            all_params.extend(sql)

        return DataSQL(
            "HAVING " + ", ".join(sql_parts),
            all_params
        )

class CteCollector:
    def collect_ctes (self) -> list[CteTable]:
        return []

class Queryable (ExecutableStatement, SupportsPaging, SupportsOrderBy, CteCollector):

    def __init__ (self) -> None:
        super().__init__()

    @override
    def to_sql (self, *, render_cte=True, use_parameter=True) -> tuple[str, SequenceAny]:
        raise NotImplementedError

class CteTable (Table, CteCollector):

    _q_: Queryable

    def __init__ (self, name: str, q: Queryable) -> None:
        super().__init__(name, "CteTable")
        self._q_ = q

    def __repr__ (self) -> str:
        return f"<CteTable of {self._q_!r}>"

    @override
    def collect_ctes (self) -> list[CteTable]:
        seen = set[str]()
        tables: list[CteTable] = []

        def dfs (cte: CteTable) -> None:
            sql = cte.to_table_sql()
            if sql in seen:
                raise RecursionError(f"CrossReference detected on {cte!r}. Recursion Not Supported")
            seen.add(sql)
            tables.append(cte)
            for child in cte._q_.collect_ctes():
                dfs(child)

        dfs(self)
        return tables

    @override
    def to_table_sql (self) -> str:
        """`SQL: table alias` version"""
        # Removed `CteTable` Schema
        return f"{self._td_.name} {self._td_.alias}"

class Union (Queryable):

    all: bool
    left: Queryable
    right: Queryable

    def __init__ (self, _all: bool, left: Queryable, right: Select) -> None:
        super().__init__()
        self.all = _all
        self.left = left
        self.right = right

    def __repr__ (self) -> str:
        return f"<UNION {"ALL" if self.all else ""}>"

    @override
    def collect_ctes (self) -> list[CteTable]:
        return [
            *self.left.collect_ctes(),
            *self.right.collect_ctes()
        ]

    @override
    def to_sql (self, **kwargs) -> tuple[str, SequenceAny]:
        sql_parts = list[str]()
        all_params = list[Any]()
        parameter = self.data.parameter()
        use_parameter = bool(kwargs.get("use_parameter", True))

        def sql_format (sql: str, params: Iterable[Any]) -> str:
            all_params.extend(params)
            return (
                sql.format(*(parameter.next() for _ in params))
                if use_parameter
                else sql
            )

        render_cte = bool(kwargs.get("render_cte", True))
        union_name = "UNION ALL" if self.all else "UNION"

        for item in (self.left, "", union_name, self.right):
            match item:
                case None: pass
                case str(): sql_parts.append(item)
                case Queryable() as query:
                    sql, params = query.to_sql(render_cte=render_cte, use_parameter=use_parameter)
                    sql_parts.append(sql_format(sql, params))
                case _: raise ValueError(
                    f"Invalid item found on Union: {item!r}"
                )

        spaced = False
        for data in (self.data.data_orderby(), self.data.data_paging()):
            if data is None:
                continue
            spaced = spaced or (sql_parts.append("") is None)
            sql_parts.append(sql_format(data.join(), data))

        return "\n".join(sql_parts), all_params

    def Union (self, select: Select) -> Union:
        """Apply `self UNION {select}`"""
        return Union(False, self, select)

    def UnionAll (self, select: Select) -> Union:
        """Apply `self UNION ALL {select}`"""
        return Union(True, self, select)

    def AsCte (self, name: str) -> CteTable:
        """Transform `Union` into a `CTE` that works as a `Table`"""
        return CteTable(name, self)

class Select (Queryable, SupportsWhere):
    """Builder of `Select` Statement
    - Supports `Unions` and `CTE Tables`

    ## Example
    ```python
    from simple_sql_builder import E, A, T, Select, Connection

    # Select
    users = T.users
    orders = T.orders
    select = (
        Select(
            users.id,
            users.name.Trim().As("user_name"),
            orders.id.As("order_id"),
            (orders.quantity * orders.value).As("total_value"),
            E.LOCAL_TIMESTAMP.As("timestamp")
        )
        .From(users)
        .Join(orders, orders.user_id == users.id)
        .Where( (users.id == 1) | (users.role.Upper() == "ADMIN") )
        .OrderBy(
            users.id.ASC,
            A.user_name.ASC.NULLS_LAST,
            (users.id % 2).DESC
        )
        .Offset(0)
        .Limit(100)
    )

    # CTE + GROUPING
    a = T.actor
    fa = T.film_actor
    cte = (
        Select(
            a.actor_id,
            fa.film_id.Count().As("movies_count")
        )
        .Join(fa, fa.actor_id == a.actor_id)
        .From(a)
        .GroupBy(a.actor_id)
        .Having(fa.film_id.Count() > 30)
        .OrderBy(a.actor_id.ASC)
        .AsCte("cte_movies_count")
    )
    select = (
        Select(A.All())
        .From(cte)
        .OrderBy(cte.actor_id.ASC)
        .Limit(5)
        .Offset(0)
    )

    # Transform
    sql, params = select.to_sql()
    # Execute
    Connection(...).execute(select)
    ```
    """

    data: SelectData

    def __init__ (self, *columns: Column | AliasedExpression) -> None:
        if not columns:
            raise ValueError("No columns informed on Select(). Consider using Select(T.table.All())")

        super().__init__()
        self.data = SelectData() # type: ignore
        self.data.columns.extend(columns)

    def __repr__ (self) -> str:
        d = " DISTINCT " if self.data.distinct else " "
        return (
            f"<SELECT{d}FROM {self.data.table.to_table_sql()}>"
            if self.data.table else 
            f"<SELECT{d}empty>"
        )

    @override
    def collect_ctes (self) -> list[CteTable]:
        return [
            cte
            for table in (self.data.table, *(t for _, t, _ in self.data.joins))
                if isinstance(table, CteTable)
            for cte in table.collect_ctes()
        ]

    @override
    def to_sql (self, **kwargs) -> tuple[str, SequenceAny]:
        if self.data.table is None:
            raise ValueError("Table not set on Select().From(Table)")

        all_params = list[Any]()
        parameter = self.data.parameter()
        use_parameter = bool(kwargs.get("use_parameter", True))

        def sql_format (sql: str, params: Iterable[Any]) -> str:
            return (
                sql.format(*(parameter.next() for _ in params))
                if use_parameter
                else sql
            )

        # SELECT DISTINCT TOP
        sql_parts = ["SELECT"]
        if self.data.distinct:
            sql_parts.append("DISTINCT")
        if top := self.data.top:
            all_params.append(top)
            sql_parts.append(sql_format("TOP ({})", [top]))

        # COLUMNS FROM
        columns = self.data.data_columns()
        all_params.extend(columns)
        sql_parts.append(sql_format(columns.join(", "), columns))
        sql_parts = [
            " ".join(sql_parts),
            f"FROM { self.data.table.to_table_sql() }"
        ]

        # JOINS
        for name, table, expression in self.data.joins:
            data = expression.to_sql(quote_info=self.data.quote_info)
            all_params.extend(data)
            sql = sql_format(data.join(), data)
            sql_parts.append(f"{name} JOIN {table.to_table_sql()} ON {sql}")

        # WHERE GROUPBY HAVING ORDERBY PAGING
        for data in (self.data.data_where(), self.data.data_groupby(),
                     self.data.data_having(), self.data.data_orderby(),
                     self.data.data_paging()):
            if data is None: continue
            all_params.extend(data)
            sql_parts.append(sql_format(data.join(), data))

        # No CTE Table
        cte_tables = self.collect_ctes()
        render_cte = bool(kwargs.get("render_cte", True))
        if not render_cte or not cte_tables:
            return "\n".join(sql_parts), all_params

        # CTE Table
        cte_tables.reverse()
        last = cte_tables[-1]
        cte_parts, cte_params = ["WITH"], []

        for cte in cte_tables:
            sql, params = cte._q_.to_sql(render_cte=False, use_parameter=False)
            cte_params.extend(params)
            cte_parts.extend((
                f"{cte._td_.name} AS (",
                sql_format(indent(sql), params),
                ")" if cte is last else "),"
            ))

        cte_params.extend(all_params)
        return "\n".join(
            line
            for lines in (cte_parts, sql_parts)
            for line in lines
        ), cte_params

    def Distinct (self) -> Self:
        """Apply `SELECT DISTINCT`"""
        self.data.distinct = True
        return self

    def Top (self, rows: int | None) -> Self:
        """Apply `TOP {rows}`
        - `None` do nothing"""
        if rows is None:
            return self
        if rows <= 0:
            raise ValueError(f"Select().Top({ rows }) should be >= 1")
        self.data.top = rows
        return self

    def From (self, table: Table | CteTable) -> Self:
        """Add `table` to Select `FROM`"""
        self.data.table = table
        return self

    def AsCte (self, name: str) -> CteTable:
        """Transform `Select` into a `CTE` that works as a `Table`"""
        if self.data.table is None:
            raise ValueError("Table not set on Select().From(Table)")
        return CteTable(name, self)

    #-------#
    # JOINS #
    #-------#

    def Join (self, table: Table | CteTable, on: Expression) -> Self:
        """Apply `INNER JOIN {table} ON {on}`
        - `Join(T.orders, T.orders.user_id == T.users.id)`"""
        self.data.joins.append(("INNER", table, on))
        return self

    def LeftJoin (self, table: Table | CteTable, on: Expression) -> Self:
        """Apply `LEFT JOIN {table} ON {on}`
        - `LeftJoin(T.orders, T.orders.user_id == T.users.id)`"""
        self.data.joins.append(("LEFT", table, on))
        return self

    def RightJoin (self, table: Table | CteTable, on: Expression) -> Self:
        """Apply `RIGHT JOIN {table} ON {on}`
        - `RightJoin(T.orders, T.orders.user_id == T.users.id)`"""
        self.data.joins.append(("RIGHT", table, on))
        return self

    def FullJoin (self, table: Table | CteTable, on: Expression) -> Self:
        """Apply `FULL JOIN {table} ON {on}`
        - `FullJoin(T.orders, T.orders.user_id == T.users.id)`"""
        self.data.joins.append(("FULL", table, on))
        return self

    #----------#
    # GROUPING #
    #----------#

    def GroupBy (self, *expression: Expression | AliasedColumn) -> Self:
        """Apply `GROUP BY {expression, ...}`"""
        self.data.groupby.extend(expression)
        return self

    def Having (self, *expression: Expression | AliasedColumn) -> Self:
        """Apply `HAVING {expression, ...}`"""
        self.data.having.extend(expression)
        return self

    #--------#
    # UNIONS #
    #--------#

    def Union (self, select: Select) -> Union:
        """Apply `self UNION {select}`

        ## Example
        ```
        Select(T.actor.actor_id.As("id"), T.actor.first_name, E.Value("actor").As("type"))
        .From(T.actor)
        .Union(
            Select(T.customer.customer_id.As("id"), T.customer.first_name, E.Value("customer").As("type"))
            .From(T.customer)
        )
        .Union(
            Select(T.staff.staff_id.As("id"), T.staff.first_name.As("nome"), E.Value("staff").As("type"))
            .From(T.staff)
        )
        .OrderBy(A.id.ASC, A.type.ASC)
        .Limit(3)
        ```
        """
        return Union(False, self, select)

    def UnionAll (self, select: Select) -> Union:
        """Apply `self UNION ALL {select}`

        ## Example
        ```
        Select(T.actor.actor_id.As("id"), T.actor.first_name, E.Value("actor").As("type"))
        .From(T.actor)
        .Union(
            Select(T.customer.customer_id.As("id"), T.customer.first_name, E.Value("customer").As("type"))
            .From(T.customer)
        )
        .Union(
            Select(T.staff.staff_id.As("id"), T.staff.first_name.As("nome"), E.Value("staff").As("type"))
            .From(T.staff)
        )
        .OrderBy(A.id.ASC, A.type.ASC)
        .Limit(3)
        ```
        """
        return Union(True, self, select)

__all__ = ["Select"]