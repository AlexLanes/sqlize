"""Package to automatically handle Connections of drivers and execute `Statements`
- `Connection(conn)` Simplified wrapper to `DB API 2.0`
- `ResultSQL` return `@dataclass` of `cursor.execute()` and `cursor.executemany()`"""

from simple_sql_builder.connections.setup import Connection, ResultSQL