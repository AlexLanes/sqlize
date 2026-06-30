"""`Connection` for `PostgreSQL` database using external `psycopg[binary]`
## Optional dependency `[postgresql]` needed"""

# std
from typing import Any, override
# internal
from simple_sql_builder.shared import SequenceAny, TableData, ColumnData
from simple_sql_builder.supports import ExecutableStatement
from simple_sql_builder.connections import Connection as C, ResultSQL
# external
try: from psycopg import (
    connect as psycopg_connect,
    Connection as psycopg_Connection
)
except ImportError:
    raise ImportError("Optional dependency [postgresql] needed to use 'simple_sql_builder.connections.postgresql'")

class PostgreSQL (C):
    """`Connection` for `PostgreSQL` database using external `psycopg[binary]`
    - `PostgreSQL(dsn_or_url: str)`
    - `PostgreSQL.Connect(...)`"""

    conn: psycopg_Connection[SequenceAny]

    def __init__ (self, dsn_or_url: str, **kwargs: Any) -> None:
        kwargs = { "connect_timeout": 5, **kwargs }
        self.conn = psycopg_connect(dsn_or_url, **kwargs)
        self.set_parameter("%s")

    @classmethod
    def Connect (cls, *, host: str | None = "localhost",
                         port: int | str | None = 5432,
                         user: str | None = None,
                         password: str | None = None,
                         dbname: str | None = "postgres",
                         connect_timeout: int | None = 5,
                         **kwargs: Any) -> "PostgreSQL":
        connection = object.__new__(cls)
        connection.conn = psycopg_connect(**{
            key: value
            for key, value in {
                "host": host,
                "port": port,
                "user": user,
                "password": password,
                "dbname": dbname,
                "connect_timeout": connect_timeout,
                **kwargs
            }.items()
            if value is not None
        })
        return connection.set_parameter("%s")

    @override
    def execute (self, statement: ExecutableStatement, **kwargs) -> ResultSQL:
        """Execute `SQL: Statement`
        - `kwargs` additional params `execute()` or `executemany()` accepts"""
        sql, params = (
            statement
            .set_parameter(self.parameter, self.quote_info)
            .to_sql()
        )

        cursor = self.cursor()
        if params and isinstance(params[0], (list, tuple)):
            return cursor.executemany(sql, params, **{ "returning": True, **kwargs })
        return cursor.execute(sql, params, **kwargs)

    def tables (self, schema: str | None = None) -> list[TableData]:
        """List Tables Data of Database"""
        cursor = self.cursor()
        if schema is None:
            sql = """
                SELECT table_name AS name, table_schema AS schema, (table_type = 'VIEW') AS is_view
                FROM information_schema.tables
                WHERE table_schema = ANY(current_schemas(false))
                    AND table_type IN ('BASE TABLE', 'VIEW')
                ORDER BY table_schema, table_type, table_name
            """
            result = cursor.execute(sql)

        else:
            sql = """
                SELECT table_name AS name, table_schema AS schema, (table_type = 'VIEW') AS is_view
                FROM information_schema.tables
                WHERE table_schema = %s
                    AND table_type IN ('BASE TABLE', 'VIEW')
                ORDER BY table_schema, table_type, table_name
            """
            result = cursor.execute(sql, [schema])

        return [
            TableData(**item)
            for item in result.to_dict()
        ]

    def columns (self, table: str, schema: str | None = None) -> list[ColumnData]:
        """List Columns Data of `table` and `schema`"""
        if schema is None:
            sql = """
                SELECT column_name AS name,
                       data_type AS type,
                       is_nullable = 'YES' AS is_nullable,
                       column_default IS NOT NULL AS has_default
                FROM information_schema.columns
                WHERE table_name = %s
                    AND table_schema = ANY(current_schemas(false))
                ORDER BY ordinal_position
            """
            params = (table,)
        else:
            sql = """
                SELECT column_name AS name,
                       data_type AS type,
                       is_nullable = 'YES' AS is_nullable,
                       column_default IS NOT NULL AS has_default
                FROM information_schema.columns
                WHERE table_name = %s
                    AND table_schema = %s
                ORDER BY ordinal_position
            """
            params = (table, schema)

        cursor = self.cursor()
        return [
            ColumnData(**item)
            for item in cursor.execute(sql, params).to_dict()
        ]

__all__ = ["PostgreSQL"]