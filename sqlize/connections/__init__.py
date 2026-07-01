"""Package to automatically handle `Connections` of drivers and execute `Statements`
- `Connection(conn)` Simplified wrapper to `DB API 2.0`
- `ResultSQL` `@dataclass` used by `cursor.execute() cursor.executemany() Connection.execute()`

Database         | Extra Dependency | Module
:--------------- | :--------------: | :----:
`SQLite`         | -                | `sqlize.connections.sqlite`
`MySQL`          | `[mysql]`        | `sqlize.connections.mysql`
`Oracle`         | `[oracle]`       | `sqlize.connections.oracle`
`PostgreSQL`     | `[postgresql]`   | `sqlize.connections.postgresql`
`MicrosoftSQL`   | `[mssql]`        | `sqlize.connections.mssql`
`ConnectionODBC` | `[odbc]`         | `sqlize.connections.odbc`
"""

from sqlize.connections.setup import Connection, ResultSQL