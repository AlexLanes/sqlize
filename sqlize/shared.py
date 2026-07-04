# std
from __future__ import annotations
from dataclasses import dataclass
from json import dumps
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime, date, time
from typing import (
    Any, Self, overload,
    Iterable, Sequence, Mapping
)

type SQLValue = object
type SequenceAny = Sequence[Any]
type MappingAny = Mapping[str, Any]
type ManySequenceAny = Sequence[SequenceAny]

def quote (s: str, quote_info: tuple[bool, str] | None = None) -> str:
    """Quote `s` depending on `quote_info`
    - `quote_info` used as `enforce, char_quote` and `None` for `"` if contains space"""
    if s == "*":
        return s

    if quote_info is None:
        return f'"{s}"' if " " in s else s

    enforce, char = quote_info
    if char == "[": return f"[{s}]" if enforce or " " in s else s
    return f"{char}{s}{char}" if enforce or " " in s else s

def indent (sql: str) -> str:
    """Indent lines do `sql` by 4 spaces"""
    return "\n".join(
        "    " + line
        for line in sql.split("\n")
    )

def stringify (item: Any, indent: bool = False) -> str:
    """Transforms `item` to `JSON String`"""
    def defaults (item: Any) -> Any:
        match item:
            case None: return "null"
            case bool(): return "true" if item else "false"
            case str() | int() | float(): return item
            case datetime(): return item.isoformat(sep="T", timespec="seconds")
            case time(): return item.isoformat(timespec="seconds")
            case date(): return item.isoformat()
            case Decimal(): return float(item)
            case _ if hasattr(item, "__iter__"):
                return [defaults(x) for x in item]
            case _ if data := getattr(item, "__dict__", {}):
                return {
                    str(key): defaults(value)
                    for key, value in data.items()
                }
            case _: return str(item)

    return dumps(
        item,
        indent = 4 if indent else None,
        default = defaults,
        ensure_ascii = False,
    )

@dataclass(kw_only=True)
class TableData:
    name: str
    schema: str | None = None
    is_view: bool

@dataclass(kw_only=True)
class ColumnData:
    name: str
    type: str
    is_pk: bool = False
    is_nullable: bool
    has_default: bool

class DataSQL:
    __slots__ = ("sqls", "params")
    sqls: list[str]
    """`SQLs: Parameterized`
    - Formatted as Python Positional Parameter `{}`"""
    params: list[Any]
    """Positional parameters of `sqls`"""

    def __init__ (self, sql: str, params: SequenceAny) -> None:
        self.sqls = [sql]
        self.params = params if isinstance(params, list) else [*params]

    @classmethod
    def from_parts (cls, sql_parts: list[str], params: list[Any]) -> DataSQL:
        sql = object.__new__(cls)
        sql.sqls = sql_parts
        sql.params = params
        return sql

    @classmethod
    def merge (cls, datas: Iterable[DataSQL]) -> DataSQL:
        sql = object.__new__(cls)
        sql.sqls = []
        sql.params = []

        for data in datas:
            sql.extend(data)

        return sql

    def __repr__ (self) -> str:
        return f"<ParamsSQL => {self.params} {self.join()}>"

    def __str__ (self) -> str:
        return self.join()

    def __iter__ (self):
        yield from self.params

    @overload
    def extend (self, sql: DataSQL) -> Self: ...
    @overload
    def extend (self, sql: str, params: SequenceAny | None = None) -> Self: ...
    def extend (self, sql: str | DataSQL, params: SequenceAny | None = None) -> Self:
        if isinstance(sql, DataSQL):
            self.sqls.extend(sql.sqls)
            self.params.extend(sql)
        else:
            self.sqls.append(sql)
            self.params.extend(params or [])
        return self

    def join (self, string=" ") -> str:
        """`SQL: Parameterized`
        - `string` used to concat `sqls`
        - Formatted as Python Positional Parameter `{}`"""
        return string.join(self.sqls)

__all__ = [
    "quote",
    "indent",
    "DataSQL",
    "SQLValue",
    "TableData",
    "stringify",
    "ColumnData",
    "MappingAny",
    "SequenceAny",
    "ManySequenceAny",
]