# std
from __future__ import annotations
import itertools, string
from typing import Generator
from dataclasses import dataclass
# internal
from sqlize.column import Column, ESPECIAL_TABLES

def gen () -> Generator[str, None, None]:
    c_cycle = itertools.cycle(string.ascii_lowercase)
    c, n = next(c_cycle), 1
    while True:
        yield f"{c}{n}"
        if n == 9:
            c = next(c_cycle)
            n = 1
        else: n += 1
table_alias_generator = gen()

TABLE_CACHE = dict[str | None, dict[str, "Table"]]()
"""`{ schema: { table_name: Table }}`"""

@dataclass
class TableData:
    name: str
    alias: str
    schema: str | None

class Table:

    _td_: TableData

    def __init__ (self, name: str, schema: str | None) -> None:
        self._td_ = (
            TableData(name, next(table_alias_generator), schema)
            if name.lower() not in ESPECIAL_TABLES
            else TableData(name, name, schema)
        )
        if schema not in TABLE_CACHE:
            TABLE_CACHE[schema] = {}
        TABLE_CACHE[schema][name] = self

    def __repr__ (self) -> str:
        return f"<Table {self.to_table_sql()}>"

    def to_table_name (self) -> str:
        """`SQL: [schema.]table` version"""
        name = self._td_.name
        schema = self._td_.schema
        return f"{schema}.{name}" if schema else name

    def to_table_sql (self) -> str:
        """`SQL: [schema.]table alias` version"""
        return f"{self.to_table_name()} {self._td_.alias}"

    def Schema (self, schema: str) -> Table:
        """Apply `schema.table`"""
        if (s := TABLE_CACHE.get(schema)) and (t := s.get(self._td_.name)):
            return t

        if schema not in TABLE_CACHE:
            TABLE_CACHE[schema] = {}
        TABLE_CACHE[schema][self._td_.name] = self

        self._td_.schema = schema
        return self

    #--------#
    # Column #
    #--------#

    def __getattr__ (self, name: str) -> Column:
        return self.Column(name)

    def All (self) -> Column:
        """Create column `*` for `table`"""
        return Column("*", self._td_.alias)

    def Column (self, name: str) -> Column:
        """Create column `name` for `table`
        - Same as `table.column_name`"""
        return Column(name, self._td_.alias)

class TableBuilder:
    def __call__ (self, table_name: str, schema: str | None) -> Table:
        if (s := TABLE_CACHE.get(schema)) and (t := s.get(table_name)):
            return t
        return Table(table_name, schema)

    def __getattr__ (self, table_name: str) -> Table:
        return self.__call__(table_name, None)

T = TableBuilder()
"""Creator of `Table`

### Creating Table
`users = T.users`  
`T("users", "public")`  
`T.users.Schema("public")`

### Creating Column
`users.id`  
`users.All()`  
`T.users.Column("name")`  
`users.email.As("e-mail")`
"""

__all__ = ["Table", "T"]