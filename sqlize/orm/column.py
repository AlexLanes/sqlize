# std
from dataclasses import dataclass
from functools import cached_property
from typing import overload, override
# internal
from sqlize.shared import SQLValue
from sqlize.table import Table
from sqlize.column import Column as C
from sqlize.orm.exceptions import PrimaryKeyNotSetError

class Column[T: SQLValue]:

    column: C

    def __init__ (self, column: C) -> None:
        self.column = column

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
            msg = f"Atribute {instance.__class__.__name__}.{self.name} of instance has not been set"
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
    pytype: type
    column: C
    is_pk: bool

@dataclass(frozen=True)
class ModelData:
    table: Table
    infos: dict[str, ColumnInfo]
    """`{ property_name: ColumnInfo }`"""

    @property
    def all_columns (self) -> list[C]:
        """PK + Columns"""
        return [*self.primary_keys, *self.columns]

    @cached_property
    def columns (self) -> list[C]:
        """No Primary Key"""
        return [
            info.column
            for info in self.infos.values()
            if not info.is_pk
        ]

    @cached_property
    def primary_keys (self) -> list[C]:
        """Only Primary Key"""
        return [
            info.column
            for info in self.infos.values()
            if info.is_pk
        ]

    @property
    def has_pk (self) -> bool:
        return bool(self.primary_keys)

__all__ = [
    "Column",
    "PrimaryKey",

    "ModelData",
    "ColumnInfo",
]