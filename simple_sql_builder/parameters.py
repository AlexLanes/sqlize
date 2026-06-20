# std
from typing import Protocol, Literal

class IPositionalParameter (Protocol):
    identifier: str
    def next (self) -> str:
        """Return the next parameter when called"""
        ...

class QuestionMarkPositional (IPositionalParameter):
    identifier = "?"
    def next (self) -> str:
        return self.identifier

class PercentPositional (IPositionalParameter):
    identifier = "%s"
    def next (self) -> str:
        return self.identifier

class ColonNumberPositional (IPositionalParameter):
    identifier = ":N"
    def __init__ (self) -> None:
        self.n = 0

    def next (self) -> str:
        self.n += 1
        return f":{self.n}"

type Positionals = Literal["?", "%s", ":N"]
POSITIONAL_PARAMETERS: dict[str, type[IPositionalParameter]] = {
    "?":  QuestionMarkPositional,
    "%s": PercentPositional,
    ":N": ColonNumberPositional
}

DB_DRIVER_PARAMSTYLE: dict[str, Positionals] = {
    # SQLite
    "sqlite3": "?",
    # ODBC
    "pyodbc": "?",
    # PostgreSQL
    "psycopg2": "%s",
    "psycopg": "%s",
    "pg8000": "%s",
    # MySQL / MariaDB
    "mysqldb": "%s",
    "pymysql": "%s",
    "mariadb": "?",
    # SQL Server
    "pymssql": "%s",
    # Oracle
    "oracledb": ":N",
    "cx_oracle": ":N",
    # DuckDB
    "duckdb": "?",
}

def guess_driver_parameter (driver: object) -> Positionals:
    module_name = driver.__class__.__module__.lower().strip()
    if p := DB_DRIVER_PARAMSTYLE.get(module_name):
        return p

    name = module_name + driver.__class__.__name__.lower().strip()
    guesses: list[tuple[str, Literal["?", "%s", ":N"]]] = [
        ("oracle", ":N"),
        ("mysql", "%s"),
        ("pg", "%s")
    ]

    for db, p in guesses:
        if db in name: return p
    return "?"

__all__ = [
    "Positionals",
    "POSITIONAL_PARAMETERS",
    "guess_driver_parameter",
]