# std
from typing import Self
# internal
from simple_sql_builder.shared import SQLValue
from simple_sql_builder.expression import Expression
from simple_sql_builder.column import ColumnEqualsValue, ColumnWithDefaultValue, AliasedExpression
from simple_sql_builder.table import Table
from simple_sql_builder.supports import SupportsReturning, SupportParameter
from simple_sql_builder import Update, InsertOne, Connection, ResultSQL

class Upsert (SupportsReturning, SupportParameter):
    """Builder of `Update` or `Insert` Statement

    ## Example
    ```python
    from simple_sql_builder import A, T, Upsert, Connection

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

    table: Table
    data_on: Expression
    data_matched: list[ColumnEqualsValue | ColumnWithDefaultValue | AliasedExpression]
    data_not_matched: list[ColumnEqualsValue | ColumnWithDefaultValue]

    def __init__ (self, table: Table | str, *, on: Expression) -> None:
        super().__init__()
        self.data_on = on
        self.data_matched = []
        self.data_not_matched = []
        self.table = table if isinstance(table, Table) else Table(table, None)

    def __repr__ (self) -> str:
        return f"<UPDATE or INSERT {self.table.to_table_name()!r}"

    def execute (self, conn: Connection, *, rollback_on_error=True) -> tuple[bool, ResultSQL]:
        """Use a `Connection` to execute `Update` or `Insert` Statement
        - `WhenMatched` do `Update`
        - `WhenNotMatched` do `Insert`
        - Returns `(updated, ResultSQL)`"""
        if not self.data_matched:
            raise ValueError("Upsert().WhenMatched() should be called first")
        if not self.data_not_matched:
            raise ValueError("Upsert().WhenNotMatched() should be called first")

        # TRY UPDATE
        try:
            update = Update(self.table).Set(*self.data_matched).Where(self.data_on)
            update.data_returning = self.data_returning
            update.data_output = self.data_output
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
            insert = InsertOne(into=self.table).Values(*self.data_not_matched)
            insert.data_returning = self.data_returning
            insert.data_output = self.data_output
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
        if not to_update and not columns:
            raise ValueError("At least one value is required on Upsert().WhenMatched()")

        self.data_matched.extend(to_update)
        self.data_matched.extend(
            ColumnEqualsValue(self.table.Column(column), "=", value)
            for column, value in columns.items()
        )
        return self

    def WhenNotMatched (self, *to_insert: ColumnEqualsValue | ColumnWithDefaultValue, **columns: SQLValue) -> Self:
        """Values to `Insert` if not matched  
        `.WhenNotMatched(T.users.name == "Foo", T.users.last_update.DEFAULT_VALUE)`  
        `.WhenMatched(name="Foo", last_update=datetime.now())`"""
        if not to_insert and not columns:
            raise ValueError("At least one value is required on Upsert().WhenNotMatched()")

        self.data_not_matched.extend(to_insert)
        self.data_not_matched.extend(
            ColumnEqualsValue(self.table.Column(column), "=", value)
            for column, value in columns.items()
        )
        return self

__all__ = ["Upsert"]