# std
from typing import override
# internal
from sqlize.shared import SequenceAny
from sqlize.table import Table
from sqlize.supports import ExecutableStatement, SupportsReturning, SupportsWhere
from sqlize.dml.interface import SQLizerModel

class Delete (ExecutableStatement, SupportsWhere, SupportsReturning):
    """Builder of `Delete` Statement

    ## Example
    ```python
    from sqlize import T, Delete, Connection

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

    def __init__ (self, table: Table | str | SQLizerModel, *, allow_empty_where=False) -> None:
        super().__init__()
        setattr(self, "allow_empty_where", allow_empty_where)
        match table:
            case str(): self.data.table = Table(table, None)
            case Table(): self.data.table = table
            case _ if isinstance(table.__table__, Table):
                self.data.table = table.__table__
            case _:
                self.data.table = Table(str(table.__table__), None)

    def __repr__ (self) -> str:
        assert self.data.table is not None
        return f"<DELETE FROM {self.data.table.to_table_name()!r}>"

    @override
    def to_sql (self) -> tuple[str, SequenceAny]:
        assert self.data.table is not None
        if self.data.where is None and not getattr(self, "allow_empty_where", False):
            raise ValueError("Missing Delete().Where(Expression)")

        params = []
        positional = self.data.parameter()
        parts = [f"DELETE FROM {self.data.table.to_table_name()}"]

        table_alias = False
        for data in (self.data.data_output(table_alias),
                     self.data.data_where(table_alias),
                     self.data.data_returning(table_alias)):
            if data is None: continue
            parameterized = (positional.next() for _ in data)
            parts.append(data.join().format(*parameterized))
            params.extend(data)

        return "\n".join(parts), params

__all__ = ["Delete"]