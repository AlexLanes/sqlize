"""Package to automatically handle `Connections` of drivers and execute `Statements`
- `Connection(conn)` Simplified wrapper to `DB API 2.0`
- `ResultSQL` `@dataclass` used by `cursor.execute() cursor.executemany() Connection.execute()`

Database         | Extra Dependency     | Module
:--------------- | :------------------: | :----:
`SQLite`         | -                    | `sqlize.connections.sqlite`
`MySQL`          | `sqlize[mysql]`      | `sqlize.connections.mysql`
`Oracle`         | `sqlize[oracle]`     | `sqlize.connections.oracle`
`PostgreSQL`     | `sqlize[postgresql]` | `sqlize.connections.postgresql`
`MicrosoftSQL`   | `sqlize[mssql]`      | `sqlize.connections.mssql`
`ConnectionODBC` | `sqlize[odbc]`       | `sqlize.connections.odbc`
"""

from sqlize.connections.setup import Connection, ResultSQL