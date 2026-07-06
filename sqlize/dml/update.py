# std
from typing import Self, override
# internal
from sqlize.shared import SequenceAny, SQLValue
from sqlize.expression import to_sql
from sqlize.column import ColumnWithDefaultValue, AliasedExpression, ColumnEqualsValue
from sqlize.table import Table
from sqlize.supports import ExecutableStatement, SupportsReturning, SupportsWhere
from sqlize.dml.interface import SQLizerModel

class Update (ExecutableStatement, SupportsWhere, SupportsReturning):
    """Builder of `Update` Statement

    ## Example
    ```python
    from sqlize import E, A, T, Update, Connection

    # Simple Values
    a = T.actor
    update = (
        Update(a)
        .Set(a.first_name == "Foo", last_name="Bar")
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

    data_set: list[ColumnEqualsValue | ColumnWithDefaultValue | AliasedExpression]

    def __init__ (self, table: Table | str | SQLizerModel, *, allow_empty_where=False) -> None:
        super().__init__()
        self.data_set = []
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
        return f"<UPDATE {self.data.table.to_table_name()!r} {len(self.data_set)} Columns(s)>"

    @override
    def to_sql (self) -> tuple[str, SequenceAny]:
        assert self.data.table is not None
        if not self.data_set:
            raise ValueError("Update().Set() should be called first")
        if self.data.where is None and not getattr(self, "allow_empty_where", False):
            raise ValueError("Missing Update().Where(Expression)")

        params = []
        sets = list[str]()
        positional = self.data.parameter()
        for value in self.data_set:
            match value:

                case ColumnEqualsValue():
                    name = value.left.quote_name(self.data.quote_info)
                    sets.append(f"{name} = {positional.next()}")
                    params.append(value.right)

                case ColumnWithDefaultValue():
                    name = value.column.quote_name(self.data.quote_info)
                    sets.append(f"{name} = {value.to_sql().join()}")

                case AliasedExpression():
                    name = value.quote_alias(self.data.quote_info)
                    sql = to_sql(value.expression, table_alias=False, quote_info=self.data.quote_info)
                    params.extend(sql)
                    parameterized = sql.join().format(*(positional.next() for _ in sql))
                    sets.append(f"{name} = {parameterized}")

                case _: raise TypeError(f"Invalid value found on Update().Set({value!r})")

        parts = [
            f"UPDATE {self.data.table.to_table_name()} SET",
            ",\n".join(sets),
        ]

        table_alias = False
        for data in (self.data.data_output(table_alias),
                     self.data.data_where(table_alias),
                     self.data.data_returning(table_alias)):
            if data is None: continue
            parameterized = (positional.next() for _ in data)
            parts.append(data.join().format(*parameterized))
            params.extend(data)

        return "\n".join(parts), params

    def Set (self, *column: ColumnEqualsValue | ColumnWithDefaultValue | AliasedExpression, **columns: SQLValue) -> Self:
        """Apply `SET {column} = {value}, ...`  
        `.Set(T.users.name == "Foo", T.users.id.DEFAULT_VALUE)`  
        `.Set(name="Foo", id=1)`"""
        assert self.data.table
        if not column and not columns:
            raise ValueError("At least one value is required on Update().Set()")

        self.data_set.extend(column)
        self.data_set.extend(
            ColumnEqualsValue(self.data.table.Column(column), "=", value)
            for column, value in columns.items()
        )
        return self

__all__ = ["Update"]