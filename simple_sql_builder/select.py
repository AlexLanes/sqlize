# std
from __future__ import annotations
from typing import Self, Literal, override
# internal
from simple_sql_builder.shared     import AliasedColumn, OrderableExpression
from simple_sql_builder.connection import Connection, ResultSQL
from simple_sql_builder.expression import Expression
from simple_sql_builder.column     import Column
from simple_sql_builder.table      import Table

type JOINS = Literal["INNER", "LEFT", "RIGHT", "FULL"]

class Pageable:

    _paging: list[tuple[int, str, int]]
    """`[(order weight, "SQL {value}", value)]`"""

    def __init__ (self) -> None:
        self._paging = []
        super().__init__()

    def Limit (self, value: int | None) -> Self:
        """Apply `LIMIT {value}`
        - `None` do nothing"""
        if value is None:
            return self
        if value <= 0:
            raise ValueError(f"Select.Limit({value}) should be >= 1")
        self._paging.append((1, "LIMIT {value}", value))
        return self

    def Offset (self, value: int | None) -> Self:
        """Apply `OFFSET {value}`
        - `None` do nothing"""
        if value is None:
            return self
        if value < 0:
            raise ValueError(f"Select.Offset({value}) should be >= 0")
        self._paging.append((2, "OFFSET {value}", value))
        return self

    def OffsetRows (self, value: int | None) -> Self:
        """Apply `OFFSET {value} ROWS`
        - `None` do nothing"""
        if value is None:
            return self
        if value < 0:
            raise ValueError(f"Select.OffsetRows({value}) should be >= 0")
        self._paging.append((2, "OFFSET {value} ROWS", value))
        return self

    def FetchNextRowsOnly (self, value: int | None) -> Self:
        """Apply `FETCH NEXT {value} ROWS ONLY`
        - `None` do nothing"""
        if value is None:
            return self
        if value <= 0:
            raise ValueError(f"Select.FetchNextRowsOnly({value}) should be >= 1")
        self._paging.append((3, "FETCH NEXT {value} ROWS ONLY", value))
        return self

    def FetchFirstRowsOnly (self, value: int | None) -> Self:
        """Apply `FETCH FRIST {value} ROWS ONLY`
        - `None` do nothing"""
        if value is None:
            return self
        if value <= 0:
            raise ValueError(f"Select.FetchFirstRowsOnly({value}) should be >= 1")
        self._paging.append((3, "FETCH FRIST {value} ROWS ONLY", value))
        return self

class Orderable:

    _orders: list[OrderableExpression]

    def __init__ (self) -> None:
        self._orders = []
        super().__init__()

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
        self._orders.extend(order)
        return self

class CteCollector:
    def collect_ctes (self) -> list[CteTable]:
        return []

class Queryable (Pageable, Orderable, CteCollector):

    @property
    def as_sql (self) -> str:
        """`SQL: SELECT` version"""
        raise NotImplementedError

    def to_raw_sql (self) -> str:
        """Complete `SQL: SELECT` version"""
        return self.as_sql

    def execute (self, connection: Connection) -> ResultSQL:
        """Execute `Select` Statement for `Connection`"""
        return (
            connection
            .cursor()
            .execute(self.to_raw_sql()) # TODO
        )

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
    right: Select

    def __init__ (self, _all: bool, left: Queryable, right: Select) -> None:
        self.all = _all
        self.left = left
        self.right = right
        super().__init__()

    def __repr__ (self) -> str:
        return f"<Union {"ALL" if self.all else ""}>"

    @property
    @override
    def as_sql (self) -> str:
        union_name = "UNION ALL" if self.all else "UNION"
        orderby = ", ".join(o.to_sql() for o in self._orders)
        paging_gen = (
            sql.format(value=value)
            for _, sql, value in sorted(self._paging)
        )

        return "\n".join(
            part
            for part in (
                self.left.to_raw_sql(),
                union_name,
                self.right.to_raw_sql(),
                " ",
                f"ORDER BY {orderby}" if orderby else None,
                *paging_gen
            )
            if part
        ).rstrip()

    @override
    def collect_ctes (self) -> list[CteTable]:
        return [
            *self.left.collect_ctes(),
            *self.right.collect_ctes()
        ]

    def Union (self, select: Select) -> Union:
        """Apply `self UNION {select}`"""
        return Union(False, self, select)

    def UnionAll (self, select: Select) -> Union:
        """Apply `self UNION ALL {select}`"""
        return Union(True, self, select)

    def AsCte (self, name: str) -> CteTable:
        """Transform `Union` into a `CTE` that works as a `Table`"""
        return CteTable(name, self)

class Select (Queryable):
    """Builder of `Select` statement

    # Example
    ```python
    from simple_sql_builder import T, Select

    users = T.users
    orders = T.orders
    print(
        Select(
            users.id,
            users.name,
            orders.id.As("order_id"),
            (orders.quantity * orders.value).As("total_value")
        )
        .From(users)
        .Join(T.orders, orders.user_id == users.id)
        .Where( (users.id == 1) | (users.role.Upper() == "ADMIN") )
        .OrderBy(
            users.id.ASC,
            T.users.name.ASC.NullsLast,
            (T.users.id % 2).DESC
        )
        .Offset(0)
        .Limit(100)

        # Transform
        .to_raw_sql()
    )
    ```
    """

    distinct: bool
    table: Table | CteTable | None
    columns: list[Column | AliasedColumn]

    def __init__ (self, *columns: Column | AliasedColumn) -> None:
        """`Columns` to Select

        ### Example
        ```python
        Select(
            T.users.id,
            T.users.name,
            T.orders.id.As("order_id"),
            (T.orders.quantity * T.orders.value).As("total_value")
        )
        ```
        """
        if not columns:
            raise ValueError("No columns informed on Select(). Consider using Select(T.table.All())")

        self.table = None
        self.distinct = False
        self.columns = list(columns)

        self._joins = []
        self._expression = None
        self._groups = ([], [])
        super().__init__()

    def __repr__ (self) -> str:
        d = " DISTINCT " if self.distinct else " "
        return (
            f"<Select{d}FROM {self.table.to_table_sql()}>"
            if self.table else 
            f"<Select{d}empty>"
        )

    @property
    @override
    def as_sql (self) -> str:
        if self.table is None:
            raise ValueError("Table not set on Select.From(Table)")

        select  = "SELECT DISTINCT" if self.distinct else "SELECT"
        columns = ", ".join(c.to_sql() for c in self.columns)
        orderby = ", ".join(o.to_sql() for o in self._orders)
        joins_gen = (
            f"{name} JOIN {table.to_table_sql()} ON {exp.to_sql()}"
            for name, table, exp in self._joins
        )
        paging_gen = (
            sql.format(value=value)
            for _, sql, value in sorted(self._paging)
        )
        groupby, having = (
            ", ".join(
                exp.to_sql() if isinstance(exp, Expression) else exp.alias
                for exp in item
            )
            for item in self._groups
        )
        return "\n".join(
            line
            for line in (
                f"{select} {columns}",
                f"FROM {self.table.to_table_sql()}",
                *joins_gen,
                f"WHERE {self._expression.to_sql()}" if self._expression is not None else "",
                f"GROUP BY {groupby}" if groupby else "",
                f"HAVING {having}"    if having  else "",
                f"ORDER BY {orderby}" if orderby else "",
                *paging_gen,
            )
            if line and not line.isspace()
        )

    @override
    def to_raw_sql (self) -> str:
        if self.table is None:
            raise ValueError("Table not set on Select.From(Table)")

        ctes = [cte
                for table in (self.table, *(t for _, t, _ in self._joins))
                    if isinstance(table, CteTable)
                for cte in table.collect_ctes()]
        if not ctes:
            return self.as_sql

        cte_sql = ",\n".join(
            "\n".join((
                f"{cte._td_.name} AS (",
                *(f"    {line}" for line in cte._q_.as_sql.split("\n")),
                ")"
            ))
            for cte in ctes
        )
        return f"""WITH {cte_sql}\n{self.as_sql}"""

    @override
    def collect_ctes (self) -> list[CteTable]:
        return (
            self.table.collect_ctes()
            if isinstance(self.table, CteTable)
            else []
        )

    def Distinct (self) -> Self:
        """Apply `SELECT DISTINCT`"""
        self.distinct = True
        return self

    def From (self, table: Table | CteTable) -> Self:
        """Add `table` to Select `FROM`"""
        self.table = table
        return self

    def AsCte (self, name: str) -> CteTable:
        """Transform `Select` into a `CTE` that works as a `Table`"""
        if self.table is None:
            raise ValueError("Table not set on Select.From(Table)")
        return CteTable(name, self)

    #-------#
    # JOINS #
    #-------#

    _joins: list[tuple[JOINS, Table | CteTable, Expression]]

    def Join (self, table: Table | CteTable, on: Expression) -> Self:
        """Apply `INNER JOIN {table} ON {on}`
        - `Join(T.orders, T.orders.user_id == T.users.id)`"""
        self._joins.append(
            ("INNER", table, on)
        )
        return self

    def LeftJoin (self, table: Table | CteTable, on: Expression) -> Self:
        """Apply `LEFT JOIN {table} ON {on}`
        - `LeftJoin(T.orders, T.orders.user_id == T.users.id)`"""
        self._joins.append(
            ("LEFT", table, on)
        )
        return self

    def RightJoin (self, table: Table | CteTable, on: Expression) -> Self:
        """Apply `RIGHT JOIN {table} ON {on}`
        - `RightJoin(T.orders, T.orders.user_id == T.users.id)`"""
        self._joins.append(
            ("RIGHT", table, on)
        )
        return self

    def FullJoin (self, table: Table | CteTable, on: Expression) -> Self:
        """Apply `FULL JOIN {table} ON {on}`
        - `FullJoin(T.orders, T.orders.user_id == T.users.id)`"""
        self._joins.append(
            ("FULL", table, on)
        )
        return self

    #-------#
    # WHERE #
    #-------#

    _expression: Expression | None

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
        self._expression = expression
        return self

    #----------#
    # GROUPING #
    #----------#

    _groups: tuple[list[Expression | AliasedColumn], list[Expression | AliasedColumn]]

    def GroupBy (self, *expression: Expression | AliasedColumn) -> Self:
        """Apply `GROUP BY {expression, ...}`"""
        self._groups[0].extend(expression)
        return self

    def Having (self, *expression: Expression | AliasedColumn) -> Self:
        """Apply `HAVING {expression, ...}`"""
        self._groups[1].extend(expression)
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