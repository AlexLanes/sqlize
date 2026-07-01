"""Generic `Connection` using external `pyodbc`
## Optional dependency `[odbc]` needed"""

# std
from typing import Any, override
# internal
from sqlize.shared import (
    TableData, ColumnData,
    ManySequenceAny, SequenceAny,
)
from sqlize.connections.setup import (
    Connection as C,
    Cursor, ResultSQL,
    ExecutableStatement
)
# external
try: from pyodbc import (
    connect as pyodbc_connect,
    Connection as pyodbc_Connection,
    drivers
)
except ImportError: raise ImportError(
    "Optional dependency [odbc] needed to use "
    "'sqlize.connections.odbc'"
)

class CursorODBC (Cursor):
    @override
    def executemany (self, sql: str, params: ManySequenceAny, **kwargs) -> ResultSQL:
        try:
            rowcount = 0
            rows = list[SequenceAny]()
            columns = tuple[str, ...]()

            for p in params:
                self.cursor.execute(sql, p)
                if not columns: columns = self.columns
                if columns: rows.extend([tuple(line) for line in self.cursor])
                rowcount += self.rowcount

            return ResultSQL(rowcount, len(rows), columns, rows)

        finally:
            self.close()

class ConnectionODBC (C):
    """Generic ODBC `Connection` using external `pyodbc`
    - Works on any database with `ODBC Driver` installed

    ## Examples
    ```python
    ConnectionODBC.PrintDrivers()
    ConnectionODBC(
        "Driver={ODBC Driver 18 for SQL Server};"
        "Server=localhost;"
        "Database=test;"
        "UID=sa;"
        "PWD=password;"
        "TrustServerCertificate=yes;"
    )
    ConnectionODBC.Connect(
        driver="{ODBC Driver 18 for SQL Server}",
        server="localhost",
        database="master",
        user="sa",
        password="password",
        TrustServerCertificate="yes",
    )
    ConnectionODBC.Connect(
        driver="PostgreSQL Unicode(x64)",
        server="localhost",
        user="postgres",
        password="admin",
        database="postgres",
    )
    ```
    """

    conn: pyodbc_Connection

    def __init__ (self, connection_string: str, **kwargs: Any) -> None:
        kwargs = { "timeout": 5, **kwargs }
        self.conn = pyodbc_connect(connection_string, **kwargs)
        self.set_parameter("?")

    @classmethod
    def Connect (cls, driver: str,
                      timeout = 5,
                      encoding = "utf-16le",
                      server: str | None = None,
                      database: str | None = None,
                      user: str | None = None,
                      password: str | None = None,
                      **kwargs: Any) -> "ConnectionODBC":
        connection = object.__new__(cls)
        connection_string = ";".join(
            f"{key}={value}"
            for key, value in {
                "driver": driver,
                "server": server,
                "database": database,
                "uid": user,
                "pwd": password,
                **kwargs
            }.items()
            if value is not None
        )
        connection.conn = pyodbc_connect(connection_string, timeout=timeout, encoding=encoding)
        return connection.set_parameter("?")

    @staticmethod
    def PrintDrivers () -> None:
        """Print the names of all available ODBC drivers"""
        print(*sorted(drivers()), sep="\n")

    def tables (self, schema: str | None = None) -> list[TableData]:
        """List Tables Data of Database using ODBC metadata"""
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
        """List Columns Data of `table` and `schema` using ODBC metadata"""
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

    @override
    def cursor (self) -> CursorODBC:
        """`cursor.executemany()` is a `for` `cursor.execute()` loop due to limitation on `pyodbc`"""
        return CursorODBC(self.conn.cursor()) # type: ignore

    @override
    def execute (self, statement: ExecutableStatement, **kwargs) -> ResultSQL:
        """Execute `SQL: Statement`
        - `cursor.executemany()` is a `for` `cursor.execute()` loop due to limitation on `pyodbc`
        - `cursor.executemany()` auto rollback on `Exception`"""
        sql, params = (
            statement
            .set_parameter(self.parameter, self.quote_info)
            .to_sql()
        )

        cursor = self.cursor()
        if params and isinstance(params[0], (list, tuple)):
            try: return cursor.executemany(sql, params)
            except Exception:
                self.rollback()
                raise
        return cursor.execute(sql, params)

__all__ = ["ConnectionODBC"]