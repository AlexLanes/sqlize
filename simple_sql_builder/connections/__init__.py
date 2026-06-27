"""Package to automatically handle `Connections` of drivers and execute `Statements`
- `Connection(conn)` Simplified wrapper to `DB API 2.0`
- `ResultSQL` return `@dataclass` of `cursor.execute()` and `cursor.executemany()`
### Optional dependency `[postgresql]` needed to use `simple_sql_builder.connections.postgresql`"""

from simple_sql_builder.connections.setup import Connection, ResultSQL