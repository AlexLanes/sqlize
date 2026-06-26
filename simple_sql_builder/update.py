# std
from __future__ import annotations
from typing import Self, override
# internal
from .shared import SequenceAny
from .expression import Expression, to_sql
from .column import ColumnWithValue, ColumnWithDefaultValue, AliasedExpression
from .table import Table
from .supports import ExecutableStatement, SupportsReturning, SupportsWhere

class Update (ExecutableStatement, SupportsWhere, SupportsReturning):
    """Builder of `Update` Statement

    ## Example
    ```python
    from simple_sql_builder import E, A, T, Update
    a = T.actor

    # Simple Values
    update = (
        Update(a)
        .Set(a.first_name.Value("Bar"), a.last_name.Value("Foo"))
        .Where(a.actor_id == 1)
        .Returning(A.All())
    )

    # Default + Expression
    update = (
        Update(a)
        .Set(
            a.actor_id.DEFAULT_VALUE,
            a.first_name.Value("Bar"),
            a.last_name.Value("Foo"),
            E.CURRENT_TIMESTAMP.As("last_update")
        )
        .Where(a.actor_id == None)
        .Returning(
            A.All(),
            a.actor_id.Cast("TEXT").As("id_as_text"),
            (a.first_name.Length() + a.last_name.Length()).As("full_name_length")
        )
    )

    # Transform
    sql, params = update.to_sql(allow_empty_where=False)
    ```
    """

    table: Table
    data_set: list[ColumnWithValue | ColumnWithDefaultValue | AliasedExpression]

    def __init__ (self, table: Table) -> None:
        super().__init__()
        self.table = table
        self.data_set = []

    def __repr__ (self) -> str:
        return f"<UPDATE {self.table.to_table_name()!r} {len(self.data_set)} Columns(s)>"

    @override
    def to_sql (self, *, allow_empty_where=False) -> tuple[str, SequenceAny]:
        if not self.data_set:
            raise ValueError("Update().Set() should be called first")
        if not allow_empty_where and self.data_where is None:
            raise ValueError("Missing Update().Where(Expression)")

        params = []
        sets = list[str]()
        positional = self.parameter()
        for value in self.data_set:
            match value:

                case ColumnWithValue():
                    name = value.column.name
                    sets.append(f"{name} = {positional.next()}")
                    params.extend(value.values)

                case ColumnWithDefaultValue():
                    name = value.column.name
                    sets.append(f"{name} = {value.to_sql().join()}")

                case AliasedExpression():
                    name = value.alias
                    sql = to_sql(value.expression)
                    params.extend(sql)
                    parameterized = sql.join().format(*(positional.next() for _ in sql))
                    sets.append(f"{name} = {parameterized}")

                case _: raise TypeError(f"Invalid value found on Update.Set({value!r})")

        parts = [
            f"UPDATE {self.table.to_table_name()} SET",
            ",\n".join(sets),
        ]

        for wr in (self.data_where, self.data_returning):
            if wr is None: continue
            parameterized = (positional.next() for _ in wr)
            parts.append(wr.join().format(*parameterized))
            params.extend(wr)

        return "\n".join(parts), params

    def Set (self, *value: ColumnWithValue | ColumnWithDefaultValue | AliasedExpression) -> Self:
        """Apply `SET {column} = {value}, ...`  
        `.Set(T.users.id.DEFAULT_VALUE, T.users.name.Value("Bar"))`"""
        if not value:
            raise ValueError("At least one value is required on Update().Set()")

        self.data_set.extend(value)
        return self

    @override
    def Where (self, expression: Expression) -> Self:
        sql = expression.to_sql(table_alias=False)
        sql.sqls.insert(0, "WHERE")
        self.data_where = sql
        return self

__all__ = ["Update"]