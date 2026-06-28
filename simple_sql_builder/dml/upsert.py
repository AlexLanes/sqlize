# std
from typing import Self
# internal
from simple_sql_builder.expression import Expression
from simple_sql_builder.column import ColumnWithValue, ColumnWithDefaultValue, AliasedExpression
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
        .WhenMatched(actor.first_name.Value("Bar"), actor.last_update.DEFAULT_VALUE)
        .WhenNotMatched(actor.first_name.Value("Foo"), actor.last_name.Value("Bar"))
        .Returning(A.All()) # PostgreSQL, SQLite
        .Output(T.inserted.All()) # SQL Server
        .execute(Connection(...))
    )
    ```
    """

    table: Table
    data_on: Expression
    data_matched: list[ColumnWithValue | ColumnWithDefaultValue | AliasedExpression]
    data_not_matched: list[ColumnWithValue | ColumnWithDefaultValue]

    def __init__ (self, table: Table, *, on: Expression) -> None:
        super().__init__()
        self.table = table
        self.data_on = on
        self.data_matched = []
        self.data_not_matched = []

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
            update.parameter = self.parameter
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
            insert.parameter = self.parameter
            result = conn.execute(insert)
            assert 1 in (result.rowcount, result.returned), (
                "Upsert().execute() did not match any row to update "
                "and failed to insert a new row"
            )
            return (False, result)
        except Exception:
            if rollback_on_error: conn.rollback()
            raise

    def WhenMatched (self, *to_update: ColumnWithValue | ColumnWithDefaultValue | AliasedExpression) -> Self:
        """Values to `Update` if matched  
        `.WhenMatched(T.users.name.Value("Foo"), T.users.last_update.DEFAULT_VALUE)`"""
        if not to_update:
            raise ValueError("At least one value is required on Upsert().WhenMatched()")

        self.data_matched.extend(to_update)
        return self

    def WhenNotMatched (self, *to_insert: ColumnWithValue | ColumnWithDefaultValue) -> Self:
        """Values to `Insert` if not matched  
        `.WhenNotMatched(T.users.name.Value("Foo"), T.users.last_update.DEFAULT_VALUE)`"""
        if not to_insert:
            raise ValueError("At least one value is required on Upsert().WhenNotMatched()")

        self.data_not_matched.extend(to_insert)
        return self

__all__ = ["Upsert"]