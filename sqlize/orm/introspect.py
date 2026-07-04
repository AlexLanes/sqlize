# std
from __future__ import annotations
import unicodedata
from typing import Any
from decimal import Decimal
from datetime import date, time, datetime
# internal
from sqlize.orm.interface import ISupportColumns, ColumnData

TRANSLATE_MAP: dict[str, tuple[type, str]] = {
    # Text
    "char": (str, ""),
    "clob": (str, ""),
    "text": (str, ""),
    "uuid": (str, ""),
    "nchar": (str, ""),
    "nclob": (str, ""),
    "string": (str, ""),
    "varchar": (str, ""),
    "uniqueidentifier": (str, ""),
    # Int
    "int": (int, ""),
    "serial": (int, ""),
    "integer": (int, ""),
    # Float
    "real": (float, ""),
    "float": (float, ""),
    "double": (float, ""),
    # Decimal
    "money": (Decimal, "from decimal import Decimal"),
    "numeric": (Decimal, "from decimal import Decimal"),
    "decimal": (Decimal, "from decimal import Decimal"),
    "smallmoney": (Decimal, "from decimal import Decimal"),
    # Boolean
    "bit": (bool, ""),
    "bool": (bool, ""),
    "boolean": (bool, ""),
    # Dates
    "time": (time, "from datetime import time"),
    "date": (date, "from datetime import date"),
    "datetime": (datetime, "from datetime import datetime"),
    "timestamp": (datetime, "from datetime import datetime"),
}

def translate (base_type: str) -> tuple[Any, str]:
    if t := TRANSLATE_MAP.get(base_type):
        return t

    # str
    if any(t in base_type for t in ("text", "varchar", "character", "xml", "enum")):
        return str, ""
    # bytes
    if any(t in base_type for t in ("binary", "blob", "raw")):
        return bytes, ""
    # int
    if any(t in base_type for t in ("int", "number", "serial")):
        return int, ""
    # float
    if any(t in base_type for t in ("float", "real", "double")):
        return float, ""

    # datetime
    if any(t in base_type for t in ("timestamp", "datetime")):
        return datetime, "from datetime import datetime"
    # date
    if "date" in base_type:
        return date, "from datetime import date"
    # time
    if "time" in base_type:
        return time, "from datetime import time"

    return "Unknown", "from typing import Any as Unknown"

def normalize (name: str) -> str:
    return "_".join(
        "".join(
            char for char in part.strip().lower()
            if char.isalnum() or char == "_"
        )
        for part in unicodedata.normalize("NFKD", name)
                               .encode("ASCII", "ignore")
                               .decode("utf-8", "ignore")
                               .split(" ")
        if part.strip()
    ).strip("_")

def introspect (connection: ISupportColumns, table_name: str, schema: str | None = None) -> None:
    """Instrospect metadatas of `tablename` from `connection` and `print()` generated `Model`
    ### Example
    ```python
    from sqlize.orm import introspect
    from sqlize.connections.postgresql import PostgreSQL

    with PostgreSQL.Connect(user="postgres", password="admin") as conn:
        introspect(conn, table_name="users")
    ```
    """
    if "schema" in connection.columns.__annotations__:
        columns = connection.columns(table_name, schema) # type: ignore
    else: columns = connection.columns(table_name)

    table = ".".join((table_name, schema)) if schema else table_name
    assert columns and isinstance(columns, list), f"Table not found {table} to introspect"
    columns = [
        column
        for column in columns
        if isinstance(column, ColumnData)
    ]

    typed_columns = list[str]()
    imports = { "from sqlize.orm import SQLizer, PrimaryKey, Column" }

    for column in columns:
        t, i = translate(base_type = column.type.split("(", 1)[0].strip().lower())
        if i: imports.add(i)

        column_name = column.name
        normalized = normalize(column_name)
        cls = "PrimaryKey" if column.is_pk else "Column"
        generic_type = (
            f"{cls}[Unknown]"
            if t == "Unknown" else
            f"{cls}[{ t | None }]"
            if column.is_nullable else
            f"{cls}[{ t.__name__ }]"
        )

        typed_columns.append(
            f"{column_name}: {generic_type}"
            if column_name == normalized
            else f"{normalized} = {generic_type}(alias={column_name!r})"
        )

    print(*sorted(imports, key=lambda i: (bool(i != "Unknown") , len(i))), sep="\n")
    if schema: print("from sqlize import T")    
    print("from", connection.__class__.__module__, "import", connection_name := connection.__class__.__name__)
    print()

    print(f"class {table_name.capitalize()} (SQLizer):")
    if not schema: print(f'    __table__ = "{table_name}"')
    else: print(f'    __table__ = T("{table_name}", "{schema}")')
    print(*(f"    {column}" for column in typed_columns), sep="\n")
    print()

    print(f"with {connection_name}(...).AddInstance():")
    print(f'    print("Total Rows:", {table_name.capitalize()}.Select().Count())')

__all__ = ["introspect"]