# std
from typing import overload
from dataclasses import dataclass
# internal
from sqlize.shared import SQLValue
from sqlize.table import Table
from sqlize.column import Column as C

class Column[T: SQLValue]:

    column: C

    def __init__ (self, column: C) -> None:
        self.column = column

    def __set_name__ (self, _, name: str) -> None:
        self.name = name

    def __set__ (self, instance, value: T) -> None:
        instance.__dict__[self.name] = value

    @overload
    def __get__(self, instance: None, owner: type) -> C: ...
    @overload
    def __get__(self, instance: object, owner: type) -> T: ...
    def __get__(self, instance: object, owner: type) -> C | T:
        # Class.attribute -> Column[T]
        if instance is None:
            return self.column
        # Instance.attribute -> type[T]
        try: return instance.__dict__[self.name]
        except KeyError:
            error = AttributeError(self.name)
            error.add_note(f"Atribute {instance.__class__.__name__}.{self.name} has not been set")
            raise error from None

class PrimaryKey[T: SQLValue] (Column[T]):
    ...

@dataclass(slots=True, frozen=True)
class ColumnInfo:
    name: str
    pytype: type
    column: C

@dataclass
class ModelData:
    table: Table
    infos: dict[str, ColumnInfo]
    """`{ property_name: ColumnInfo }`"""
    columns: tuple[list[C], list[C]]
    """`([PrimaryKey], [Column])`"""

__all__ = [
    "Column",
    "PrimaryKey",

    "ModelData",
    "ColumnInfo",
]