# std
from typing import Literal
# internal
from simple_sql_builder.table import Table
from simple_sql_builder.expression import Expression

class Join:
    def __init__ (self, t: Literal["INNER", "LEFT", "RIGHT", "FULL"],
                        table: Table,
                        expression: Expression) -> None:
        self.t = t
        self.table = table
        self.expression = expression

    def __repr__(self) -> str:
        return f"<{self.t} JOIN for {self.table}>"

    def to_sql (self) -> str:
        return f"{self.t} JOIN {self.table.to_sql()} ON {self.expression.to_sql()}"

__all__ = ["Join"]