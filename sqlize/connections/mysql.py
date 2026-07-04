"""`Connection` for `MySQL` database using external `mysql-connector-python`
## Optional dependency `[mysql]` needed"""

# std
from typing import Any, override
# internal
from sqlize.shared import SequenceAny, TableData, ColumnData
from sqlize.connections.setup import Connection as C, Cursor
# external
try:
    from mysql.connector import connect
    from mysql.connector.cursor import MySQLCursor as cursorSQL
    from mysql.connector.connection import MySQLConnection as connection
except ImportError:
    raise ImportError("Optional dependency [mysql] needed to use 'sqlize.connections.mysql'")

class CursorSQL (Cursor):

    cursor: cursorSQL

    @override
    def close (self) -> None:
        setattr(MySQL, "_lastrowid", self.lastrowid)
        return super().close()

    @property
    def lastrowid (self) -> int | None:
        """First `AUTO_INCREMENT` value after an `INSERT` or `UPDATE`"""
        return self.cursor.lastrowid or None

class MySQL (C):
    """`Connection` for `MySQL` database using external `mysql-connector-python`
    - `MySQL(host=..., user=..., password=..., database=...)`"""

    conn: connection

    def __init__ (self, *, host: str = "localhost",
                           port: int = 3306,
                           user: str | None = None,
                           password: str | None = None,
                           database: str | None = None,
                           connect_timeout: int = 5,
                           **kwargs: Any) -> None:
        conn = connect(
            host = host,
            port = port,
            user = user,
            password = password or "",
            database = database,
            connect_timeout = connect_timeout,
            **kwargs,
        )
        assert isinstance(conn, connection), "Pool of MySQL not supported"
        self.conn = conn
        self.set_parameter("%s", (False, "`"))

    @property
    def lastrowid (self) -> int | None:
        """First `AUTO_INCREMENT` value after an `INSERT` or `UPDATE`"""
        return getattr(MySQL, "_lastrowid", None)

    def tables (self, schema: str | None = None) -> list[TableData]:
        """List Tables Data of Database"""
        if schema is None:
            sql = """
                SELECT TABLE_NAME, TABLE_SCHEMA, TABLE_TYPE = 'VIEW' AS is_view
                FROM information_schema.tables
                WHERE TABLE_SCHEMA = DATABASE()
                    AND TABLE_TYPE IN ('BASE TABLE', 'VIEW')
                ORDER BY TABLE_TYPE, TABLE_NAME
            """
            params = ()
        else:
            sql = """
                SELECT TABLE_NAME, TABLE_SCHEMA, TABLE_TYPE = 'VIEW' AS is_view
                FROM information_schema.tables
                WHERE TABLE_SCHEMA = %s
                    AND TABLE_TYPE IN ('BASE TABLE', 'VIEW')
                ORDER BY TABLE_TYPE, TABLE_NAME
            """
            params = (schema,)

        return [
            TableData(
                name = item["TABLE_NAME"],
                schema = item["TABLE_SCHEMA"],
                is_view = item["is_view"] == 1,
            )
            for item in self.cursor().execute(sql, params)
        ]

    def columns (self, table: str, schema: str | None = None) -> list[ColumnData]:
        """List Columns Data of `table` and `schema`"""
        if schema is None:
            sql = """
                SELECT
                    column_name AS name,
                    data_type AS type,
                    column_key = 'PRI' AS is_pk,
                    is_nullable = 'YES' AS is_nullable,
                    column_default IS NOT NULL AS has_default
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position
            """
            params: SequenceAny = (table,)
        else:
            sql = """
                SELECT
                    column_name AS name,
                    data_type AS type,
                    column_key = 'PRI' AS is_pk,
                    is_nullable = 'YES' AS is_nullable,
                    column_default IS NOT NULL AS has_default
                FROM information_schema.columns
                WHERE table_schema = %s
                    AND table_name = %s
                ORDER BY ordinal_position;
            """
            params = (schema, table)

        return [
            ColumnData(**{
                "name": item["name"],
                "type": item["type"],
                "is_pk": item["is_pk"],
                "is_nullable": item["is_nullable"] == 1,
                "has_default": item["has_default"] == 1,
            })
            for item in self.cursor().execute(sql, params).to_dict()
        ]

    @override
    def cursor (self) -> CursorSQL:
        return CursorSQL(self.conn.cursor()) # type: ignore

__all__ = ["MySQL"]