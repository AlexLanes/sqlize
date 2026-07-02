# std
from __future__ import annotations
from json import dumps
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime, date, time
from typing import Protocol, Any, Self, Iterator, Callable
# internal
from sqlize.parameters import *
from sqlize.shared import SequenceAny, ManySequenceAny, MappingAny, SQLValue
from sqlize.supports import ExecutableStatement, SupportParameters

class ICursorPEP249 (Protocol):
    def __iter__ (self) -> Self: ...
    def __next__ (self) -> SequenceAny: ...
    @property
    def rowcount (self) -> int: ...
    @property
    def description (self) -> ManySequenceAny | None: ...
    def close (self) -> None: ...
    def execute (self, *args, **kwargs) -> ICursorPEP249: ...
    def executemany (self, *args, **kwargs) -> ICursorPEP249 | None: ...

class IConnectionPEP249 (Protocol):
    def close (self) -> None: ...
    def commit (self) -> None: ...
    def rollback (self) -> None: ...
    def cursor (self, *args, **kwargs) -> ICursorPEP249: ...

@dataclass
class ResultSQL:
    """SQL dataclass of `Connection.execute()` `Cursor.execute()` `Cursor.executemany()`
    - `bool(result)` to check for `rowcount` or `rows returned`
    - `for line in result: ...`"""

    rowcount: int
    """Affected lines
    - Can vary because of database driver"""
    returned: int
    """Rows originally returned
    - Use `len(self)` for actual `rows` length"""
    columns: tuple[str, ...]
    """Columns names of `rows returned`"""
    rows: list[SequenceAny]
    """Sequence of values of `rows returned`"""

    def __bool__ (self) -> bool:
        return bool(self.rowcount or len(self))

    def __repr__ (self) -> str:
        return f"<ResultSQL rowcount={self.rowcount} returned={self.returned}>"

    def __len__ (self) -> int:
        return len(self.rows)

    def __iter__ (self) -> Iterator[MappingAny]:
        for row in self.rows:
            yield dict(zip(self.columns, row))

    @property
    def first (self) -> MappingAny:
        """First row returned or `{}` if empty"""
        return next(self.__iter__()) if self.rows else {}

    def transform (self, **funcs: Callable[[SQLValue], SQLValue]) -> Self:
        """Transform values of columns with custom function `column_name = (value) -> value`
        - `result.transform(name = lambda value: str(value).upper())`"""
        if not funcs:
            return self

        transforms = {}
        for column, func in funcs.items():
            if column not in self.columns:
                raise ValueError(f"Column name {column!r} not present on ResultSQL.columns: {self.columns}")
            index = self.columns.index(column)
            transforms[index] = func

        self.rows = [
            tuple(
                transforms[index](value)
                if index in transforms
                else value

                for index, value in enumerate(row)
            )
            for row in self.rows
        ]
        return self

    def filter (self, func: Callable[[MappingAny], bool]) -> Self:
        """Filter `rows returned` with custom `func (line) -> bool`
        - `result.filter(lambda line: line["id"] == 1)`"""
        self.rows = [
            row
            for line, row in zip(self, self.rows)
            if func(line)
        ]
        return self

    def to_dict (self) -> list[MappingAny]:
        """Transform `rows` and `columns` to `list[dict]`"""
        return list(self)

    def stringify (self, indent: bool = False) -> str:
        """Transform of `result.to_dict()` to `JSON String`"""
        def defaults (item: Any) -> Any:
            match item:
                case datetime(): return item.isoformat(sep="T", timespec="seconds")
                case time(): return item.isoformat(timespec="seconds")
                case date(): return item.isoformat()
                case Decimal(): return float(item)
                case 1 if hasattr(item, "__iter__"):
                    return [defaults(x) for x in item]
                case 1 if hasattr(item, "__dict__"):
                    return {
                        str(key): defaults(value)
                        for key, value in (item.__dict__ or {}).items()
                    }
                case _: return str(item)

        return dumps(
            self.to_dict(),
            indent = 4 if indent else None,
            default = defaults,
            ensure_ascii = False,
        )

    def print (self) -> None:
        """Print to `console`"""
        print(*self, self, sep="\n")

class Cursor:
    def __init__ (self, cursor: ICursorPEP249) -> None:
        self.cursor = cursor

    @property
    def rowcount (self) -> int:
        try: return max(self.cursor.rowcount or 0, 0)
        except Exception: return 0

    @property
    def columns (self) -> tuple[str, ...]:
        """Helper for `description`"""
        try: return tuple(str(column) for column, *_ in self.cursor.description or [])
        except Exception: return tuple()

    def close (self) -> None:
        try: self.cursor.close()
        except Exception: pass

    def execute (self, sql: str, params: SequenceAny | None = None, **kwargs) -> ResultSQL:
        if not params:
            self.cursor.execute(sql, **kwargs)
        else:
            self.cursor.execute(sql, params, **kwargs)

        columns = self.columns
        rows = [row for row in self.cursor] if columns else []
        rowcount = self.rowcount

        self.close()
        return ResultSQL(rowcount, len(rows), columns, rows)

    def executemany (self, sql: str, params: ManySequenceAny, **kwargs) -> ResultSQL:
        self.cursor.executemany(sql, params, **kwargs)

        columns = self.columns
        rows = [row for row in self.cursor] if columns else []
        rowcount = self.rowcount

        # cursor.nextset()
        if (nextset := getattr(self.cursor, "nextset", None)) and callable(nextset):
            while nextset():
                rowcount += self.rowcount
                rows.extend(row for row in self.cursor)

        self.close()
        return ResultSQL(rowcount, len(rows), columns, rows)

CONNECTIONS = list["Connection"]()

class Connection (SupportParameters):
    """Wrapper to a driver Connection with support to `execute(statement)`
    - `IConnectionPEP249 => "DB API 2.0"` Interface to `commit` `rollback` `close` `Cursor`
    - `Connection(conn)` closing should be handled
    - `with Connection(conn) as connection` are closed after `with`"""

    def __init__ (self, conn: IConnectionPEP249) -> None:
        self.conn = conn
        self.set_parameter(*guess_driver_parameter(conn))

    def __repr__ (self) -> str:
        name = (
            f"{self.conn.__module__}.{self.conn.__class__.__name__}"
            if self
            else "closed"
        )
        return f"<Connection => {name!r} ID({id(self)})>"

    def __bool__ (self) -> bool:
        return hasattr(self, "conn")

    def __enter__ (self) -> Self:
        return self

    def __exit__ (self, *_) -> None:
        self.close()

    def AddInstance (self) -> Self:
        """Add `Instance: Connection` to be accessible by `GetInstance()`"""
        CONNECTIONS.append(self)
        return self

    @classmethod
    def GetInstance (cls) -> Self:
        """Get last opened `Instance: Connection`"""
        global CONNECTIONS
        CONNECTIONS = [
            connection
            for connection in CONNECTIONS
            if connection
        ]

        for connection in reversed(CONNECTIONS):
            if cls is Connection or isinstance(connection, cls):
                return connection # type: ignore

        raise Exception(f"No opened Connection found for {cls}")

    def close (self) -> None:
        if not self:
            return

        self.conn.close()
        del self.conn

        if self in CONNECTIONS:
            CONNECTIONS.remove(self)

    def commit (self) -> None:
        self.conn.commit()

    def rollback (self) -> None:
        self.conn.rollback()

    def cursor (self) -> Cursor:
        return Cursor(self.conn.cursor())

    def execute (self, statement: ExecutableStatement, **kwargs) -> ResultSQL:
        """Execute `SQL: Statement`
        - Type of `PositionalParameter` guessed on `init` by `conn` name
            - `set_parameter()` to manually set
        - `kwargs` additional params `execute()` or `executemany()` accepts"""
        sql, params = (
            statement
            .set_parameter(self.data.parameter, self.data.quote_info)
            .to_sql()
        )

        cursor = self.cursor()
        if params and isinstance(params[0], (list, tuple)):
            return cursor.executemany(sql, params, **kwargs)
        return cursor.execute(sql, params, **kwargs)

    def execute_and_print (self, statement: ExecutableStatement, **kwargs) -> None:
        """Execute `SQL: Statement` and `print` to console
        - Type of `PositionalParameter` guessed on `init` by `conn` name
            - `set_parameter()` to manually set
        - `kwargs` additional params `execute()` or `executemany()` accepts"""
        sql, params = (
            statement
            .set_parameter(self.data.parameter, self.data.quote_info)
            .to_sql()
        )

        print("--- SQL ---", sql, "", "--- PARAMS ---", sep="\n")
        if params and isinstance(params[0], (tuple, list)):
            print(*params, sep="\n")
        else: print(params)
    
        print("\n--- Result ---")
        self.execute(statement, **kwargs).print()

__all__ = [
    "ResultSQL",
    "Connection",
]