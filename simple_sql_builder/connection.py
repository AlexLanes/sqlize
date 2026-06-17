# std
from __future__ import annotations
from json import dumps
from decimal import Decimal
from dataclasses import dataclass
from typing import Protocol, Any, Self
from datetime import datetime, date, time
# internal
from simple_sql_builder.shared import SequenceAny, ManySequenceAny, MappingAny

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

    rowcount: int
    columns: tuple[str, ...]
    rows: list[SequenceAny]

    def __bool__ (self) -> bool:
        return bool(self.rowcount or self.returned)

    def __repr__ (self) -> str:
        return f"<ResultSQL rowcount={self.rowcount} returned={self.returned}>"

    @property
    def returned (self) -> int:
        return len(self.rows)

    @property
    def first (self) -> MappingAny:
        rows = self.rows[0] if self.rows else []
        return dict(zip(self.columns, rows))

    def to_dict (self) -> list[MappingAny]:
        return [
            dict(zip(self.columns, row))
            for row in self.rows
        ]

    def stringify (self, indent: int = 4) -> str:
        def defaults (item: Any) -> Any:
            match item:
                case datetime(): return item.isoformat(sep="T", timespec="seconds")
                case time(): return item.isoformat(timespec="seconds")
                case date(): return item.isoformat()
                case Decimal(): return float(item)
                case 1 if hasattr(item, "__iter__"):
                    return [defaults(x) for x in item]
                case 1 if hasattr(item, "__dict__"):
                    return item.__dict__
                case _: return str(item)

        return dumps(
            self.to_dict(),
            indent = indent,
            default = defaults,
            ensure_ascii = False,
        )

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
        self.cursor = (
            self.cursor.execute(sql, **kwargs)
            if params is None else
            self.cursor.execute(sql, params, **kwargs)
        )

        columns = self.columns
        rowcount = self.rowcount
        rows = [row for row in self.cursor] if columns else []

        self.close()
        return ResultSQL(rowcount, columns, rows)

    def executemany (self, sql: str, params: ManySequenceAny, **kwargs) -> ResultSQL:
        self.cursor = (
            self.cursor.executemany(sql, params, **kwargs)
            or self.cursor
        )

        columns = self.columns
        rowcount = self.rowcount
        rows = [row for row in self.cursor] if columns else []

        # cursor.nextset()
        if (nextset := getattr(self.cursor, "nextset", None)) and callable(nextset):
            while nextset():
                rowcount += self.rowcount
                rows.extend(row for row in self.cursor)

        self.close()
        return ResultSQL(rowcount, columns, rows)

class Connection:
    """`IConnectionPEP249 => "DB API 2.0"` Wrapper to `transaction` `close` `Cursor`
    - `Connection(conn)` closing should be handled
    - `with Connection(conn) as connection` are closed after `with`"""
    def __init__ (self, conn: IConnectionPEP249) -> None:
        self.conn = conn

    def __repr__ (self) -> str:
        name = (
            f"for {conn.__module__}.{conn.__class__.__name__}"
            if (conn := getattr(self, "conn", False))
            else "closed"
        )
        return f"<Connection {name!r}>"

    def __enter__ (self) -> Self:
        return self

    def __exit__ (self, *_) -> None:
        self.close()

    def close (self) -> None:
        self.conn.close()
        del self.conn

    def commit (self) -> None:
        self.conn.commit()

    def rollback (self) -> None:
        self.conn.rollback()

    def cursor (self) -> Cursor:
        return Cursor(self.conn.cursor())

__all__ = [
    "ResultSQL",
    "Connection",
]