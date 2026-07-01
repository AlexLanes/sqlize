"""`Connection` for `SQLite` database using std `sqlite3`"""

# std
from typing import Any
from os import PathLike
from sqlite3 import (
    connect as sq3_connect,
    Connection as sq3_Connection
)
# internal
from pysqlbuilder.shared import TableData, ColumnData
from pysqlbuilder.connections import Connection as C

class SQLite (C):
    """`Connection` for `SQLite` database using stdlib `sqlite3`
    - `SQLite(file_path)`
    - `SQLite.Memory()`"""

    conn: sq3_Connection

    def __init__ (self, file_path: str | PathLike[str] = "./database.sqlite", **kwargs: Any) -> None:
        self.conn = sq3_connect(str(file_path), **kwargs)
        self.set_parameter("?")

    @classmethod
    def Memory (cls, **kwargs: Any) -> "SQLite":
        connection = object.__new__(cls)
        connection.conn = sq3_connect(":memory:", **kwargs)
        return connection.set_parameter("?")

    def foreign_keys (self, enable: bool = True) -> "SQLite":
        """`Enable/Disable` Foreign Keys"""
        e = 'ON' if enable else 'OFF'
        self.conn.execute(f"PRAGMA foreign_keys = {e}")
        return self

    def optimize (self) -> None:
        """Run automatic database optimizations"""
        self.conn.execute("PRAGMA optimize")

    def vacuum (self) -> None:
        """Rebuild the database to reduce size and fragmentation"""
        self.conn.execute("VACUUM")

    def integrity_check (self) -> bool:
        """Check database integrity"""
        return (
            self.conn.execute("PRAGMA integrity_check")
            .fetchone()
            [0] == "ok"
        )

    def tables (self) -> list[TableData]:
        """List Tables and Views"""
        sql = """
            SELECT name, type = 'view' AS is_view
            FROM sqlite_master
            WHERE type IN ('table', 'view')
                AND name NOT LIKE 'sqlite_%'
            ORDER BY type, name
        """
        cursor = self.cursor()
        return [
            TableData(name = item["name"],
                      is_view = bool(item["is_view"]))
            for item in cursor.execute(sql).to_dict()
        ]

    def columns (self, table: str) -> list[ColumnData]:
        """List Columns of `table`"""
        cursor = self.cursor()
        return [
            ColumnData(
                name = item["name"],
                type = item["type"],
                is_nullable = item["pk"] != 1 and item["notnull"] == 0,
                has_default = item["dflt_value"] is not None,
            )
            for item in cursor.execute(f"PRAGMA table_info({table!r})").to_dict()
        ]

__all__ = ["SQLite"]