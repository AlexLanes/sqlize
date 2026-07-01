"""`Connection` for `Microsoft SQL Server` database using external `mssql-python`
## Optional dependency `[mssql]` needed"""

# std
from typing import Any
# internal
from pysqlbuilder.shared import TableData, ColumnData
from pysqlbuilder.connections import Connection as C
# external
try: from mssql_python import (
    connect as mssql_connect,
    Connection as mssql_Connection,
)
except ImportError:
    raise ImportError("Optional dependency [mssql] needed to use 'pysqlbuilder.connections.mssql'")

class MicrosoftSQL (C):
    """`Connection` for `Microsoft SQL Server` using external `mssql-python`
    - `MicrosoftSQL(connection_string)`
    - `MicrosoftSQL.Connect(...)`"""

    conn: mssql_Connection

    def __init__ (self, connection_string: str, **kwargs: Any) -> None:
        kwargs = { "timeout": 5, **kwargs }
        self.conn = mssql_connect(connection_string, **kwargs)
        self.set_parameter("?", (False, "["))

    @classmethod
    def Connect (cls, *, server: str = "localhost",
                         database: str | None = "master",
                         user: str | None = None,
                         password: str | None = None,
                         timeout: int = 5,
                         encrypt: bool | None = None,
                         trusted_connection: bool | None = None,
                         trusted_server_certificate: bool | None = None,
                         **kwargs: Any) -> "MicrosoftSQL":
        connection = object.__new__(cls)
        bools = { None: None, True: "yes", False: "no" }
        connection_string = ";".join(
            f"{key}={value}"
            for key, value in {
                "server": server,
                "database": database,
                "uid": user,
                "pwd": password,
                "encrypt": bools[encrypt],
                "Trusted_Connection": bools[trusted_connection],
                "TrustServerCertificate": bools[trusted_server_certificate],
                **kwargs,
            }.items()
            if value is not None
        )
        connection.conn = mssql_connect(connection_string, timeout=timeout)
        return connection.set_parameter("?", (False, "["))

    def tables (self, schema: str | None = None) -> list[TableData]:
        """List Tables Data of Database"""
        return [
            TableData(
                name = row.table_name,
                schema = row.table_schem,
                is_view = str(row.table_type).upper() == "VIEW",
            )
            for row in self.conn.cursor().tables(schema=schema)
            if str(row.table_type).upper() in {"TABLE", "VIEW"}
        ]

    def columns (self, table: str, schema: str | None = None) -> list[ColumnData]:
        """List Columns Data of `table` and `schema`"""
        rows = self.conn.cursor().columns(table=table, schema=schema)
        return [
            ColumnData(
                name = row.column_name,
                type = row.type_name,
                is_nullable = bool(row.nullable),
                has_default = row.column_def is not None,
            )
            for row in rows
        ]

__all__ = ["MicrosoftSQL"]