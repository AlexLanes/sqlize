# std
from dataclasses import dataclass
from functools import cached_property
from typing import overload, override
# internal
from sqlize.shared import SQLValue
from sqlize.table import Table
from sqlize.column import Column as C, AliasedColumn as A
from sqlize.orm.exceptions import PrimaryKeyNotSetError
# external
import msgspec

class Column[T: SQLValue]:

    column: C

    @overload
    def __init__ (self, *, column: C) -> None: ...
    @overload
    def __init__ (self, *, alias: str) -> None: ...
    def __init__ (self, **kwargs) -> None:
        if (column := kwargs.get("column")) is not None:
            self.column = column
        elif (alias := kwargs.get("alias")) is not None:
            self.column = alias
        else: raise ValueError("Unexpected **kwargs for Column")

    def __set_name__ (self, _, name: str) -> None:
        self.name = name

    def __set__ (self, instance, value: T) -> None:
        instance.__dict__[self.name] = value

    @overload
    def __get__ (self, instance: None, owner: type) -> C: ...
    @overload
    def __get__ (self, instance: object, owner: type) -> T: ...
    def __get__ (self, instance: object, owner: type) -> C | T:
        # Class.attribute -> Column[T]
        if instance is None:
            return self.column
        # Instance.attribute -> type[T]
        try: return instance.__dict__[self.name]
        except KeyError:
            msg = f"Attribute {instance.__class__.__name__}.{self.name} of instance has not been set"
            error = (
                PrimaryKeyNotSetError(msg, name=self.name, obj=instance)
                if self.__class__ is PrimaryKey
                else AttributeError(msg, name=self.name, obj=instance)
            )
            raise error from None

class PrimaryKey[T: SQLValue] (Column[T]):

    @override
    def __set__ (self, instance, value: T) -> None:
        if self.name in instance.__dict__:
            raise AttributeError(f"{instance.__class__.__name__}().{self.name} is a PrimaryKey and should not be mutable")
        super().__set__(instance, value)

@dataclass(slots=True, frozen=True)
class ColumnInfo:
    name: str
    """`property_name`"""
    pytype: type
    column: C
    is_pk: bool

@dataclass(frozen=True)
class ModelData:
    table: Table
    infos: dict[str, ColumnInfo]
    """`{ property_name: ColumnInfo }`"""
    struct: type[msgspec.Struct]

    @cached_property
    def pk (self) -> ColumnInfo | None:
        return (
            [
                info
                for info in self.infos.values()
                if info.is_pk
            ] or [None]
        )[0]

    @cached_property
    def sql_columns (self) -> list[C | A]:
        return [
            info.column
            if name == info.column.name
            else info.column.As(name)

            for name, info in self.infos.items()
        ]

__all__ = [
    "Column",
    "PrimaryKey",

    "ModelData",
    "ColumnInfo",
]