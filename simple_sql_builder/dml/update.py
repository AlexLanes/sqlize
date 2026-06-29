# std
from typing import Self, override
# internal
from simple_sql_builder.shared import SequenceAny
from simple_sql_builder.expression import Expression, to_sql
from simple_sql_builder.column import ColumnWithDefaultValue, AliasedExpression, ColumnEqualsValue
from simple_sql_builder.table import Table
from simple_sql_builder.supports import ExecutableStatement, SupportsReturning, SupportsWhere

class Update (ExecutableStatement, SupportsWhere, SupportsReturning):
    """Builder of `Update` Statement

    ## Example
    ```python
    from simple_sql_builder import E, A, T, Update, Connection

    # Simple Values
    a = T.actor
    update = (
        Update(a)
        .Set(a.first_name == "Foo", a.last_name == "Bar")
        .Where(a.actor_id == 1)
        .Returning(a.All()) # PostgreSQL, SQLite
        .Output(T.inserted.All()) # SQL Server
    )

    # Default + Expression
    update = (
        Update(a)
        .Set(
            a.actor_id.DEFAULT_VALUE,
            a.first_name == "Foo",
            a.last_name == "Bar",
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
    sql, params = update.to_sql()
    # Execute
    Connection(...).execute(select)
    ```
    """

    table: Table
    allow_empty_where: bool
    data_set: list[ColumnEqualsValue | ColumnWithDefaultValue | AliasedExpression]

    def __init__ (self, table: Table, *, allow_empty_where=False) -> None:
        super().__init__()
        self.table = table
        self.data_set = []
        self.allow_empty_where = allow_empty_where

    def __repr__ (self) -> str:
        return f"<UPDATE {self.table.to_table_name()!r} {len(self.data_set)} Columns(s)>"

    @override
    def to_sql (self) -> tuple[str, SequenceAny]:
        if not self.data_set:
            raise ValueError("Update().Set() should be called first")
        if not self.allow_empty_where and self.data_where is None:
            raise ValueError("Missing Update().Where(Expression)")

        params = []
        sets = list[str]()
        positional = self.parameter()
        for value in self.data_set:
            match value:

                case ColumnEqualsValue():
                    name = value.left.name
                    sets.append(f"{name} = {positional.next()}")
                    params.append(value.right)

                case ColumnWithDefaultValue():
                    name = value.column.name
                    sets.append(f"{name} = {value.to_sql().join()}")

                case AliasedExpression():
                    name = value.alias
                    sql = to_sql(value.expression, table_alias=False)
                    params.extend(sql)
                    parameterized = sql.join().format(*(positional.next() for _ in sql))
                    sets.append(f"{name} = {parameterized}")

                case _: raise TypeError(f"Invalid value found on Update.Set({value!r})")

        parts = [
            f"UPDATE {self.table.to_table_name()} SET",
            ",\n".join(sets),
        ]

        for data in (self.data_output, self.data_where, self.data_returning):
            if data is None: continue
            parameterized = (positional.next() for _ in data)
            parts.append(data.join().format(*parameterized))
            params.extend(data)

        return "\n".join(parts), params

    def Set (self, *value: ColumnEqualsValue | ColumnWithDefaultValue | AliasedExpression) -> Self:
        """Apply `SET {column} = {value}, ...`  
        `.Set(T.users.name == "Foo", T.users.id.DEFAULT_VALUE)`"""
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