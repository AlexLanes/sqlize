# std
from typing import Self
# internal
from simple_sql_builder.shared import quote, ManySequenceAny
from simple_sql_builder.connection import Connection, ResultSQL
from simple_sql_builder.expression import to_sql_str
from simple_sql_builder.column import Column, ColumnWithValue, AliasedColumn
from simple_sql_builder.table import Table
from simple_sql_builder.parameters import *

class Insert:

    into: Table
    data_values: list[list[ColumnWithValue]]
    data_returning: list[Column | AliasedColumn]
    positional: type[IPositionalParameter]

    def __init__ (self, into: Table, *, positional: DefaultsPositional | type[IPositionalParameter] = "?") -> None:
        self.into = into
        self.data_values = []
        self.data_returning = []

        match positional:
            case IPositionalParameter():
                self.positional = positional
            case str() if positional in POSITIONAL_PARAMETERS:
                    self.positional = POSITIONAL_PARAMETERS[positional]
            case _: raise ValueError(f"Unexpected Positional for Insert(): {positional!r}")

    def __repr__ (self) -> str:
        return f"<INSERT INTO {self.into.to_table_name()!r} {len(self.data_values)} ROW(S)>"

    @property
    def as_positional_sql (self) -> str:
        """Positional Parameterized `SQL: INSERT INTO table (column, ...) VALUES (param, ...) RETURNING ...` version"""
        if not self.data_values:
            raise ValueError("Insert.Values() should be called first")

        positional = self.positional()
        columns = ", ".join(quote(v.column.name) for v in self.data_values[0])
        parameters = ", ".join(positional.next() for _ in self.data_values[0])
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
        """Positional Parameterized `SQL: INSERT INTO table (column, ...) VALUES (param, ...) RETURNING ...` version
        - Return `(sql, [(values, ...)])`"""
        return (
            self.as_positional_sql,
            [
                tuple(c.value for c in columns)
                for columns in self.data_values
            ]
        )

    def to_raw_sql (self) -> str:
        """Raw `SQL: INSERT INTO table (column, ...) VALUES (value, ...) RETURNING ...` version
        - Consider using `to_positional_sql()`"""
        if not self.data_values:
            raise ValueError("Insert.Values() should be called first")

        last = self.data_values[-1]
        columns = ", ".join(quote(v.column.name) for v in self.data_values[0])
        insert = f"INSERT INTO {self.into.to_table_name()}\n({columns})"
        values_gen = (
            f"""({ ", ".join(to_sql_str(v.value) for v in values) }){ "" if values is last else "," }"""
            for values in self.data_values
        )
        returning = ", ".join(
            column.name if isinstance(column, Column) else column.alias
            for column in self.data_returning
        )

        return "\n".join(
            line
            for line in (
                insert,
                "VALUES",
                *values_gen,
                f"RETURNING {returning}" if returning else None
            )
            if line
        )

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
        """Apply `({Columns}) VALUES ({Values})`  
        `.Values(T.users.id.Value(1), T.users.name.Value("Bar"))`  
        `.Values(T.users.id.Value(2), T.users.name.Value("Foo"))`"""
        if not value:
            raise ValueError("At least one value is required on Insert.Values()")

        ordered = sorted(value, key=lambda v: v.column.name)
        columns = [c.column.name for c in ordered]

        match self.data_values:
            case []:
                if len(columns) != len(set(columns)):
                    raise ValueError(
                        f"Duplicate names found on Insert.Values(): {columns}"
                    )

            case [first, *_]:
                expected = [v.column.name for v in first]
                if expected != columns:
                    raise ValueError(
                        "All Insert.Values() rows must have the same columns names;"
                        f" Columns {columns};"
                        f" Expected {expected}"
                    )

        self.data_values.append(ordered)
        return self

    def Returning (self, *value: Column | AliasedColumn) -> Self:
        """Apply `RETURNING {Columns}`  
        `.Returning(A.All())`  
        `.Returning(T.users.id, A.name)`"""
        self.data_returning = list(value)
        return self

__all__ = ["Insert"]