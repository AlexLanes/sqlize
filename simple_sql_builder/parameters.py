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

DB_DRIVER_PARAMSTYLE: dict[str, tuple[Positionals, tuple[bool, str] | None]] = {
    # SQLite
    "sqlite3":   ("?", None),
    # ODBC
    "pyodbc":    ("?", None),
    # PostgreSQL
    "psycopg2":  ("%s", None),
    "psycopg":   ("%s", None),
    "pg8000":    ("%s", None),
    # MySQL / MariaDB
    "mysqldb":   ("%s", (False, "`")),
    "pymysql":   ("%s", (False, "`")),
    "mariadb":   ("?",  (False, "`")),
    # SQL Server
    "pymssql":   ("%s", (False, "[")),
    # Oracle
    "oracledb":  (":N", (True, '"')),
    "cx_oracle": (":N", (True, '"')),
    # DuckDB
    "duckdb":    ("?", None),
}

def guess_driver_parameter (driver: object) -> tuple[Positionals, tuple[bool, str] | None]:
    module_name = driver.__class__.__module__.lower().strip()
    if parameter := DB_DRIVER_PARAMSTYLE.get(module_name):
        return parameter

    name = module_name + driver.__class__.__name__.lower().strip()
    guesses = [
        ("oracle", ":N", (True, '"')),
        ("mysql", "%s", (False, "`")),
        ("pg", "%s", (False, '"')),
    ]

    for db_db, parameter, quote_info in guesses:
        if db_db in name: return (parameter, quote_info) # type: ignore
    return ("?", None)

__all__ = [
    "Positionals",
    "IPositionalParameter",
    "POSITIONAL_PARAMETERS",
    "guess_driver_parameter",
]