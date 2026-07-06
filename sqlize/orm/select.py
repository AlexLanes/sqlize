# std
from typing import override
# internal
from sqlize.column import Column, AliasedColumn
from sqlize.statement import Select
from sqlize.orm.interface import IModel
from sqlize.orm.exceptions import NotFoundError

class ModelSelect[T: IModel] (Select):

    model: type[T]

    def __init__ (self, *columns: Column | AliasedColumn, model: type[T]) -> None:
        self.model = model
        super().__init__(*columns)
        self.data.table = model.__data__.table

    @override
    def From (self, table):
        raise NotImplementedError(f"This method shouldn't be called. Already set by {self.model.__name__}.Select()")

    def All (self) -> list[T]:
        """Execute `Select` and get `All` rows"""
        model = self.model
        connection = self.model.GetConnection()
        return [
            model(**line)
            for line in connection.execute(self)
        ]

    def First (self) -> T:
        """Execute `Select` and get `First` row
        - `NotFoundException`"""
        connection = self.model.GetConnection()
        if result := connection.execute(self):
            return self.model(**result.first)
        raise NotFoundError(
            f"No Result for {self.model.__name__}.Select().First()",
            cls = self.model,
            values = {}
        )

    def Count (self) -> int:
        """Count total of rows of `Select`"""
        table = self.data.table
        assert table

        connection = self.model.GetConnection()
        result = connection.execute(
            Select(table.Column("*").Count().As("total"))
            .From(self.AsCte("tmp_count_cte"))
        )

        return int(result.first["total"])

__all__ = ["ModelSelect"]