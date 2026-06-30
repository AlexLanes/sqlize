# std
from typing import Self, override
# internal
from simple_sql_builder.shared import SequenceAny
from simple_sql_builder.expression import Expression
from simple_sql_builder.table import Table
from simple_sql_builder.supports import ExecutableStatement, SupportsReturning, SupportsWhere

class Delete (ExecutableStatement, SupportsWhere, SupportsReturning):
    """Builder of `Delete` Statement

    ## Example
    ```python
    from simple_sql_builder import T, Delete, Connection

    a = T.actor
    delete = (
        Delete(a, allow_empty_where=False)
        .Where(a.actor_id == 11)
        .Returning(a.All()) # PostgreSQL, SQLite
        .Output(T.deleted.All()) # SQL Server
    )

    # Transform
    sql, params = delete.to_sql()
    # Execute
    Connection(...).execute(select)
    ```
    """

    table: Table
    allow_empty_where: bool

    def __init__ (self, table: Table, *, allow_empty_where=False) -> None:
        super().__init__()
        self.table = table
        self.allow_empty_where = allow_empty_where

    def __repr__ (self) -> str:
        return f"<DELETE FROM {self.table.to_table_name()!r}>"

    @override
    def to_sql (self) -> tuple[str, SequenceAny]:
        if not self.allow_empty_where and self.data_where is None:
            raise ValueError("Missing Delete().Where(Expression)")

        params = []
        positional = self.parameter()
        parts = [f"DELETE FROM {self.table.to_table_name()}"]

        for data in (self.data_output, self.data_where, self.data_returning):
            if data is None: continue
            parameterized = (positional.next() for _ in data)
            parts.append(data.join().format(*parameterized))
            params.extend(data)

        return "\n".join(parts), params

    @override
    def Where (self, expression: Expression) -> Self:
        sql = expression.to_sql(table_alias=False, quote_info=self.quote_info)
        sql.sqls.insert(0, "WHERE")
        self.data_where = sql
        return self

__all__ = ["Delete"]