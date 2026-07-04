# std
from typing import Callable
# internal
from sqlize.shared import SQLValue
from sqlize.table import Table
from sqlize.dml import Insert, Select
from sqlize.connections import Connection
from sqlize.orm.interface import IModel
from sqlize.orm.select import ModelSelect
from sqlize.orm.exceptions import PrimaryKeyNotSetError

class ModelInsert[T: IModel]:

    model: type[T]
    connection: Connection

    def __init__ (self, model: type[T]) -> None:
        self.model = model
        self.connection = model.GetConnection()

    def module_router (self) -> Callable[[dict[str, SQLValue]], T]:
        *_, connection_name = map(str.lower, self.connection.__module__.split("."))
        match connection_name:
            case "sqlite" | "postgresql": return self.insert_returning
            case "mssql": return self.insert_output
            case "mysql": return self.insert_mysql
            case _: return self.insert_default

    def insert_for_connection (self, insert: dict[str, SQLValue]) -> T:
        func = self.module_router()
        return func(insert)

    def insert_returning (self, insert: dict[str, SQLValue]) -> T:
        model = self.model
        data = model.__data__
        result = self.connection.execute(
            Insert(data.table)
            .Values(**{
                info.column.name: insert[name]
                for name, info in data.infos.items()
                if name in insert
            })
            .Returning(*data.all_columns)
        )
        assert result, "Unexpected ResultSQL after Insert, no rowcount or rows returned"
        return model(**result.first)

    def insert_output (self, insert: dict[str, SQLValue]) -> T:
        model = self.model
        data = model.__data__
        inserted = Table("inserted", None)
        result = self.connection.execute(
            Insert(data.table)
            .Values(**{
                info.column.name: insert[name]
                for name, info in data.infos.items()
                if name in insert
            })
            .Output(*(
                inserted.Column(column.name)
                for column in data.all_columns
            ))
        )
        assert result, "Unexpected ResultSQL after Insert, no rowcount or rows returned"
        return model(**result.first)

    def insert_mysql (self, insert: dict[str, SQLValue]) -> T:
        from sqlize.connections.mysql import MySQL
        connection = MySQL.GetInstance()

        model = self.model
        data = model.__data__
        pk = data.primary_key

        result = connection.execute(
            Insert(data.table)
            .Values(**{
                info.column.name: insert[name]
                for name, info in data.infos.items()
                if name in insert
            })
        )
        assert result, "Unexpected ResultSQL after Insert, no rowcount returned"

        # PrimaryKey
        if (lastrowid := connection.lastrowid):
            if pk is None:
                raise PrimaryKeyNotSetError(f"Expected a PrimaryKey for {model.__name__}", obj=model)
            result = connection.execute(
                Select(*data.all_columns)
                .From(data.table)
                .Where(pk == lastrowid)
            )
            assert result, f"Unexpected ResultSQL after Insert. AUTO_INCREMENT {lastrowid} not found for {model.__name__}.{data.alias.get(pk.name, pk.name)}"
            return model(**result.first)

        # Get Last by Values Inserted
        select = (
            ModelSelect(*data.all_columns, model=model)
            .WhereEquals(*(
                info.column == insert[name]
                for name, info in data.infos.items()
                if name in insert
            ))
        )
        total = select.Count()
        return select.Offset(total - 1).First()

    def insert_default (self, insert: dict[str, SQLValue]) -> T:
        model = self.model
        data = model.__data__
        result = self.connection.execute(
            Insert(data.table)
            .Values(**{
                info.column.name: insert[name]
                for name, info in data.infos.items()
                if name in insert
            })
        )
        assert result, "Unexpected ResultSQL after Insert, no rowcount returned"

        # Get Last by Values Inserted
        return (
            ModelSelect(*data.all_columns, model=model)
            .WhereEquals(*(
                info.column == insert[name]
                for name, info in data.infos.items()
                if name in insert
            ))
            .All()
            [-1]
        )

__all__ = ["ModelInsert"]