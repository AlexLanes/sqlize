# std
from typing import Self, override
# internal
from simple_sql_builder.shared import ManySequenceAny, SequenceAny, SQLValue
from simple_sql_builder.expression import AliasedExpression, to_sql
from simple_sql_builder.column import ColumnWithDefaultValue, ColumnEqualsValue
from simple_sql_builder.table import Table
from simple_sql_builder.supports import SupportsReturning, ExecutableStatement

class InsertDefaultValues (ExecutableStatement, SupportsReturning):

    def __init__ (self, into: Table) -> None:
        super().__init__()
        self.data.table = into

    def __repr__ (self) -> str:
        assert self.data.table is not None
        return f"<INSERT INTO {self.data.table.to_table_name()!r} DEFAULT VALUES>"

    @override
    def to_sql (self) -> tuple[str, SequenceAny]:
        assert self.data.table is not None

        table_alias = False
        positional = self.data.parameter()
        params, sqls = [], [f"INSERT INTO {self.data.table.to_table_name()}"]

        if data := self.data.data_output(table_alias):
            parameters = (positional.next() for _ in data)
            sqls.append(data.join().format(*parameters))
            params.extend(data)

        sqls.append("DEFAULT VALUES")

        if data := self.data.data_returning(table_alias):
            parameters = (positional.next() for _ in data)
            sqls.append(data.join().format(*parameters))
            params.extend(data)

        return "\n".join(sqls), params

class InsertOne (ExecutableStatement, SupportsReturning):
    """Builder of `Insert` Statement

    ## Examples
    ```python
    from simple_sql_builder import E, A, T, InsertOne, Connection

    actor = T.actor
    insert = (
        InsertOne(into=actor)
        .Values(
            actor.actor_id.DEFAULT_VALUE,
            actor.first_name == "Alex",
            actor.last_name == "Lanes",
            E.CURRENT_TIMESTAMP.As("last_update")
        )
        .Returning(actor.All()) # PostgreSQL, SQLite
    )
    insert = (
        InsertOne(into="actor")
        .Values(
            first_name = "Alex",
            last_name = "Lanes",
            last_update = datetime.now()
        )
        .Output(T.inserted.All()) # SQL Server
    )
    insert = (
        InsertOne(into=actor)
        .DefaultValues()
        .Returning(A.All())
    )

    # Transform
    sql, params = insert.to_sql()
    # Execute
    Connection(...).execute(select)
    ```
    """

    data_values: list[ColumnEqualsValue | ColumnWithDefaultValue | AliasedExpression]

    def __init__ (self, into: Table | str) -> None:
        super().__init__()
        self.data_values = []
        self.data.table = into if isinstance(into, Table) else Table(into, None)

    def __repr__ (self) -> str:
        assert self.data.table is not None
        return f"<INSERT INTO {self.data.table.to_table_name()!r} 1 ROW>"

    @override
    def to_sql (self) -> tuple[str, SequenceAny]:
        assert self.data.table is not None
        if not self.data_values:
            raise ValueError("InsertOne().Values() should be called first")

        params = []
        columns, values = [], []
        positional = self.data.parameter()
        for value in self.data_values:
            match value:

                case ColumnEqualsValue():
                    columns.append(value.left.quote_name(self.data.quote_info))
                    values.append(positional.next())
                    params.append(value.right)

                case ColumnWithDefaultValue():
                    columns.append(value.column.quote_name(self.data.quote_info))
                    values.append(value.to_sql().join())

                case AliasedExpression():
                    columns.append(value.quote_alias(self.data.quote_info))
                    sql = to_sql(value.expression, table_alias=False)
                    parameters = (positional.next() for _ in sql)
                    values.append(sql.join().format(*parameters))
                    params.extend(sql)

                case _: raise TypeError(f"Invalid value found on InsertOne().Values({value!r})")

        parts = [
            f"INSERT INTO {self.data.table.to_table_name()}",
            f"({ ", ".join(columns) })",
        ]

        if data := self.data.data_output(False):
            parameters = (positional.next() for _ in data)
            parts.append(data.join().format(*parameters))
            params.extend(data)

        parts.append(f"VALUES ({ ", ".join(values) })")

        if data := self.data.data_returning(False):
            parameters = (positional.next() for _ in data)
            parts.append(data.join().format(*parameters))
            params.extend(data)

        return "\n".join(parts), params

    def Values (self, *values: ColumnEqualsValue | ColumnWithDefaultValue | AliasedExpression, **columns: SQLValue) -> Self:
        """Apply `VALUES ({ values })`  
        `.Values(name="Foo", age=11, last_update=datetime.now())`  
        `.Values(T.users.id.DEFAULT_VALUE, T.users.name == "Foo", E.CURRENT_TIMESTAMP.As("last_update"))`"""
        assert self.data.table is not None
        if not values and not columns:
            raise ValueError("At least one value is required on InsertOne().Values()")

        self.data_values.extend(values)
        self.data_values.extend(
            ColumnEqualsValue(self.data.table.Column(column), "=", value)
            for column, value in columns.items()
        )
        return self

    def DefaultValues (self) -> InsertDefaultValues:
        """Apply `DEFAULT VALUES`"""
        assert self.data.table is not None
        return InsertDefaultValues(self.data.table)

class InsertMany (ExecutableStatement, SupportsReturning):
    """Builder of `Insert` Statement with multiple values

    ## Example
    ```python
    from simple_sql_builder import T, InsertMany, Connection

    actor = T.actor
    insert = (
        InsertMany(into=actor)
        .Values(actor.first_name == "Alex", actor.last_name =="Lanes")
        .Values(last_name="Foo", first_name="Bar")
        .Returning(actor.All()) # PostgreSQL
        .Output(T.inserted.All()) # SQL Server
    )

    # Transform
    sql, params = insert.to_sql()
    # Execute
    Connection(...).execute(select)
    ```
    """

    data_values: list[list[ColumnEqualsValue]]

    def __init__ (self, into: Table | str) -> None:
        super().__init__()
        self.data_values = []
        self.data.table = into if isinstance(into, Table) else Table(into, None)

    def __repr__ (self) -> str:
        assert self.data.table is not None
        return f"<INSERT INTO {self.data.table.to_table_name()!r} {len(self.data_values)} ROW(S)>"

    @override
    def to_sql (self) -> tuple[str, ManySequenceAny]:
        assert self.data.table is not None
        if not self.data_values:
            raise ValueError("InsertMany().Values() should be called first")

        table_alias = False
        first = self.data_values[0]
        positional = self.data.parameter()
        parts = [
            f"INSERT INTO {self.data.table.to_table_name()}",
            f"({ ", ".join(c.left.quote_name(self.data.quote_info) for c in first) })",
        ]

        output = []
        if data := self.data.data_output(table_alias):
            parameters = (positional.next() for _ in data)
            parts.append(data.join().format(*parameters))
            output.extend(data)

        parts.append(f"VALUES ({ ", ".join(positional.next() for _ in first) })")

        returning = []
        if data := self.data.data_returning(table_alias):
            parameters = (positional.next() for _ in data)
            parts.append(data.join().format(*parameters))
            returning.extend(data)

        return (
            "\n".join(parts),
            [
                tuple(
                    value
                    for column in columns
                    for value in [*output, column.right, *returning]
                )
                for columns in self.data_values
            ]
        )

    def Values (self, *value: ColumnEqualsValue, **columns: SQLValue) -> Self:
        """Apply `VALUES ({ values })`  
        `.Values(T.users.id == 1, T.users.name == "Foo")`  
        `.Values(name="Bar", id=2)`"""
        assert self.data.table is not None
        if not value and not columns:
            raise ValueError("At least one value is required on InsertMany().Values()")

        ordered = sorted(
            [
                *value,
                *(
                    ColumnEqualsValue(self.data.table.Column(column), "=", value)
                    for column, value in columns.items()
                )
            ],
            key = lambda c: c.left.name
        )
        names = [c.left.name for c in ordered]

        match self.data_values:
            case [] if len(names) != len(set(names)):
                raise ValueError(f"Duplicate names found on InsertMany().Values(): {names}")

            case [first, *_]:
                expected = [c.left.name for c in first]
                if expected != names:
                    raise ValueError(
                        "All InsertMany().Values() rows must have the same columns names;"
                        f" Columns {names};"
                        f" Expected {expected}"
                    )

        self.data_values.append(ordered)
        return self

__all__ = ["InsertOne", "InsertMany"]