# std
from itertools import chain
from typing import Any, Self, override
from dataclasses import dataclass, field
# internal
from sqlize.parameters import IPositionalParameter
from sqlize.shared import ManySequenceAny, SequenceAny, SQLValue
from sqlize.expression import AliasedExpression, to_sql
from sqlize.column import ColumnWithDefaultValue, ColumnEqualsValue, Column, AliasedColumn
from sqlize.table import Table
from sqlize.supports import SupportsReturning, ExecutableStatement, Data
from sqlize.statement.interface import SQLizerModel

@dataclass
class InsertData[T] (Data):

    values: list[list[T]] = field(default_factory=list)
    ignore: bool = False
    """`INSERT IGNORE`"""

    do_nothing: list[str] | None = None
    """`ON CONFLICT [(columns)] DO NOTHING`"""
    do_update: tuple[list[str], list[ColumnEqualsValue | AliasedExpression | ColumnWithDefaultValue], bool] | None = None
    """`([conflicts], [updates], is_postgresql)`"""

    def conflict (self, positional: IPositionalParameter) -> tuple[list[str], list[Any]] | None:
        """Returns `([sql_parts], [params])`
        - `None` if not set"""
        # DO NOTHING
        if (do_nothing := self.do_nothing) is not None:
            if not do_nothing: return (["ON CONFLICT DO NOTHING"], [])
            else: return ([f"ON CONFLICT ({ ", ".join(do_nothing) }) DO NOTHING"], [])

        # DO UPDATE
        elif (do_update := self.do_update) is not None:
            params = []
            sets = list[str]()
            for value in do_update[1]:
                match value:
                    case ColumnEqualsValue():
                        name = value.left.quote_name(self.quote_info)
                        sets.append(f"{name} = {positional.next()}")
                        params.append(value.right)
                    case AliasedExpression():
                        name = value.quote_alias(self.quote_info)
                        sql = to_sql(value.expression, table_alias=False, quote_info=self.quote_info)
                        parameterized = sql.join().format(*(positional.next() for _ in sql))
                        sets.append(f"{name} = {parameterized}")
                        params.extend(sql)
                    case ColumnWithDefaultValue():
                        name = value.column.quote_name(self.quote_info)
                        sets.append(f"{name} = {value.to_sql().join()}")

            is_postgresql = do_update[2]
            return [
                f"ON CONFLICT ({ ", ".join(do_update[0]) }) DO UPDATE SET"
                if is_postgresql
                else "ON DUPLICATE KEY UPDATE",

                ",\n".join(sets)
            ], params

class SupportsConflicts:

    data: InsertData

    def Ignore (self) -> Self:
        """Ignore insert errors and skip conflicting rows
        #### Supported By: `MySQL`"""
        self.data.ignore = True
        return self

    def OnConflictDoNothing (self, *conflict: str | Column | AliasedColumn) -> Self:
        """Skip rows that violate a unique or exclusion constraint
        - `conflict` optional
        #### Supported By: `PostgreSQL` `SQLite`"""
        on = []
        quote_info = self.data.quote_info

        for column in conflict:
            match column:
                case Column(): on.append(column.quote_name(quote_info))
                case AliasedColumn(): on.append(column.quote_alias(quote_info))
                case _: on.append(str(column))

        self.data.do_nothing = on
        return self

    def OnConflictDoUpdate (self, conflicts: list[str | Column | AliasedColumn],
                                  *to_update: ColumnEqualsValue | AliasedExpression | ColumnWithDefaultValue,
                                  **to_updates: SQLValue) -> Self:
        """Update existing rows that violate a unique or exclusion constraint
        #### `SQLite`
        `.OnConflictDoUpdate(["id"], T.users.name == "Foo", last_name="Bar")`  
        `.OnConflictDoUpdate(["id"], E.CURRENT_TIMESTAMP.As("last_update"))`  
        `.OnConflictDoUpdate([T.users.email], (T.users.age * 2).As("age"))`  
        `.OnConflictDoUpdate([T.users.email], (T.excluded.age * 2).As("age"))`
        #### `PostgreSQL`
        `.OnConflictDoUpdate(["id"], T.users.name == "Foo", last_name="Bar")`  
        `.OnConflictDoUpdate(["id"], T.users.last_update.DEFAULT_VALUE))`  
        `.OnConflictDoUpdate([T.users.email], (T.users.age * 2).As("age"))`  
        `.OnConflictDoUpdate([T.users.email], (T.EXCLUDED.age * 2).As("age"))`"""
        assert self.data.table is not None
        if not conflicts:
            raise ValueError(f"At least one value is required to 'conflicts' on {self.__class__.__name__}().OnConflictDoUpdate()")
        if not to_update and not to_updates:
            raise ValueError(f"At least one value is required to 'update' on {self.__class__.__name__}().OnConflictDoUpdate()")

        conflict = list[str]()
        quote_info = self.data.quote_info

        for column in conflicts:
            match column:
                case Column(): conflict.append(column.quote_name(quote_info))
                case AliasedColumn(): conflict.append(column.quote_alias(quote_info))
                case _: conflict.append(str(column))

        sets = [*to_update]
        sets.extend(
            ColumnEqualsValue(self.data.table.Column(column), "=", value)
            for column, value in to_updates.items()
        )

        self.data.do_update = (conflict, sets, True)
        return self

    def OnDuplicateKeyUpdate (self, *to_update: ColumnEqualsValue | AliasedExpression | ColumnWithDefaultValue,
                                    **to_updates: SQLValue) -> Self:
        """Update existing rows when a duplicate key conflict occurs
        #### Supported By: `MySQL`
        `.OnDuplicateKeyUpdate(T.users.name == "Foo", last_name="Bar")`  
        `.OnDuplicateKeyUpdate(T.users.last_update.DEFAULT_VALUE)`  
        #### Current Value
        `.OnDuplicateKeyUpdate((A.age * 2).As("age"))`  
        `.OnDuplicateKeyUpdate((T.users.age * 2).As("age"))`  
        Translates to `age = (age * %s)`
        #### Insert Value
        `.OnDuplicateKeyUpdate(E.VALUES(A.name).As("name"))`  
        `.OnDuplicateKeyUpdate(E.VALUES(T.users.name).As("name"))`  
        Translates to `name = VALUES(name)`
        """
        assert self.data.table is not None
        if not to_update and not to_updates:
            raise ValueError(f"At least one value is required to 'update' on {self.__class__.__name__}().OnConflictDoUpdate()")

        sets = [*to_update]
        sets.extend(
            ColumnEqualsValue(self.data.table.Column(column), "=", value)
            for column, value in to_updates.items()
        )

        self.data.do_update = ([], sets, False)
        return self

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

class Insert (ExecutableStatement, SupportsReturning, SupportsConflicts):
    """Builder of `Insert` Statement

    ## Examples
    ```python
    from sqlize import E, A, T, Insert, Connection

    actor = T.actor
    insert = (
        Insert(into=actor)
        .Values(
            actor.actor_id.DEFAULT_VALUE,
            actor.first_name == "Alex",
            actor.last_name == "Lanes",
            E.CURRENT_TIMESTAMP.As("last_update")
        )
        .Returning(actor.All()) # PostgreSQL, SQLite
    )
    insert = (
        Insert(into="actor")
        .Values(
            first_name = "Alex",
            last_name = "Lanes",
            last_update = datetime.now()
        )
        .Output(T.inserted.All()) # SQL Server
    )
    insert = (
        Insert(into=actor)
        .DefaultValues()
        .Returning(A.All())
    )

    # Transform
    sql, params = insert.to_sql()
    # Execute
    Connection(...).execute(select)
    ```
    """

    data: InsertData[ColumnEqualsValue | ColumnWithDefaultValue | AliasedExpression]

    def __init__ (self, into: Table | str | SQLizerModel) -> None:
        super().__init__()
        self.data = InsertData() # type: ignore
        match into:
            case str(): self.data.table = Table(into, None)
            case Table(): self.data.table = into
            case _ if isinstance(into.__table__, Table):
                self.data.table = into.__table__
            case _:
                self.data.table = Table(str(into.__table__), None)

    def __repr__ (self) -> str:
        assert self.data.table is not None
        return f"<INSERT INTO {self.data.table.to_table_name()!r} 1 ROW>"

    @override
    def to_sql (self) -> tuple[str, SequenceAny]:
        assert self.data.table is not None
        if not self.data.values:
            raise ValueError("Insert().Values() should be called first")

        params = []
        columns, values = [], []
        positional = self.data.parameter()
        for value in self.data.values[0]:
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

                case _: raise TypeError(f"Invalid value found on Insert().Values({value!r})")

        # INSERT INTO
        insert = "INSERT IGNORE" if self.data.ignore else "INSERT"
        parts = [
            f"{insert} INTO {self.data.table.to_table_name()}",
            f"({ ", ".join(columns) })",
        ]

        # OUTPUT
        if data := self.data.data_output(False):
            parameters = (positional.next() for _ in data)
            parts.append(data.join().format(*parameters))
            params.extend(data)

        # VALUES
        parts.append(f"VALUES ({ ", ".join(values) })")

        # ON CONFLICT
        if (data := self.data.conflict(positional)) is not None:
            parts.extend(data[0])
            params.extend(data[1])

        # RETURNING
        if data := self.data.data_returning(False):
            parameters = (positional.next() for _ in data)
            parts.append(data.join().format(*parameters))
            params.extend(data)

        return "\n".join(parts), params

    def Values (self, *column: ColumnEqualsValue | AliasedExpression | ColumnWithDefaultValue, **columns: SQLValue) -> Self:
        """Apply `VALUES ({ columns })`  
        `.Values(name="Foo", age=11, last_update=datetime.now())`  
        `.Values(T.users.id.DEFAULT_VALUE, T.users.name == "Foo", E.CURRENT_TIMESTAMP.As("last_update"))`"""
        assert self.data.table is not None
        if not column and not columns:
            raise ValueError("At least one value is required on Insert().Values()")
        if self.data.values:
            raise ValueError("Insert().Values() should be called once")

        self.data.values.append(list(column))
        self.data.values[0].extend(
            ColumnEqualsValue(self.data.table.Column(column), "=", value)
            for column, value in columns.items()
        )
        return self

    def DefaultValues (self) -> InsertDefaultValues:
        """Apply `INSERT INTO {table} DEFAULT VALUES`
        #### Supported By: `SQLite` `PostgreSQL` `MicrosoftSQL`"""
        assert self.data.table is not None
        return InsertDefaultValues(self.data.table)

class InsertMany (ExecutableStatement, SupportsReturning, SupportsConflicts):
    """Builder of `Insert` Statement with multiple values

    ## Example
    ```python
    from sqlize import T, InsertMany, Connection

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

    data: InsertData[ColumnEqualsValue]

    def __init__ (self, into: Table | str | SQLizerModel) -> None:
        super().__init__()
        self.data = InsertData() # type: ignore
        match into:
            case str(): self.data.table = Table(into, None)
            case Table(): self.data.table = into
            case _ if isinstance(into.__table__, Table):
                self.data.table = into.__table__
            case _:
                self.data.table = Table(str(into.__table__), None)

    def __repr__ (self) -> str:
        assert self.data.table is not None
        return f"<INSERT INTO {self.data.table.to_table_name()!r} {len(self.data.values)} ROW(S)>"

    @override
    def to_sql (self) -> tuple[str, ManySequenceAny]:
        assert self.data.table is not None
        if not self.data.values:
            raise ValueError("InsertMany().Values() should be called first")

        table_alias = False
        first = self.data.values[0]
        positional = self.data.parameter()

        # INSERT INTO COLUMNS
        insert = "INSERT IGNORE" if self.data.ignore else "INSERT"
        parts = [
            f"{insert} INTO {self.data.table.to_table_name()}",
            f"({ ", ".join(c.left.quote_name(self.data.quote_info) for c in first) })",
        ]

        # OUTPUT
        output = []
        if data := self.data.data_output(table_alias):
            parameters = (positional.next() for _ in data)
            parts.append(data.join().format(*parameters))
            output.extend(data)

        # VALUES
        parts.append(f"VALUES ({ ", ".join(positional.next() for _ in first) })")

        # ON CONFLICT
        conflicts = []
        if (data := self.data.conflict(positional)) is not None:
            parts.extend(data[0])
            conflicts = data[1]

        # RETURNING
        returning = []
        if data := self.data.data_returning(table_alias):
            parameters = (positional.next() for _ in data)
            parts.append(data.join().format(*parameters))
            returning.extend(data)

        return (
            "\n".join(parts),
            [
                tuple(chain(
                    output,
                    (column.right for column in columns),
                    conflicts,
                    returning
                ))
                for columns in self.data.values
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

        match self.data.values:
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

        self.data.values.append(ordered)
        return self

__all__ = ["Insert", "InsertMany"]