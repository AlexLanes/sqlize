# std
from typing import Self
from dataclasses import dataclass, field
# internal
from pysqlbuilder.shared import SQLValue
from pysqlbuilder.expression import Expression
from pysqlbuilder.column import ColumnEqualsValue, ColumnWithDefaultValue, AliasedExpression
from pysqlbuilder.table import Table
from pysqlbuilder.supports import SupportsReturning, SupportParameters, Data
from pysqlbuilder import Update, Insert, Connection, ResultSQL

@dataclass
class UpsertData (Data):
    on: Expression | None = None
    matched: list[ColumnEqualsValue | ColumnWithDefaultValue | AliasedExpression] = field(default_factory=list)
    not_matched: list[ColumnEqualsValue | ColumnWithDefaultValue] = field(default_factory=list)

class Upsert (SupportsReturning, SupportParameters):
    """Builder of `Update` or `Insert` Statement

    ## Example
    ```python
    from pysqlbuilder import A, T, Upsert, Connection

    actor = T.actor
    updated, result = (
        Upsert(actor, on=actor.actor_id == 1)
        .WhenMatched(actor.first_name == "Bar", actor.last_update.DEFAULT_VALUE)
        .WhenNotMatched(actor.first_name == "Foo", actor.last_name == "Bar")
        .Returning(A.All()) # PostgreSQL, SQLite
        .Output(T.inserted.All()) # SQL Server
        .execute(Connection(...))
    )
    ```
    """

    data: UpsertData

    def __init__ (self, table: Table | str, *, on: Expression) -> None:
        super().__init__()
        self.data = UpsertData() # type: ignore
        self.data.on = on
        self.data.table = table if isinstance(table, Table) else Table(table, None)

    def __repr__ (self) -> str:
        assert self.data.table is not None
        return f"<UPDATE or INSERT {self.data.table.to_table_name()!r}"

    def execute (self, conn: Connection, *, rollback_on_error=True) -> tuple[bool, ResultSQL]:
        """Use a `Connection` to execute `Update` or `Insert` Statement
        - `WhenMatched` do `Update`
        - `WhenNotMatched` do `Insert`
        - Returns `(updated, ResultSQL)`"""
        assert self.data.on is not None
        assert self.data.table is not None
        if not self.data.matched:
            raise ValueError("Upsert().WhenMatched() should be called first")
        if not self.data.not_matched:
            raise ValueError("Upsert().WhenNotMatched() should be called first")

        # TRY UPDATE
        try:
            update = Update(self.data.table).Set(*self.data.matched).Where(self.data.on)
            update.data.returning = self.data.returning
            update.data.output = self.data.output
            result = conn.execute(update)
            if 1 in (result.rowcount, result.returned): return (True, result)
            assert not result, (
                "Upsert().execute() resulted on more than 1 rowcount; "
                "Upsert().On() should be more strict, like using a Primary Key"
            )
        except Exception:
            if rollback_on_error: conn.rollback()
            raise

        # TRY INSERT
        try:
            insert = Insert(self.data.table).Values(*self.data.not_matched)
            insert.data.returning = self.data.returning
            insert.data.output = self.data.output
            result = conn.execute(insert)
            assert 1 in (result.rowcount, result.returned), (
                "Upsert().execute() did not match any row to Update "
                "and failed to Insert a new row"
            )
            return (False, result)
        except Exception:
            if rollback_on_error: conn.rollback()
            raise

    def WhenMatched (self, *to_update: ColumnEqualsValue | ColumnWithDefaultValue | AliasedExpression, **columns: SQLValue) -> Self:
        """Values to `Update` if matched  
        `.WhenMatched(T.users.name == "Foo", T.users.last_update.DEFAULT_VALUE)`  
        `.WhenMatched(name="Foo", last_update=datetime.now())`"""
        assert self.data.table is not None
        if not to_update and not columns:
            raise ValueError("At least one value is required on Upsert().WhenMatched()")

        self.data.matched.extend(to_update)
        self.data.matched.extend(
            ColumnEqualsValue(self.data.table.Column(column), "=", value)
            for column, value in columns.items()
        )
        return self

    def WhenNotMatched (self, *to_insert: ColumnEqualsValue | ColumnWithDefaultValue, **columns: SQLValue) -> Self:
        """Values to `Insert` if not matched  
        `.WhenNotMatched(T.users.name == "Foo", T.users.last_update.DEFAULT_VALUE)`  
        `.WhenNotMatched(name="Foo", last_update=datetime.now())`"""
        assert self.data.table is not None
        if not to_insert and not columns:
            raise ValueError("At least one value is required on Upsert().WhenNotMatched()")

        self.data.not_matched.extend(to_insert)
        self.data.not_matched.extend(
            ColumnEqualsValue(self.data.table.Column(column), "=", value)
            for column, value in columns.items()
        )
        return self

__all__ = ["Upsert"]