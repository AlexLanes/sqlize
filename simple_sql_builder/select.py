# std
from __future__ import annotations
from typing import Self
# internal
from simple_sql_builder.shared     import AliasedColumn, Orderable
from simple_sql_builder.column     import Column
from simple_sql_builder.table      import Table
from simple_sql_builder.expression import Expression
from simple_sql_builder.join       import Join

class Select:
    """Builder of `Select` statement

    ### Example
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

    _table: Table | None
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
        self._table = None
        self.columns = list(columns)
        self._page, self._orders = [], []
        self._joins, self._expression = [], None

    def __repr__ (self) -> str:
        return (
            f"<Select FROM {self._table.to_sql()}>"
            if self._table else 
            "<Select empty>"
        )

    def From (self, table: Table) -> Self:
        """Add `table` to Select `FROM`"""
        self._table = table
        return self

    def to_raw_sql (self) -> str:
        """Complete SQL version"""
        if self._table is None:
            raise ValueError("Table not set on Select.From(Table)")

        select = ", ".join(c.to_sql() for c in self.columns)
        orderby = ", ".join(c.to_sql() for c in self._orders)
        return "\n".join(
            line
            for line in (
                f"SELECT {select}",
                f"FROM {self._table.to_sql()}",
                "\n".join(j.to_sql() for j in self._joins),
                f"WHERE {self._expression.to_sql()}" if self._expression is not None else "",
                f"ORDER BY {orderby}" if orderby else "",
                "\n".join(sql.format(value=value) for _, sql, value in sorted(self._page))
            )
            if line and not line.isspace()
        )

    #-------#
    # JOINS #
    #-------#

    _joins: list[Join]

    def Join (self, table, on: Expression) -> Self:
        """Apply `INNER JOIN {table} ON {on}`
        - `Join(T.orders, T.orders.user_id == T.users.id)`"""
        self._joins.append(
            Join("INNER", table, on)
        )
        return self

    def LeftJoin (self, table, on: Expression) -> Self:
        """Apply `LEFT JOIN {table} ON {on}`
        - `LeftJoin(T.orders, T.orders.user_id == T.users.id)`"""
        self._joins.append(
            Join("LEFT", table, on)
        )
        return self

    def RightJoin (self, table, on: Expression) -> Self:
        """Apply `RIGHT JOIN {table} ON {on}`
        - `RightJoin(T.orders, T.orders.user_id == T.users.id)`"""
        self._joins.append(
            Join("RIGHT", table, on)
        )
        return self

    def FullJoin (self, table, on: Expression) -> Self:
        """Apply `FULL JOIN {table} ON {on}`
        - `FullJoin(T.orders, T.orders.user_id == T.users.id)`"""
        self._joins.append(
            Join("FULL", table, on)
        )
        return self

    #-------#
    # WHERE #
    #-------#

    _expression: Expression | None

    def Where (self, expression: Expression) -> Self:
        """Apply `WHERE {expression}`

        ## Arithmetic `Expressions`
        `+ - * / %`

        ## Comparable `Expressions`
        **Operators** `==` `!=` `>` `<` `>=` `<=`  
        **Methods** `In()` `Like()` `ILike()` `Between()` `Case()`

        ## Logical `Expressions`
        **OR**  `(exp) | (exp)` `exp.Or(exp)`  
        **AND** `(exp) & (exp)` `exp.And(exp)`  
        **NOT** `(exp).Not()`

        ## Functions `Expressions`
        `Upper()` `Lower()` `Length()` `Trim()`   
        `Substring()` `Coalesce()` `Replace()` `Concat()`

        ## Constants `Expression`
        `CURRENT_DATE` `CURRENT_TIME` `CURRENT_TIMESTAMP`  
        `LOCAL_TIME` `LOCAL_TIMESTAMP`

        # Examples
        ```python
        users = T.users
        Where(users.id == 1)
        Where( (users.id % 2 == 0) )
        Where( (users.role == "admin").Not() )
        Where( (users.role == "admin") & (users.name != None) )
        ```
        """
        self._expression = expression
        return self

    #---------#
    # ORDERBY #
    #---------#

    _orders: list[Orderable]

    def OrderBy (self, *o: Orderable) -> Self:
        """Apply `ORDER BY {o}`

        ## Example
        ```python
        Select(T.users.All())
        .From(T.users)
        .OrderBy(
            T.users.id.ASC,
            T.users.name.DESC.NullsFirst,
            (T.users.id % 2).DESC
        )
        ```
        """
        self._orders.extend(o)
        return self

    #------#
    # PAGE #
    #------#

    _page: list[tuple[int, str, int]]
    """`[(order weight, "SQL {value}", value)]`"""

    def Offset (self, value: int | None) -> Self:
        """Apply `OFFSET {value}`
        - `None` do nothing"""
        if value is None:
            return self
        if value < 0:
            raise ValueError(f"Select.Offset({value}) should be >= 0")
        self._page.append((1, "OFFSET {value}", value))
        return self

    def OffsetRows (self, value: int | None) -> Self:
        """Apply `OFFSET {value} ROWS`
        - `None` do nothing"""
        if value is None:
            return self
        if value < 0:
            raise ValueError(f"Select.OffsetRows({value}) should be >= 0")
        self._page.append((1, "OFFSET {value} ROWS", value))
        return self

    def Limit (self, value: int | None) -> Self:
        """Apply `LIMIT {value}`
        - `None` do nothing"""
        if value is None:
            return self
        if value <= 0:
            raise ValueError(f"Select.Limit({value}) should be >= 1")
        self._page.append((2, "LIMIT {value}", value))
        return self

    def FetchNextRowsOnly (self, value: int | None) -> Self:
        """Apply `FETCH NEXT {value} ROWS ONLY`
        - `None` do nothing"""
        if value is None:
            return self
        if value <= 0:
            raise ValueError(f"Select.FetchNextRowsOnly({value}) should be >= 1")
        self._page.append((3, "FETCH NEXT {value} ROWS ONLY", value))
        return self

    def FetchFirstRowsOnly (self, value: int | None) -> Self:
        """Apply `FETCH FRIST {value} ROWS ONLY`
        - `None` do nothing"""
        if value is None:
            return self
        if value <= 0:
            raise ValueError(f"Select.FetchFirstRowsOnly({value}) should be >= 1")
        self._page.append((3, "FETCH FRIST {value} ROWS ONLY", value))
        return self

__all__ = ["Select"]