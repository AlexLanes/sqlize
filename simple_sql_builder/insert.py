# std
from typing import Self
# internal
from simple_sql_builder.shared import quote, ManySequenceAny
from simple_sql_builder.connection import Connection, ResultSQL
from simple_sql_builder.expression import to_sql_str
from simple_sql_builder.column import ColumnWithValue
from simple_sql_builder.table import Table
from simple_sql_builder.parameters import *

class Insert:

    into: Table
    data: list[list[ColumnWithValue]]
    positional: type[IPositionalParameter]

    def __init__ (self, into: Table, *, positional: DefaultsPositional | type[IPositionalParameter] = "?") -> None:
        self.data = []
        self.into = into

        match positional:
            case IPositionalParameter():
                self.positional = positional
            case str() if positional in POSITIONAL_PARAMETERS:
                    self.positional = POSITIONAL_PARAMETERS[positional]
            case _: raise ValueError(f"Unexpected Positional for Insert(): {positional!r}")

    def __repr__ (self) -> str:
        return f"<INSERT INTO {self.into.to_table_name()!r} {len(self.data)} ROW(S)>"

    @property
    def as_positional_sql (self) -> str:
        """Positional Parameterized `SQL: INSERT INTO table (column, ...) VALUES (param, ...)` version"""
        if not self.data:
            raise ValueError("Insert.Values() should be called first")

        positional = self.positional()
        columns = ", ".join(quote(v.column.name) for v in self.data[0])
        parameters = ", ".join(positional.next() for _ in self.data[0])
        return "\n".join((
            f"INSERT INTO {self.into.to_table_name()}",
            f"({ columns })",
            f"VALUES ({ parameters })"
        ))

    def to_positional_sql (self) -> tuple[str, ManySequenceAny]:
        """Positional Parameterized `SQL: INSERT INTO table (column, ...) VALUES (param, ...)` version
        - Return `(sql, [(values, ...)])`"""
        return (
            self.as_positional_sql,
            [
                tuple(c.value for c in columns)
                for columns in self.data
            ]
        )

    def to_raw_sql (self) -> str:
        """Raw `SQL: INSERT INTO table (column, ...) VALUES (value, ...)` version
        - Consider using `to_positional_sql()`"""
        if not self.data:
            raise ValueError("Insert.Values() should be called first")

        last = self.data[-1]
        columns = ", ".join(quote(v.column.name) for v in self.data[0])
        insert = f"INSERT INTO {self.into.to_table_name()}\n({columns})"
        values_gen = (
            f"""({ ", ".join(to_sql_str(v.value) for v in values) }){ "" if values is last else "," }"""
            for values in self.data
        )

        return "\n".join((
            insert,
            "VALUES",
            *values_gen
        ))

    def execute (self, connection: Connection, *, commit=False) -> ResultSQL:
        """Execute `Insert` Statement for `Connection`"""
        result = (
            connection
            .cursor()
            .executemany(*self.to_positional_sql())
        )
        if commit: connection.commit()
        return result

    def Values (self, *value: ColumnWithValue) -> Self:
        """Apply `*ColumnWithValue` into `Insert`  
        `.Values(T.users.id.Value(1), T.users.name.Value("Bar"))`  
        `.Values(T.users.id.Value(2), T.users.name.Value("Foo"))`"""
        if not value:
            raise ValueError("At least one value is required on Insert.Values()")

        ordered = sorted(value, key=lambda v: v.column.name)
        columns = [c.column.name for c in ordered]

        match self.data:
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

        self.data.append(ordered)
        return self

__all__ = ["Insert"]