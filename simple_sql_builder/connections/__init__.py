"""Package to automatically handle `Connections` of drivers and execute `Statements`
- `Connection(conn)` Simplified wrapper to `DB API 2.0`
- `ResultSQL` return `@dataclass` of `cursor.execute()` and `cursor.executemany()`
#### SQLite Connection `simple_sql_builder.connections.sqlite`
#### ODBC Connection `simple_sql_builder.connections.odbc` optional dependency `[odbc]` needed
#### MySQL Connection `simple_sql_builder.connections.mysql` optional dependency `[mysql]` needed
#### PostgreSQL Connection `simple_sql_builder.connections.postgresql` optional dependency `[postgresql]` needed
#### MicrosoftSQL Connection `simple_sql_builder.connections.mssql` optional dependency `[mssql]` needed"""

from simple_sql_builder.connections.setup import Connection, ResultSQL