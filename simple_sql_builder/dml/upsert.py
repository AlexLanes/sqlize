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
        .WhenMatch(actor.first_name.Value("Bar"), actor.last_update.DEFAULT_VALUE)
        .WhenNotMatch(actor.first_name.Value("Foo"), actor.last_name.Value("Bar"))
        .Returning(A.All())
        .execute(...)
    )
    ```
    """

    table: Table
    data_on: Expression
    data_match: list[ColumnWithValue | ColumnWithDefaultValue | AliasedExpression]
    data_not_match: list[ColumnWithValue | ColumnWithDefaultValue]

    def __init__ (self, table: Table, *, on: Expression) -> None:
        super().__init__()
        self.table = table
        self.data_on = on
        self.data_match = []
        self.data_not_match = []

    def __repr__ (self) -> str:
        return f"<UPDATE or INSERT {self.table.to_table_name()!r}"

    def execute (self, conn: Connection, *, rollback_on_error=True) -> tuple[bool, ResultSQL]:
        """Use a `Connection` to execute `Update` or `Insert` Statement
        - `WhenMatch` do `Update`
        - `WhenNotMatch` do `Insert`
        - Returns `(updated, ResultSQL)`"""
        if not self.data_match:
            raise ValueError("Upsert().WhenMatch() should be called first")
        if not self.data_not_match:
            raise ValueError("Upsert().WhenNotMatch() should be called first")

        # TRY UPDATE
        try:
            update = Update(self.table).Set(*self.data_match).Where(self.data_on)
            update.data_returning = self.data_returning
            update.parameter = self.parameter
            result = conn.execute(update)
            if result.rowcount == 1: return (True, result)
            assert result.rowcount < 1, (
                "Upsert().execute() resulted on more than 1 rowcount; "
                "Upsert().On() should be more strict, like using a Primary Key"
            )
        except AssertionError: raise
        except Exception:
            if rollback_on_error: conn.rollback()
            raise

        # TRY INSERT
        try:
            insert = InsertOne(into=self.table).Values(*self.data_not_match)
            insert.data_returning = self.data_returning
            insert.parameter = self.parameter
            result = conn.execute(insert)
            assert result.rowcount == 1, (
                "Upsert().execute() did not match any row to update "
                "and failed to insert a new row"
            )
            return (False, result)
        except AssertionError: raise
        except Exception:
            if rollback_on_error: conn.rollback()
            raise

    def WhenMatch (self, *to_update: ColumnWithValue | ColumnWithDefaultValue | AliasedExpression) -> Self:
        """Values to `Update`  
        `.WhenMatch(T.users.name.Value("Foo"), T.users.last_update.DEFAULT_VALUE)`"""
        if not to_update:
            raise ValueError("At least one value is required on Upsert().WhenMatch()")

        self.data_match.extend(to_update)
        return self

    def WhenNotMatch (self, *to_insert: ColumnWithValue | ColumnWithDefaultValue) -> Self:
        """Values to `Insert`  
        `.WhenNotMatch(T.users.name.Value("Foo"), T.users.last_update.DEFAULT_VALUE)`"""
        if not to_insert:
            raise ValueError("At least one value is required on Upsert().WhenNotMatch()")

        self.data_not_match.extend(to_insert)
        return self

__all__ = ["Upsert"]