"""`Connection` for `MySQL` database using external `PyMySQL`
## Optional dependency `[mysql]` needed"""

# std
from typing import Any, override
# internal
from simple_sql_builder.shared import ManySequenceAny, SequenceAny, TableData, ColumnData
from simple_sql_builder.connections.setup import Connection as C, Cursor, ResultSQL
# external
try:
    from pymysql import connect as pymysql_connect, Connection as pymysql_Connection
    from pymysql.cursors import Cursor as pymysql_Cursor
except ImportError:
    raise ImportError("Optional dependency [mysql] needed to use 'simple_sql_builder.connections.mysql'")

class MyCursor (Cursor):

    cursor: pymysql_Cursor

    @override
    def execute (self, sql: str, params: SequenceAny | None = None, **kwargs) -> ResultSQL:
        self.cursor.execute(sql, params)

        columns = self.columns
        rows = list[SequenceAny](row for row in self.cursor) if columns else []
        rowcount = self.rowcount

        self.close()
        return ResultSQL(rowcount, len(rows), columns, rows)

    @override
    def executemany (self, sql: str, params: ManySequenceAny, **kwargs) -> ResultSQL:
        self.cursor.executemany(sql, params)

        columns = self.columns
        rows = list[SequenceAny](row for row in self.cursor) if columns else []
        rowcount = self.rowcount

        self.close()
        return ResultSQL(rowcount, len(rows), columns, rows)

class MySQL (C):
    """`Connection` for `MySQL` database using external `PyMySQL`
    - `MySQL(host=..., user=..., password=..., database=...)`"""

    conn: pymysql_Connection

    def __init__ (self, *, host: str = "localhost",
                          port: int = 3306,
                          user: str | None = None,
                          password: str | None = None,
                          database: str | None = None,
                          connect_timeout: int = 5,
                          **kwargs: Any) -> None:
        self.conn = pymysql_connect(
            host=host,
            port=port,
            user=user,
            password=password or "",
            database=database,
            connect_timeout=connect_timeout,
            **kwargs,
        )
        self.set_parameter("%s", (False, "`"))

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
                    is_nullable = 'YES' AS is_nullable,
                    column_default IS NOT NULL AS has_default
                FROM information_schema.columns
                WHERE table_schema = DATABASE()
                    AND table_name = %s
                ORDER BY ordinal_position
            """
            params: SequenceAny = (table,)
        else:
            sql = """
                SELECT
                    column_name AS name,
                    data_type AS type,
                    is_nullable = 'YES' AS is_nullable,
                    column_default IS NOT NULL AS has_default
                FROM information_schema.columns
                WHERE table_schema = %s
                    AND table_name = %s
                ORDER BY ordinal_position
            """
            params = (schema, table)

        return [
            ColumnData(**{
                "name": item["name"],
                "type": item["type"],
                "is_nullable": item["is_nullable"] == 1,
                "has_default": item["has_default"] == 1,
            })
            for item in self.cursor().execute(sql, params).to_dict()
        ]

    @override
    def cursor (self) -> Cursor:
        return MyCursor(self.conn.cursor()) # type: ignore

__all__ = ["MySQL"]