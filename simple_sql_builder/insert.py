# std
from __future__ import annotations
from typing import Self, override
# internal
from .shared import quote, ManySequenceAny, SequenceAny
from .connection import Connection, ResultSQL
from .expression import to_sql_str
from .column import Column, ColumnWithValue, ColumnWithDefaultValue
from .table import Table
from .parameters import *
from .supports import SupportsReturning, SupportsExecute

class InsertDefaultValues (SupportsExecute, SupportsReturning):
    def __init__ (self, into: Table) -> None:
        super().__init__()
        self.into = into

    @override
    def to_raw_sql (self) -> str:
        """Raw `SQL: INSERT INTO {table} DEFAULT VALUES [RETURNING {columns}]` version"""
        returning = ", ".join(
            column.name if isinstance(column, Column) else column.alias
            for column in self.data_returning
        )

        return "\n".join(
            line
            for line in (
                f"INSERT INTO {self.into.to_table_name()}",
                "DEFAULT VALUES",
                f"RETURNING {returning}" if returning else None
            )
            if line
        )

class InsertOne (SupportsExecute, SupportsReturning):
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
    sql, params = insert.to_positional_sql()

    insert = (
        InsertOne(into=actor)
        .DefaultValues()
        .Returning(actor.All())
    )
    sql = insert.to_raw_sql()
    ```
    """

    def __init__ (self, into: Table, positional: DefaultsPositional | type[IPositionalParameter] = "?") -> None:
        super().__init__()
        self.into = into
        self.data_values = tuple[ColumnWithValue | ColumnWithDefaultValue]()

        match positional:
            case IPositionalParameter():
                self.positional = positional
            case str() if positional in POSITIONAL_PARAMETERS:
                self.positional = POSITIONAL_PARAMETERS[positional]
            case _: raise ValueError(f"Unexpected Positional for InsertOne(): {positional!r}")

    def __repr__ (self) -> str:
        return f"<INSERT INTO {self.into.to_table_name()!r} 1 ROW>"

    @property
    def as_positional_sql (self) -> str:
        """Positional Parameterized `SQL: INSERT INTO {table} ({columns}) VALUES ({values}) [RETURNING {columns}]` version"""
        if not self.data_values:
            raise ValueError("InsertOne.Values() should be called first")

        positional = self.positional()
        columns = ", ".join(quote(c.column.name) for c in self.data_values)
        parameters = ", ".join(
            positional.next()
            if isinstance(column, ColumnWithValue)
            else column.to_sql()
            for column in self.data_values
        )
        returning = ", ".join(
            column.name if isinstance(column, Column) else column.alias
            for column in self.data_returning
        )

        return "\n".join(
            line
            for line in (
                f"INSERT INTO {self.into.to_table_name()}",
                f"({ columns })",
                f"VALUES ({ parameters })",
                f"RETURNING {returning}" if returning else None
            )
            if line
        )

    def to_positional_sql (self) -> tuple[str, SequenceAny]:
        """Positional Parameterized `(sql, (values, ...))`"""
        return (
            self.as_positional_sql,
            tuple(
                column.value
                for column in self.data_values
                if isinstance(column, ColumnWithValue)
            )
        )

    @override
    def to_raw_sql (self) -> str:
        """Raw `SQL: INSERT INTO {table} ({columns}) VALUES ({values}) [RETURNING {columns}]` version
        - Consider using `to_positional_sql()`"""
        if not self.data_values:
            raise ValueError("InsertOne.Values() should be called first")

        columns = ", ".join(quote(c.column.name) for c in self.data_values)
        values = ", ".join(
            to_sql_str(column.value)
            if isinstance(column, ColumnWithValue)
            else column.to_sql()
            for column in self.data_values
        )
        returning = ", ".join(
            column.name if isinstance(column, Column) else column.alias
            for column in self.data_returning
        )

        return "\n".join(
            line
            for line in (
                f"INSERT INTO { self.into.to_table_name() }\n({ columns })",
                f"VALUES ({values})",
                f"RETURNING {returning}" if returning else None
            )
            if line
        )

    @override
    def execute (self, connection: Connection, **kwargs) -> ResultSQL:
        """Execute `Insert` Statement for `Connection`
        - `kwargs` additional params `execute()` accepts"""
        sql, params = self.to_positional_sql()
        return (
            connection
            .cursor()
            .execute(sql, params, **kwargs)
        )

    def Values (self, *values: ColumnWithValue | ColumnWithDefaultValue) -> Self:
        """Apply `VALUES ({values})`  
        `.Values(T.users.id.Value(1), T.users.name.Value("Bar"))`  
        `.Values(T.users.name.Value("Foo"), T.users.id.DEFAULT_VALUE)`"""
        if not values:
            raise ValueError("At least one value is required on InsertOne.Values()")
        if self.data_values:
            raise ValueError("InsertOne.Values() should be called once")

        self.data_values = values
        return self

    def DefaultValues (self) -> InsertDefaultValues:
        """Apply `DEFAULT VALUES`"""
        return InsertDefaultValues(self.into)

class InsertMany (SupportsExecute, SupportsReturning):
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
    sql, params = insert.to_positional_sql()
    ```
    """

    def __init__ (self, into: Table, *, positional: DefaultsPositional | type[IPositionalParameter] = "?") -> None:
        super().__init__()
        self.into = into
        self.data_values = list[list[ColumnWithValue]]()

        match positional:
            case IPositionalParameter():
                self.positional = positional
            case str() if positional in POSITIONAL_PARAMETERS:
                self.positional = POSITIONAL_PARAMETERS[positional]
            case _: raise ValueError(f"Unexpected Positional for InsertMany(): {positional!r}")

    def __repr__ (self) -> str:
        return f"<INSERT INTO {self.into.to_table_name()!r} {len(self.data_values)} ROW(S)>"

    @property
    def as_positional_sql (self) -> str:
        """Positional Parameterized `SQL: INSERT INTO {table} ({columns}) VALUES ({values}) [RETURNING {columns}]` version"""
        if not self.data_values:
            raise ValueError("InsertMany.Values() should be called first")

        positional = self.positional()
        columns = ", ".join(quote(v.column.name) for v in self.data_values[0])
        parameters = ", ".join(
            positional.next()
            if isinstance(column, ColumnWithValue)
            else column.to_sql()
            for column in self.data_values[0]
        )
        returning = ", ".join(
            column.name if isinstance(column, Column) else column.alias
            for column in self.data_returning
        )

        return "\n".join(
            line
            for line in (
                f"INSERT INTO {self.into.to_table_name()}",
                f"({ columns })",
                f"VALUES ({ parameters })",
                f"RETURNING {returning}" if returning else None
            )
            if line
        )

    def to_positional_sql (self) -> tuple[str, ManySequenceAny]:
        """Positional Parameterized `(sql, [(values), ...])`"""
        return (
            self.as_positional_sql,
            [
                tuple(c.value for c in columns)
                for columns in self.data_values
            ]
        )

    @override
    def to_raw_sql (self) -> str:
        """Raw `SQL: INSERT INTO {table} ({columns}) VALUES ({values}) [RETURNING {columns}]` version
        - Consider using `to_positional_sql()`"""
        if not self.data_values:
            raise ValueError("InsertMany.Values() should be called first")

        last = self.data_values[-1]
        columns = ", ".join(quote(v.column.name) for v in self.data_values[0])
        values_gen = (
            f"""({ ", ".join(to_sql_str(column.value) for column in columns) }){ "" if columns is last else "," }"""
            for columns in self.data_values
        )
        returning = ", ".join(
            column.name if isinstance(column, Column) else column.alias
            for column in self.data_returning
        )

        return "\n".join(
            line
            for line in (
                f"INSERT INTO { self.into.to_table_name() }\n({ columns })",
                "VALUES",
                *values_gen,
                f"RETURNING {returning}" if returning else None
            )
            if line
        )

    @override
    def execute (self, connection: Connection, **kwargs) -> ResultSQL:
        """Execute `Insert` Statement for `Connection`
        - `kwargs` additional params `executemany()` accepts"""
        sql, params = self.to_positional_sql()
        return (
            connection
            .cursor()
            .executemany(sql, params, **kwargs)
        )

    def Values (self, *value: ColumnWithValue) -> Self:
        """Apply `VALUES ({values})`  
        `.Values(T.users.id.Value(1), T.users.name.Value("Bar"))`  
        `.Values(T.users.name.Value("Foo"), T.users.id.Value(2))`"""
        if not value:
            raise ValueError("At least one value is required on InsertMany.Values()")

        ordered = sorted(value, key=lambda v: v.column.name)
        columns = [c.column.name for c in ordered]

        match self.data_values:
            case []:
                if len(columns) != len(set(columns)):
                    raise ValueError(
                        f"Duplicate names found on InsertMany.Values(): {columns}"
                    )

            case [first, *_]:
                expected = [v.column.name for v in first]
                if expected != columns:
                    raise ValueError(
                        "All InsertMany.Values() rows must have the same columns names;"
                        f" Columns {columns};"
                        f" Expected {expected}"
                    )

        self.data_values.append(ordered)
        return self

__all__ = ["InsertOne", "InsertMany"]