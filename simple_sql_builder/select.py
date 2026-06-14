# std
from __future__ import annotations
from typing import Self, Literal
# internal
from simple_sql_builder.shared     import AliasedColumn, OrderableExpression
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

    def Offset (self, value: int | None) -> Self:
        """Apply `OFFSET {value}`
        - `None` do nothing"""
        if value is None:
            return self
        if value < 0:
            raise ValueError(f"Select.Offset({value}) should be >= 0")
        self._paging.append((1, "OFFSET {value}", value))
        return self

    def OffsetRows (self, value: int | None) -> Self:
        """Apply `OFFSET {value} ROWS`
        - `None` do nothing"""
        if value is None:
            return self
        if value < 0:
            raise ValueError(f"Select.OffsetRows({value}) should be >= 0")
        self._paging.append((1, "OFFSET {value} ROWS", value))
        return self

    def Limit (self, value: int | None) -> Self:
        """Apply `LIMIT {value}`
        - `None` do nothing"""
        if value is None:
            return self
        if value <= 0:
            raise ValueError(f"Select.Limit({value}) should be >= 1")
        self._paging.append((2, "LIMIT {value}", value))
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

class Union (Pageable, Orderable):

    all: bool
    left: Select
    right: Select

    def __init__ (self, _all: bool, left: Select, right: Select) -> None:
        self.all = _all
        self.left = left
        self.right = right
        super().__init__()

    def to_raw_sql (self) -> str:
        """Complete SQL version"""
        name = "UNION ALL" if self.all else "UNION"
        orderby = ", ".join(o.to_sql() for o in self._orders)
        paging_gen = (
            sql.format(value=value)
            for _, sql, value in sorted(self._paging)
        )

        left, right = map(lambda s: s.to_raw_sql(), (self.left, self.right))
        if not orderby and not self._paging:
            return f"{left}\n\n{name}\n\n{right}"

        left_gen  = (f"    {line}" for line in left.split("\n"))
        right_gen = (f"    {line}" for line in right.split("\n"))
        return "\n".join(
            part
            for part in (
                "(",
                    *left_gen,
                ")",
                name,
                "(",
                    *right_gen,
                ")",
                f"ORDER BY {orderby}" if orderby else None,
                *paging_gen
            )
            if part
        )

class Select (Pageable, Orderable):
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
    table: Table | None
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

        self.__joins = []
        self.__expression = None
        self.__groups = ([], [])
        super().__init__()

    def __repr__ (self) -> str:
        d = " DISTINCT " if self.distinct else " "
        return (
            f"<Select{d}FROM {self.table.to_sql()}>"
            if self.table else 
            f"<Select{d}empty>"
        )

    def Distinct (self) -> Self:
        """Apply `SELECT DISTINCT`"""
        self.distinct = True
        return self

    def From (self, table: Table) -> Self:
        """Add `table` to Select `FROM`"""
        self.table = table
        return self

    def to_raw_sql (self) -> str:
        """Complete SQL version"""
        if self.table is None:
            raise ValueError("Table not set on Select.From(Table)")

        select  = "SELECT DISTINCT" if self.distinct else "SELECT"
        columns = ", ".join(c.to_sql() for c in self.columns)
        orderby = ", ".join(o.to_sql() for o in self._orders)
        groupby, having = (
            ", ".join(
                exp.to_sql() if isinstance(exp, Expression) else exp.alias
                for exp in item
            )
            for item in self.__groups
        )

        return "\n".join(
            line
            for line in (
                f"{select} {columns}",
                f"FROM {self.table.to_sql()}",

                "\n".join(
                    f"{name} JOIN {table.to_sql()} ON {exp.to_sql()}"
                    for name, table, exp in self.__joins
                ),

                f"WHERE {self.__expression.to_sql()}" if self.__expression is not None else "",
                f"GROUP BY {groupby}" if groupby else "",
                f"HAVING {having}"    if having  else "",
                f"ORDER BY {orderby}" if orderby else "",
\
                "\n".join(
                    sql.format(value=value)
                    for _, sql, value in sorted(self._paging)
                )
            )
            if line and not line.isspace()
        )

    #-------#
    # JOINS #
    #-------#

    __joins: list[tuple[JOINS, Table, Expression]]

    def Join (self, table, on: Expression) -> Self:
        """Apply `INNER JOIN {table} ON {on}`
        - `Join(T.orders, T.orders.user_id == T.users.id)`"""
        self.__joins.append(
            ("INNER", table, on)
        )
        return self

    def LeftJoin (self, table, on: Expression) -> Self:
        """Apply `LEFT JOIN {table} ON {on}`
        - `LeftJoin(T.orders, T.orders.user_id == T.users.id)`"""
        self.__joins.append(
            ("LEFT", table, on)
        )
        return self

    def RightJoin (self, table, on: Expression) -> Self:
        """Apply `RIGHT JOIN {table} ON {on}`
        - `RightJoin(T.orders, T.orders.user_id == T.users.id)`"""
        self.__joins.append(
            ("RIGHT", table, on)
        )
        return self

    def FullJoin (self, table, on: Expression) -> Self:
        """Apply `FULL JOIN {table} ON {on}`
        - `FullJoin(T.orders, T.orders.user_id == T.users.id)`"""
        self.__joins.append(
            ("FULL", table, on)
        )
        return self

    #-------#
    # WHERE #
    #-------#

    __expression: Expression | None

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
        self.__expression = expression
        return self

    #----------#
    # GROUPING #
    #----------#

    __groups: tuple[list[Expression | AliasedColumn], list[Expression | AliasedColumn]]

    def GroupBy (self, *expression: Expression | AliasedColumn) -> Self:
        """Apply `GROUP BY {expression, ...}`"""
        self.__groups[0].extend(expression)
        return self

    def Having (self, *expression: Expression | AliasedColumn) -> Self:
        """Apply `HAVING {expression, ...}`"""
        self.__groups[1].extend(expression)
        return self

    #--------#
    # UNIONS #
    #--------#

    def Union (self, select: Select) -> Union:
        """Apply `(self) UNION ({select})`

        ## Example
        ```
        Select(actor.actor_id.As("id"), actor.first_name, E.Value("actor").As("type"))
        .From(actor)
        .Union(
            Select(customer.customer_id.As("id"), customer.first_name, E.Value("customer").As("type"))
            .From(customer)
        )
        .OrderBy(A.id.ASC, A.type.ASC)
        .Limit(2)
        ```
        """
        return Union(False, self, select)

    def UnionAll (self, select: Select) -> Union:
        """Apply `(self) UNION ALL ({select})`

        ## Example
        ```
        Select(actor.actor_id.As("id"), actor.first_name, E.Value("actor").As("type"))
        .From(actor)
        .UnionAll(
            Select(customer.customer_id.As("id"), customer.first_name, E.Value("customer").As("type"))
            .From(customer)
        )
        .OrderBy(A.id.ASC, A.type.ASC)
        .Limit(2)
        ```
        """
        return Union(True, self, select)

__all__ = ["Select"]