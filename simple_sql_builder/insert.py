# std
from __future__ import annotations
from typing import Self, override
# internal
from .shared import ManySequenceAny, SequenceAny
from .expression import AliasedExpression, to_sql
from .column import ColumnWithValue, ColumnWithDefaultValue
from .table import Table
from .supports import SupportsReturning, ExecutableStatement

class InsertDefaultValues (ExecutableStatement, SupportsReturning):

    into: Table

    def __init__ (self, into: Table) -> None:
        super().__init__()
        self.into = into

    def __repr__ (self) -> str:
        return f"<INSERT INTO {self.into.to_table_name()!r} DEFAULT VALUES>"

    @override
    def to_sql (self) -> tuple[str, SequenceAny]:
        positional = self.parameter()
        params, sqls = [], [
            f"INSERT INTO {self.into.to_table_name()}",
            "DEFAULT VALUES"
        ]

        if self.data_returning is not None:
            parameters = (positional.next() for _ in self.data_returning)
            sqls.append(self.data_returning.join().format(*parameters))
            params.extend(self.data_returning)

        return "\n".join(sqls), params

class InsertOne (ExecutableStatement, SupportsReturning):
    """Builder of `Insert` Statement

    ## Example
    ```python
    actor = T.actor
    insert = (
        InsertOne(into=actor)
        .Values(
            actor.actor_id.DEFAULT_VALUE,
            actor.first_name.Value("Alex"),
            E.Value(" Lanes ").Trim().As("last_name"),
            E.CURRENT_TIMESTAMP.As("last_update")
        )
        .Returning(actor.All())
    )
    sql, params = insert.to_sql()

    insert = (
        InsertOne(into=actor)
        .DefaultValues()
        .Returning(actor.All())
    )
    sql, params = insert.to_sql()
    ```
    """

    into: Table
    data_values: list[ColumnWithValue | ColumnWithDefaultValue | AliasedExpression]

    def __init__ (self, into: Table) -> None:
        super().__init__()
        self.into = into
        self.data_values = []

    def __repr__ (self) -> str:
        return f"<INSERT INTO {self.into.to_table_name()!r} 1 ROW>"

    @override
    def to_sql (self) -> tuple[str, SequenceAny]:
        """Positional Parameterized `SQL: INSERT INTO {table} ({ columns }) VALUES ({ values }) [RETURNING {columns}]` version
        - As `(sql, params)`"""
        if not self.data_values:
            raise ValueError("InsertOne().Values() should be called first")

        params = []
        columns, values = [], []
        positional = self.parameter()
        for value in self.data_values:
            match value:

                case ColumnWithValue():
                    columns.append(value.column.name)
                    values.append(positional.next())
                    params.extend(value.values)

                case ColumnWithDefaultValue():
                    columns.append(value.column.name)
                    values.append(value.to_sql().join())

                case AliasedExpression():
                    columns.append(value.alias)
                    sql = to_sql(value.expression, table_alias=False)
                    parameters = (positional.next() for _ in sql)
                    values.append(sql.join().format(*parameters))
                    params.extend(sql)

                case _: raise TypeError(f"Invalid value found on InsertOne.Values({value!r})")

        parts = [
            f"INSERT INTO {self.into.to_table_name()}",
            f"({ ", ".join(columns) })",
            f"VALUES ({ ", ".join(values) })",
        ]

        if self.data_returning is not None:
            parameters = (positional.next() for _ in self.data_returning)
            parts.append(self.data_returning.join().format(*parameters))
            params.extend(self.data_returning)

        return "\n".join(parts), params

    def Values (self, *values: ColumnWithValue | ColumnWithDefaultValue | AliasedExpression) -> Self:
        """Apply `VALUES ({ values })`  
        `.Values(T.users.id.DEFAULT_VALUE, T.users.name.Value("Bar"), E.CURRENT_TIMESTAMP.As("last_update"))`"""
        if not values:
            raise ValueError("At least one value is required on InsertOne().Values()")
        if self.data_values:
            raise ValueError("InsertOne().Values() should be called once")

        self.data_values.extend(values)
        return self

    def DefaultValues (self) -> InsertDefaultValues:
        """Apply `DEFAULT VALUES`"""
        return InsertDefaultValues(self.into)

class InsertMany (ExecutableStatement, SupportsReturning):
    """Builder of `Insert` Statement with multiple values

    ## Example
    ```python
    actor = T.actor
    insert = (
        InsertMany(into=actor)
        .Values(actor.first_name.Value("Alex"), actor.last_name.Value("Lanes"))
        .Values(actor.last_name.Value("Foo"), actor.first_name.Value("Bar"))
        .Returning(actor.All())
    )
    sql, params = insert.to_sql()
    ```
    """

    into: Table
    data_values: list[list[ColumnWithValue]]

    def __init__ (self, into: Table) -> None:
        super().__init__()
        self.into = into
        self.data_values = []

    def __repr__ (self) -> str:
        return f"<INSERT INTO {self.into.to_table_name()!r} {len(self.data_values)} ROW(S)>"

    @override
    def to_sql (self) -> tuple[str, ManySequenceAny]:
        """Positional Parameterized `SQL: INSERT INTO {table} ({ columns }) VALUES ({ values }) [RETURNING {columns}]` version
        - As `(sql, params)`"""
        if not self.data_values:
            raise ValueError("InsertMany().Values() should be called first")

        first = self.data_values[0]
        positional = self.parameter()
        parts = [
            f"INSERT INTO {self.into.to_table_name()}",
            f"({ ", ".join(v.column.name for v in first) })",
            f"VALUES ({ ", ".join(positional.next() for _ in first) })",
        ]

        params = []
        if self.data_returning is not None:
            parameters = (positional.next() for _ in self.data_returning)
            parts.append(self.data_returning.join().format(*parameters))
            params.extend(self.data_returning)

        return (
            "\n".join(parts),
            [
                tuple(
                    value
                    for column in columns
                    for value in [*column.values, *params]
                )
                for columns in self.data_values
            ]
        )

    def Values (self, *value: ColumnWithValue) -> Self:
        """Apply `VALUES ({ values })`  
        `.Values(T.users.id.Value(1), T.users.name.Value("Bar"))`  
        `.Values(T.users.name.Value("Foo"), T.users.id.Value(2))`"""
        if not value:
            raise ValueError("At least one value is required on InsertMany().Values()")

        ordered = sorted(value, key=lambda v: v.column.name)
        columns = [c.column.name for c in ordered]

        match self.data_values:
            case []:
                if len(columns) != len(set(columns)):
                    raise ValueError(
                        f"Duplicate names found on InsertMany().Values(): {columns}"
                    )

            case [first, *_]:
                expected = [v.column.name for v in first]
                if expected != columns:
                    raise ValueError(
                        "All InsertMany().Values() rows must have the same columns names;"
                        f" Columns {columns};"
                        f" Expected {expected}"
                    )

        self.data_values.append(ordered)
        return self

__all__ = ["InsertOne", "InsertMany"]