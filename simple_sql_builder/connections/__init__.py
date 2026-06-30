"""Package to automatically handle `Connections` of drivers and execute `Statements`
- `Connection(conn)` Simplified wrapper to `DB API 2.0`
- `ResultSQL` `@dataclass` used by `cursor.execute() cursor.executemany() Connection.execute()`

Database         | Extra Dependency | Module
:--------------- | :--------------: | :----:
`SQLite`         | -                | `simple_sql_builder.connections.sqlite`
`MySQL`          | `[mysql]`        | `simple_sql_builder.connections.mysql`
`Oracle`         | `[oracle]`       | `simple_sql_builder.connections.oracle`
`PostgreSQL`     | `[postgresql]`   | `simple_sql_builder.connections.postgresql`
`MicrosoftSQL`   | `[mssql]`        | `simple_sql_builder.connections.mssql`
`ConnectionODBC` | `[odbc]`         | `simple_sql_builder.connections.odbc`
"""

from simple_sql_builder.connections.setup import Connection, ResultSQL