# std
from __future__ import annotations
import itertools, string
from typing import Generator
# internal
from simple_sql_builder.column import Column

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

class Table:

    __name: str
    __table_alias: str
    __schema: str | None

    def __init__ (self, name: str, schema: str | None) -> None:
        if name.startswith("__"):
            raise ValueError(f"Table({name}) should not start with '__'")

        self.__name = name
        self.__schema = schema
        self.__table_alias = next(table_alias_generator)

        if schema not in TABLE_CACHE:
            TABLE_CACHE[schema] = {}
        TABLE_CACHE[schema][name] = self

    def __repr__ (self) -> str:
        return f"<Table {self.to_sql()}>"

    def to_sql (self) -> str:
        """`SQL: [schema.]table alias` version"""
        sql = f"{self.__name} {self.__table_alias}"
        return f"{self.__schema}.{sql}" if self.__schema else sql

    def Schema (self, schema: str) -> Table:
        """Apply `schema.table`"""
        if (s := TABLE_CACHE.get(schema)) and (t := s.get(self.__name)):
            return t

        if schema not in TABLE_CACHE:
            TABLE_CACHE[schema] = {}
        TABLE_CACHE[schema][self.__name] = self

        self.__schema = schema
        return self

    #--------#
    # Column #
    #--------#

    def __getattr__ (self, name: str) -> Column:
        return self.Column(name)

    def All (self) -> Column:
        """Create column `*` for `table`"""
        return Column("*", self.__table_alias)

    def Column (self, name: str) -> Column:
        """Create column `name` for `table`
        - Same as `table.column_name`"""
        return Column(name, self.__table_alias)

class TableBuilder:
    def __call__ (self, table_name: str, schema: str | None) -> Table:
        if (s := TABLE_CACHE.get(schema)) and (t := s.get(table_name)):
            return t
        return Table(table_name, schema)

    def __getattr__ (self, table_name: str) -> Table:
        return self.__call__(table_name, None)

T = TableBuilder()
"""Creator of `Table`

```python
# Creating table
users = T.users
T("users", "public")
T.users.Schema("public")

# Creating columns
users.id
users.All()
T.users.column("name")
users.email.As("e-mail")
```
"""
__all__ = ["T"]