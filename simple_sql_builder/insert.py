# std
from __future__ import annotations
from typing import Self, override
# internal
from .shared import quote, ManySequenceAny, SequenceAny
from .column import ColumnWithValue, ColumnWithDefaultValue
from .table import Table
from .supports import SupportsReturning, StatementWithParameter

class InsertDefaultValues (StatementWithParameter, SupportsReturning):

    into: Table

    def __init__ (self, into: Table) -> None:
        super().__init__()
        self.into = into

    def __repr__ (self) -> str:
        return f"<INSERT INTO {self.into.to_table_name()!r} DEFAULT VALUES>"

    @override
    def to_sql (self) -> tuple[str, SequenceAny]:
        return "\n".join(
            line
            for line in (
                f"INSERT INTO {self.into.to_table_name()}",
                "DEFAULT VALUES",
                self.data_returning_sql
            )
            if line
        ), []

class InsertOne (StatementWithParameter, SupportsReturning):
    """Builder of `Insert` Statement

    ## Example
    ```python
    actor = T.actor
    insert = (
        InsertOne(into=actor)
        .Values(
            actor.first_name.Value("Alex"),
            actor.last_name.Value("Lanes"),
            actor.last_update.DEFAULT_VALUE
        )
        .Returning(actor.All())
    )
    sql, params = insert.to_sql()

    insert = (
        InsertOne(into=actor)
        .DefaultValues()
        .Returning(actor.All())
    )
    sql, _ = insert.to_sql()
    ```
    """

    into: Table
    data_values: list[ColumnWithValue | ColumnWithDefaultValue]

    def __init__ (self, into: Table) -> None:
        super().__init__()
        self.into = into
        self.data_values = []

    def __repr__ (self) -> str:
        return f"<INSERT INTO {self.into.to_table_name()!r} 1 ROW>"

    @property
    def as_positional_sql (self) -> str:
        """Positional Parameterized `SQL: INSERT INTO {table} ({columns}) VALUES ({values}) [RETURNING {columns}]` version"""
        if not self.data_values:
            raise ValueError("InsertOne().Values() should be called first")

        positional = self.parameter()
        columns = ", ".join(quote(c.column.name) for c in self.data_values)
        parameters = ", ".join(
            positional.next()
            if isinstance(column, ColumnWithValue)
            else column.to_sql()
            for column in self.data_values
        )

        return "\n".join(
            line
            for line in (
                f"INSERT INTO {self.into.to_table_name()}",
                f"({ columns })",
                f"VALUES ({ parameters })",
                self.data_returning_sql
            )
            if line
        )

    @override
    def to_sql (self) -> tuple[str, SequenceAny]:
        """Positional Parameterized `(sql, (values, ...))`"""
        return (
            self.as_positional_sql,
            tuple(
                column.value
                for column in self.data_values
                if isinstance(column, ColumnWithValue)
            )
        )

    def Values (self, *values: ColumnWithValue | ColumnWithDefaultValue) -> Self:
        """Apply `VALUES ({values})`  
        `.Values(T.users.id.Value(1), T.users.name.Value("Bar"))`  
        `.Values(T.users.name.Value("Foo"), T.users.id.DEFAULT_VALUE)`"""
        if not values:
            raise ValueError("At least one value is required on InsertOne().Values()")
        if self.data_values:
            raise ValueError("InsertOne().Values() should be called once")

        self.data_values.extend(values)
        return self

    def DefaultValues (self) -> InsertDefaultValues:
        """Apply `DEFAULT VALUES`"""
        return InsertDefaultValues(self.into)

class InsertMany (StatementWithParameter, SupportsReturning):
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

    @property
    def as_positional_sql (self) -> str:
        """Positional Parameterized `SQL: INSERT INTO {table} ({columns}) VALUES ({values}) [RETURNING {columns}]` version"""
        if not self.data_values:
            raise ValueError("InsertMany().Values() should be called first")

        positional = self.parameter()
        columns = ", ".join(quote(v.column.name) for v in self.data_values[0])
        parameters = ", ".join(positional.next() for _ in self.data_values[0])

        return "\n".join(
            line
            for line in (
                f"INSERT INTO {self.into.to_table_name()}",
                f"({ columns })",
                f"VALUES ({ parameters })",
                self.data_returning_sql
            )
            if line
        )

    @override
    def to_sql (self) -> tuple[str, ManySequenceAny]:
        """Positional Parameterized `(sql, [(values), ...])`"""
        return (
            self.as_positional_sql,
            [
                tuple(c.value for c in columns)
                for columns in self.data_values
            ]
        )

    def Values (self, *value: ColumnWithValue) -> Self:
        """Apply `VALUES ({values})`  
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