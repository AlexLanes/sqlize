"""Package to automatically handle `Connections` of drivers and execute `Statements`
- `Connection(conn)` Simplified wrapper to `DB API 2.0`
- `ResultSQL` `@dataclass` used by `cursor.execute() cursor.executemany() Connection.execute()`

Database         | Extra Dependency | Module
:--------------- | :--------------: | :----:
`SQLite`         | -                | `pysqlbuilder.connections.sqlite`
`MySQL`          | `[mysql]`        | `pysqlbuilder.connections.mysql`
`Oracle`         | `[oracle]`       | `pysqlbuilder.connections.oracle`
`PostgreSQL`     | `[postgresql]`   | `pysqlbuilder.connections.postgresql`
`MicrosoftSQL`   | `[mssql]`        | `pysqlbuilder.connections.mssql`
`ConnectionODBC` | `[odbc]`         | `pysqlbuilder.connections.odbc`
"""

from pysqlbuilder.connections.setup import Connection, ResultSQL