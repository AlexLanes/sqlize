# std
from typing import Self
from abc import ABC, abstractmethod
# internal
from simple_sql_builder.parameters import *
from simple_sql_builder.shared import SequenceAny, ManySequenceAny, DataSQL
from simple_sql_builder.expression import Expression, OrderableExpression, AliasedExpression
from simple_sql_builder.column import Column, AliasedColumn

class SupportParameter:

    parameter = POSITIONAL_PARAMETERS["?"]
    """Positional Parameter
    - `Default: ?`"""

    def set_parameter (self, positional: Positionals) -> Self:
        """Change `PositionalParameter`
        - `Default: ?`"""
        if p := POSITIONAL_PARAMETERS.get(positional):
            self.parameter = p
            return self

        name = self.__class__.__name__
        raise ValueError(f"Unexpected Positional Parameter for {name}().set_parameter({positional!r})")

class ExecutableStatement (ABC, SupportParameter):
    @abstractmethod
    def to_sql (self) -> tuple[str, SequenceAny | ManySequenceAny]:
        """`SQL: Parameterized` as `(sql, params)`"""
        ...

class SupportsWhere:

    data_where: DataSQL | None

    def __init__ (self) -> None:
        super().__init__()
        self.data_where = None

    def Where (self, expression: Expression) -> Self:
        """Apply `WHERE {expression}`
        #### A `Column` can build `Expression`
        #### See `E` docstring for more info

        # Examples
        `users = T.users`  
        `Where(users.id == 1)`  
        `Where( (users.id % 2 == 0) )`  
        `Where( (users.role == "admin").Not() )`  
        `Where( (users.role == "admin") & (users.name != None) )`  
        """
        sql = expression.to_sql()
        sql.sqls.insert(0, "WHERE")
        self.data_where = sql
        return self

class SupportsOrderBy:

    data_orderby: DataSQL | None

    def __init__ (self) -> None:
        super().__init__()
        self.data_orderby = None

    def OrderBy (self, *orderable: OrderableExpression) -> Self:
        """Apply `ORDER BY {order, ...}`

        ### Example
        ```
        Select(T.users.All())
        .From(T.users)
        .OrderBy(
            T.users.id.ASC,
            T.users.name.DESC.NULLS_FIRST,
            (T.users.id % 2).DESC
        )
        ```
        """
        sqls, params = [], []
        for order in orderable:
            sql = order.to_sql()
            sqls.append(sql.join())
            params.extend(sql)

        self.data_orderby = DataSQL("ORDER BY " + ", ".join(sqls), params)
        return self

class SupportsPaging:

    data_paging: list[tuple[int, str, int]]
    """`[(order weight, "SQL {}", value)]`"""

    def __init__ (self) -> None:
        super().__init__()
        self.data_paging = []

    @property
    def data_paging_sql (self) -> DataSQL | None:
        """`SQLs` version of `LIMITS` and `OFFSETS`
        - `None` if empty"""
        if not self.data_paging:
            return

        sqls, params = [], []
        for _, sql, value in sorted(self.data_paging, key=lambda x: x[0]):
            sqls.append(sql)
            params.append(value)
        return DataSQL("\n".join(sqls), params)

    def Limit (self, value: int | None) -> Self:
        """Apply `LIMIT {value}`
        - `None` do nothing"""
        if value is None:
            return self
        if value <= 0:
            raise ValueError(f"{self.__class__.__name__}().Limit({value}) should be >= 1")
        self.data_paging.append((1, "LIMIT {}", value))
        return self

    def Offset (self, value: int | None) -> Self:
        """Apply `OFFSET {value}`
        - `None` do nothing"""
        if value is None:
            return self
        if value < 0:
            raise ValueError(f"{self.__class__.__name__}().Offset({value}) should be >= 0")
        self.data_paging.append((2, "OFFSET {}", value))
        return self

    def OffsetRows (self, value: int | None) -> Self:
        """Apply `OFFSET {value} ROWS`
        - `None` do nothing"""
        if value is None:
            return self
        if value < 0:
            raise ValueError(f"{self.__class__.__name__}().OffsetRows({value}) should be >= 0")
        self.data_paging.append((2, "OFFSET {} ROWS", value))
        return self

    def FetchNextRowsOnly (self, value: int | None) -> Self:
        """Apply `FETCH NEXT {value} ROWS ONLY`
        - `None` do nothing"""
        if value is None:
            return self
        if value <= 0:
            raise ValueError(f"{self.__class__.__name__}().FetchNextRowsOnly({value}) should be >= 1")
        self.data_paging.append((3, "FETCH NEXT {} ROWS ONLY", value))
        return self

    def FetchFirstRowsOnly (self, value: int | None) -> Self:
        """Apply `FETCH FIRST {value} ROWS ONLY`
        - `None` do nothing"""
        if value is None:
            return self
        if value <= 0:
            raise ValueError(f"{self.__class__.__name__}().FetchFirstRowsOnly({value}) should be >= 1")
        self.data_paging.append((3, "FETCH FIRST {} ROWS ONLY", value))
        return self

class SupportsReturning:

    data_returning: DataSQL | None
    data_output: DataSQL | None

    def __init__ (self) -> None:
        super().__init__()
        self.data_returning = self.data_output = None

    def Returning (self, *value: Column | AliasedColumn | AliasedExpression) -> Self:
        """Apply `RETURNING {Columns}`  
        `.Returning(A.All())`  
        `.Returning(T.users.All())`  
        `.Returning(T.old.name.As("old_name"), T.new.name.As("new_name"))`  
        `.Returning(T.users.id, A.name, A.first_name.Concat(A.last_name).As("full_name"))`"""
        if not value:
            return self

        sqls, params = [], []
        for column in value:
            sql = column.to_sql(table_alias=False)
            sqls.append(sql.join())
            params.extend(sql)

        self.data_returning = DataSQL(
            "RETURNING " + ", ".join(sqls),
            params
        )

        return self

    def Output (self, *value: Column | AliasedExpression) -> Self:
        """Apply `OUTPUT {Columns}`  
        `.Output(T.inserted.All())`  
        `.Output(T.deleted.name.As("old_name"), T.inserted.name.As("new_name"))`"""
        if not value:
            return self

        sqls, params = [], []
        for column in value:
            sql = column.to_sql(table_alias=False)
            sqls.append(sql.join())
            params.extend(sql)

        self.data_output = DataSQL(
            "OUTPUT " + ", ".join(sqls),
            params
        )

        return self

__all__ = [
    "SupportsWhere",
    "SupportsPaging",
    "SupportsOrderBy",
    "SupportParameter",
    "SupportsReturning",
    "ExecutableStatement",
]