"""`Connection` for `PostgreSQL` database using external `psycopg[binary]`
## Optional dependency `[postgresql]` needed"""

# std
from typing import Any, override
# internal
from sqlize.shared import SequenceAny, TableData, ColumnData
from sqlize.supports import ExecutableStatement
from sqlize.connections import Connection as C, ResultSQL
# external
try: from psycopg import (
    connect as psycopg_connect,
    Connection as psycopg_Connection
)
except ImportError:
    raise ImportError("Optional dependency [postgresql] needed to use 'sqlize.connections.postgresql'")

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
            .set_parameter(self.data.parameter, self.data.quote_info)
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
                SELECT
                    c.column_name AS name,
                    c.data_type AS type,
                    c.is_nullable = 'YES' AS is_nullable,
                    c.column_default IS NOT NULL AS has_default,
                    EXISTS (
                        SELECT 1
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu
                            ON tc.constraint_name = kcu.constraint_name
                        AND tc.table_schema = kcu.table_schema
                        WHERE tc.constraint_type = 'PRIMARY KEY'
                        AND tc.table_schema = c.table_schema
                        AND tc.table_name = c.table_name
                        AND kcu.column_name = c.column_name
                    ) AS is_pk
                FROM information_schema.columns c
                WHERE c.table_name = %s
                    AND c.table_schema = ANY(current_schemas(false))
                ORDER BY c.ordinal_position;
            """
            params = (table,)
        else:
            sql = """
                SELECT
                    c.column_name AS name,
                    c.data_type AS type,
                    c.is_nullable = 'YES' AS is_nullable,
                    c.column_default IS NOT NULL AS has_default,
                    EXISTS (
                        SELECT 1
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu
                            ON tc.constraint_name = kcu.constraint_name
                        AND tc.table_schema = kcu.table_schema
                        WHERE tc.constraint_type = 'PRIMARY KEY'
                        AND tc.table_schema = c.table_schema
                        AND tc.table_name = c.table_name
                        AND kcu.column_name = c.column_name
                    ) AS is_pk
                FROM information_schema.columns c
                WHERE c.table_name = %s
                    AND c.table_schema = %s
                ORDER BY c.ordinal_position;
            """
            params = (table, schema)

        cursor = self.cursor()
        return [
            ColumnData(**item)
            for item in cursor.execute(sql, params).to_dict()
        ]

__all__ = ["PostgreSQL"]