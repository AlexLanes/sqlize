# internal
from sqlize.column import Column, AliasedExpression, A
from sqlize.dml import Select
from sqlize.orm.interface import IModel
from sqlize.orm.exceptions import NotFoundError

class ModelSelect[T: IModel] (Select):

    model: type[T]

    def __init__ (self, *columns: Column | AliasedExpression, model: type[T]) -> None:
        self.model = model
        super().__init__(*columns)
        self.From(model.__data__.table)

    def All (self) -> list[T]:
        """Execute `Select` and get `All` rows"""
        model = self.model
        connection = self.model.GetConnection()
        return [
            model(line)
            for line in connection.execute(self)
        ]

    def First (self) -> T:
        """Execute `Select` and get `First` row
        - `NotFoundException`"""
        connection = self.model.GetConnection()
        if result := connection.execute(self):
            return self.model(result.first)
        raise NotFoundError(
            f"No Result for {self.model.__name__}.Select().First()",
            cls = self.model,
            values = {}
        )

    def Count (self) -> int:
        """Count total of rows of `Select`"""
        connection = self.model.GetConnection()
        result = connection.execute(
            Select(A.All().Count().As("total"))
            .From(self.AsCte("tmp_count_cte"))
        )
        return int(result.first["total"])

__all__ = ["ModelSelect"]