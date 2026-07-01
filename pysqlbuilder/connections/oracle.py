"""`Connection` for `Oracle` database using external `oracledb`
## Optional dependency `[oracle]` needed"""

# std
from __future__ import annotations
from typing import Any
# internal
from pysqlbuilder.shared import TableData, ColumnData
from pysqlbuilder.connections.setup import Connection as C
# external
try: import oracledb
except ImportError:
    raise ImportError("Optional dependency [oracle] needed to use 'pysqlbuilder.connections.oracle'")

class Oracle (C):
    """`Connection` for `Oracle Database` using external `oracledb`
    - `Oracle(user, password, dsn)`
    - `Oracle.Connect(...)`

    **Thin Mode** By default. Changed by **Oracle.SetThickMode()**"""

    conn: oracledb.Connection

    def __init__ (self, *, user: str, password: str, dsn: str, **kwargs: Any) -> None:
        self.conn = oracledb.connect(
            user = user,
            password = password,
            dsn = dsn,
            **kwargs,
        )
        self.set_parameter(":N", (True, '"'))

    @staticmethod
    def SetThickMode (lib_dir: str | None = None, **kwargs: Any) -> type[Oracle]:
        """Enable Oracle **Thick Mode**

        This method must be called before creating the first connection.  
        Thick Mode requires Oracle Client libraries **Oracle Instant Client** or
        **Full Oracle Client** to be installed.

        If not called, the driver uses **Thin Mode** automatically"""
        oracledb.init_oracle_client(lib_dir=lib_dir, **kwargs)
        return Oracle

    @classmethod
    def Connect (cls, *, host: str = "localhost",
                         port: int = 1521,
                         service_name: str | None = None,
                         sid: str | None = None,
                         user: str,
                         password: str,
                         **kwargs: Any) -> Oracle:
        if bool(service_name) + bool(sid) != 1:
            raise ValueError("Exactly one of 'service_name' or 'sid' must be informed")
        if service_name is not None:
            dsn = f"{host}:{port}/{service_name}"
        else:
            dsn = f"{host}:{port}:{sid}"

        connection = object.__new__(cls)
        connection.conn = oracledb.connect(
            user = user,
            password = password,
            dsn = dsn,
            **kwargs,
        )
        return connection.set_parameter(":N", (True, '"'))

    def tables (self, schema: str | None = None) -> list[TableData]:
        """List Tables and Views"""
        if schema is None:
            sql = """
                SELECT
                    OBJECT_NAME AS "name",
                    OWNER AS "schema",
                    CASE OBJECT_TYPE
                        WHEN 'VIEW' THEN TRUE
                        ELSE FALSE
                    END AS "is_view"
                FROM ALL_OBJECTS
                WHERE OWNER = SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') AND OBJECT_TYPE IN ('TABLE', 'VIEW')
                ORDER BY OBJECT_TYPE, OBJECT_NAME
            """
            params = []

        else:
            sql = """
                SELECT
                    OBJECT_NAME AS "name",
                    OWNER AS "schema",
                    CASE OBJECT_TYPE
                        WHEN 'VIEW' THEN TRUE
                        ELSE FALSE
                    END AS "is_view"
                FROM ALL_OBJECTS
                WHERE OWNER = :1 AND OBJECT_TYPE IN ('TABLE', 'VIEW')
                ORDER BY OBJECT_TYPE, OBJECT_NAME
            """
            params = [schema.upper()]

        return [
            TableData(**item)
            for item in self.cursor().execute(sql, params).to_dict()
        ]

    def columns (self, table: str, schema: str | None = None) -> list[ColumnData]:
        """List Columns Data of `table` and `schema`"""
        if schema is None:
            sql = """
                SELECT
                    COLUMN_NAME AS "name",
                    DATA_TYPE AS "type",
                    NULLABLE = 'Y' AS "is_nullable",
                    DATA_DEFAULT IS NOT NULL AS "has_default"
                FROM ALL_TAB_COLUMNS
                WHERE OWNER = SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') AND TABLE_NAME = :1
                ORDER BY COLUMN_ID
            """
            params = [table.upper()]

        else:
            sql = """
                SELECT
                    COLUMN_NAME AS "name",
                    DATA_TYPE AS "type",
                    NULLABLE = 'Y' AS "is_nullable",
                    DATA_DEFAULT IS NOT NULL AS "has_default"
                FROM ALL_TAB_COLUMNS
                WHERE OWNER = :1 AND TABLE_NAME = :2
                ORDER BY COLUMN_ID
            """
            params = [schema.upper(), table.upper()]

        return [
            ColumnData(**item)
            for item in self.cursor().execute(sql, params).to_dict()
        ]

__all__ = ["Oracle"]