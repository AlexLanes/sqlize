# std
from typing import (
    Any, Self, get_args,
    get_type_hints, get_origin
)
# internal
from sqlize.shared import SQLValue
from sqlize.column import Column as C, AliasedColumn as A
from sqlize.table import Table
from sqlize.connections import Connection
from sqlize.dml import Delete, Select, Update
from sqlize.orm.exceptions import *
from sqlize.orm.column import *
from sqlize.orm.select import ModelSelect
from sqlize.orm.insert import ModelInsert
# external
import msgspec

class SQLizer:
    """`Base Model` used as inheritance
    - External `msgspec` used for validation and serialization
    - `__table__` to set the name of table `Default: str(Model.__name__)`
    - `Model.property` are transformed into `Columns`
    - `Instance.property` type is preserved

    ### Example
    ```
    from sqlize import T
    from sqlize.orm import SQLizer, PrimaryKey, Column
    from sqlize.connections.sqlite import SQLite

    # Define Model
    class Users (SQLizer):
        __table__ = "Users"
        id: PrimaryKey[int]
        name: Column[str]

    # Define Model Expanded
    class Users (SQLizer):
        __table__ = T.Users.Schema("public")
        id = PrimaryKey[int](alias="user_id")
        name = Column[str](alias="User Name")

    # Open a Connection
    # Add to be used by other methods
    # Other Connections can be used from `sqlize.connections`
    with SQLite().AddInstance() as connection:

        # Select PK
        user_1 = Users.Get(1)
        print(user_1)
        # Select Custom
        for user in Users.Select().OrderBy(Users.id.ASC).Limit(10).All():
            print(user.id, user.name)

        # Insert
        user_2 = Users.Insert(name="Alex")
        # PrimaryKey and other Columns captured
        print(user_2.id, user_2.name)

        # Update Columns
        user_1.name = "Foo"
        user_1.Update()
        # Simplified
        user_1.Update(name="Foo")

        # Refresh Columns Values
        user_1.name = "Foo"
        user_1.Refresh()

        # Delete PK
        deleted = Users.Delete(1, raise_if_not_found=True)
        # Delete Object
        user_1.Remove()

        # Save
        connection.commit()
    ```
    """

    __table__: Table | str
    __data__: ModelData

    def __init__ (self, **kwargs: SQLValue) -> None:
        data = msgspec.convert(kwargs, self.__data__.struct, strict=False)
        for name in data.__struct_fields__:
            setattr(self, name, getattr(data, name))

    @classmethod
    def from_json (cls, json: bytes | str) -> Self:
        """Decode `JSON Object` to `Model`"""
        data = msgspec.json.decode(
            json,
            type = cls.__data__.struct,
            strict = False
        )

        obj = object.__new__(cls)
        for name in data.__struct_fields__:
            setattr(obj, name, getattr(data, name))

        return obj

    def __init_subclass__ (cls) -> None:
        super().__init_subclass__()

        table = getattr(cls, "__table__", cls.__name__)
        if not isinstance(table, Table):
            table = Table(str(table), None)

        pk_seen = False
        infos_map = dict[str, ColumnInfo]()

        # Class Defaults with Alias
        for name, hint in cls.__dict__.items():
            if not isinstance(hint, Column): continue
            if not (orig := getattr(hint, "__orig_class__", None)):
                raise ValueError(f"Missing GenericType for {cls.__name__}.{name}[T](alias={hint.column!r})")

            is_pk = isinstance(hint, PrimaryKey)
            if pk_seen and is_pk:
                raise ValueError(f"Multiples PrimaryKeys not Supported for {cls.__name__}")

            pk_seen = is_pk
            pytype = get_args(orig)[0]
            column = table.Column(
                # Alias
                str(hint.column)
                if isinstance(hint.column, str)
                else hint.column.name
            )

            # Update Class Descriptor
            hint.column = column
            infos_map[name] = ColumnInfo(name, pytype, column, is_pk)

        # Class Annotations
        for name, hint in get_type_hints(cls, include_extras=True).items():
            origin = get_origin(hint)
            match origin:
                case _ if origin is PrimaryKey and pk_seen:
                    raise ValueError(f"Multiples PrimaryKeys not Supported for {cls.__name__}")
                case _ if origin is PrimaryKey:
                    pk_seen = is_pk = True
                case _ if origin is Column:
                    is_pk = False
                case _ if hint in (PrimaryKey, Column):
                    raise ValueError(f"Missing type of {hint.__name__}[T] for {cls.__name__}.{name}")
                case _: continue

            # Class.attribute -> Column[T]
            pytype = get_args(hint)[0]
            column = table.Column(name)
            infos_map[name] = ColumnInfo(name, pytype, column, is_pk)

            # Instance.attribute -> T
            descriptor = origin(column=column)
            descriptor.__set_name__(cls, name)
            setattr(cls, name, descriptor)

        # Class Vars
        cls.__table__ = table
        cls.__data__  = ModelData(table, infos_map, msgspec.defstruct(
            eq = False,
            name = cls.__name__,
            module = cls.__module__,
            forbid_unknown_fields = True,
            fields = [
                (name, info.pytype)
                for name, info in infos_map.items()
            ],
        ))

    def __repr__ (self) -> str:
        name = self.__class__.__name__
        kwargs = ", ".join(
            f"{name}={value!r}"
            for name, value in self.__dict__.items()
        )
        return f"<{name}({kwargs})>"

    def __eq__ (self, other: object) -> bool:
        return (
            self.to_dict() == other.to_dict()
            if isinstance(other, SQLizer)
            else False
        )

    def to_dict (self) -> dict[str, Any]:
        """Format `Model` to `dict[str, Any]`"""
        return msgspec.structs.asdict(
            msgspec.convert(
                self,
                self.__data__.struct,
                strict = False,
                from_attributes = True
            )
        )

    def to_json (self) -> bytes:
        """Encode `Model` to `bytes` of `JSON Object`"""
        return msgspec.json.encode(
            msgspec.convert(
                self,
                self.__data__.struct,
                strict = False,
                from_attributes = True
            )
        )

    def stringify (self, indent: bool = False) -> str:
        """Format `Model` to `JSON String`"""
        return msgspec.json.format(
            self.to_json().decode(),
            indent = 4 if indent else 0
        )

    @staticmethod
    def GetConnection () -> Connection:
        """Get last opened `Instance: Connection`
        - `NoConnectionAvailableError`"""
        try: return Connection.GetInstance()
        except Exception:
            raise NoConnectionAvailableError

    # ------ #
    # Select #
    # ------ #

    @classmethod
    def Columns (cls) -> list[C | A]:
        """All `Columns` of `Model`"""
        return list(cls.__data__.sql_columns)

    @classmethod
    def Get (cls, pk: SQLValue) -> Self:
        """Select row of `Model` by `PrimaryKey` value
        - `@classmethod`
        - `ValueError` `NotFoundError` `MultipleResultsError`"""
        data = cls.__data__
        if data.pk is None:
            raise PrimaryKeyNotSetError(f"No PrimaryKey set for {cls.__name__}.Get({pk=})", obj=cls)

        # Validate Value
        try: pk = msgspec.convert(pk, data.pk.pytype, strict=False)
        except msgspec.ValidationError as error:
            raise ValueError(f"Mismatch value for PrimaryKey {cls.__name__}.Get({pk=}) | {cls.__name__}.{data.pk.name} {error}") from None

        # SELECT
        result = cls.GetConnection().execute(
            Select(*cls.Columns())
            .From(data.table)
            .Where(data.pk.column == pk)
        )

        match result.returned:
            case 1: return cls(**result.first)
            case 0:
                raise NotFoundError(
                    f"No Result for {cls.__name__}.Get({pk=})",
                    cls = cls,
                    values = { data.pk.name: pk }
                )
            case _:
                raise MultipleResultsError(
                    f"Multiple Results({ result.returned }) for {cls.__name__}.Get({pk=}). "
                    "PrimaryKey should match 1 row only"
                )

    @classmethod
    def Select (cls) -> ModelSelect[Self]:
        """Build custom `Select` with `Select().From()` already set
        - `@classmethod`
        - New Methods `All()` `First()` `Count()`
        ### Example
        `Model.Select().Count()`  
        `Model.Select().Where(Model.id < 100).All()`  
        `Model.Select().OrderBy(Model.id.DESC).Limit(1).First()`"""
        return ModelSelect(*cls.Columns(), model=cls)

    # ------ #
    # Delete #
    # ------ #

    def Remove (self) -> None:
        """Delete row of `Model` object by `PrimaryKey` value
        - `NotFoundError` `MultipleResultsError`"""
        data = self.__data__
        if data.pk is None:
            raise PrimaryKeyNotSetError(f"No PrimaryKey set for {self.__class__.__name__}().Remove()", obj=type(self))

        pk_value = getattr(self, data.pk.name)
        delete = Delete(data.table).Where(data.pk.column == pk_value)
        rowcount = self.GetConnection().execute(delete).rowcount

        match rowcount:
            case 1: return
            case 0:
                error = NotFoundError(
                    f"No Result for {self.__class__.__name__}({data.pk.name}={pk_value!r}).Remove()",
                    cls = type(self),
                    values = self.to_dict()
                )
                raise error
            case _:
                error = MultipleResultsError(
                    f"Multiple Results({ rowcount }) for {self.__class__.__name__}({data.pk.name}={pk_value!r}).Remove(). "
                    "PrimaryKey should match 1 row only"
                )
                raise error

    @classmethod
    def Delete (cls, pk: SQLValue, *, raise_if_not_found: bool = True) -> bool:
        """Delete row of `Model` by `PrimaryKey` value
        - Returns `deleted: bool`
        - `@classmethod`
        - `ValueError` `NotFoundError` `MultipleResultsError`"""
        data = cls.__data__
        if data.pk is None:
            raise PrimaryKeyNotSetError(f"No PrimaryKey set for {cls.__name__}.Delete({pk=})", obj=cls)

        # Validate Value
        try: pk = msgspec.convert(pk, data.pk.pytype, strict=False)
        except msgspec.ValidationError as error:
            raise ValueError(f"Mismatch value for PrimaryKey {cls.__name__}.Delete({pk=}) | {cls.__name__}.{data.pk.name} {error}") from None

        # DELETE
        result = cls.GetConnection().execute(
            Delete(data.table)
            .Where(data.pk.column == pk)
        )

        match result.rowcount:
            case 1: return True
            case 0 if not raise_if_not_found: return False
            case 0: raise NotFoundError(
                f"No Result for {cls.__name__}.Delete({pk=})",
                cls = cls,
                values = { data.pk.name: pk }
            )
            case _: raise MultipleResultsError(
                f"Multiple Results({ result.rowcount }) for {cls.__name__}.Delete({pk=}). "
                "PrimaryKey should match 1 row only"
            )

    # ------ #
    # Update #
    # ------ #

    def Update (self, **columns: SQLValue) -> Self:
        """Update row of `Model` by `PrimaryKey` value
        - `columns` to update `self` before executing `Update`
        - `Refresh()` can be chained to sync with `Connection`
        - `ValueError` `AttributeError` `UpdateError` `MultipleResultsError`"""
        data = self.__data__
        if data.pk is None:
            raise PrimaryKeyNotSetError(f"No PrimaryKey set for {self.__class__.__name__}().Update()", obj=type(self))

        infos = data.infos
        for name, value in columns.items():
            if name not in infos:
                raise AttributeError(
                    f"Unexpected attribute for {self.__class__.__name__}().Update({name}={value!r})",
                    name = name,
                    obj = self
                )
            try: value = msgspec.convert(value, data.infos[name].pytype, strict=False)
            except msgspec.ValidationError as error:
                raise ValueError(f"Mismatch value for {self.__class__.__name__}().Update({name}={value!r}) | {self.__class__.__name__}.{name} {error}") from None
            setattr(self, name, value)

        pk_value = getattr(self, data.pk.name)
        try:
            result = self.GetConnection().execute(
                Update(data.table)
                .Set(**{
                    info.column.name: getattr(self, name)
                    for name, info in data.infos.items()
                    if not info.is_pk
                })
                .Where(data.pk.column == pk_value)
            )
        except Exception as error:
            error = UpdateError(f"Update failed for {self.__class__.__name__}({data.pk.name}={pk_value!r}).Update() | {error}")
            error.add_note(repr(self))
            raise error

        match result.rowcount:
            case 1 | 0: return self
            case _:
                error = MultipleResultsError(
                    f"Multiple Results({ result.rowcount }) for {self.__class__.__name__}({data.pk.name}={pk_value!r}).Update(). "
                    "PrimaryKey should match 1 row only"
                )
                error.add_note(repr(self))
                raise error

    def Refresh (self) -> Self:
        """Refresh columns of `Model` object by `PrimaryKey` value
        - `NotFoundError` `MultipleResultsError`"""
        data = self.__data__
        if data.pk is None:
            raise PrimaryKeyNotSetError(f"No PrimaryKey set for {self.__class__.__name__}().Refresh()", obj=type(self))

        updated = self.Get(pk = getattr(self, data.pk.name))
        for name, value in updated.__dict__.items():
            if name == data.pk.name: continue
            setattr(self, name, value)

        return self

    # ------ #
    # Insert #
    # ------ #

    @classmethod
    def Insert (cls, **columns: SQLValue) -> Self:
        """Insert row of `Model` with `columns`
        - Avoid when a `PrimaryKey` don't exists on `Model` or `columns`
        - Efficient with `SQLite` `PostgreSQL` `MicrosoftSQL` `MySQL + PK`
        - `@classmethod`
        - `ValueError` `AttributeError` `InsertError`"""
        data = cls.__data__
        assert columns, f"At least 1 Column needed for {cls.__name__}.Insert()"

        for name in columns:
            value = columns[name]
            if name not in data.infos:
                raise AttributeError(
                    f"Unexpected attribute for {cls.__name__}.Insert({name}={value!r})",
                    name = name,
                    obj = cls
                )
            try: columns[name] = msgspec.convert(value, data.infos[name].pytype, strict=False)
            except msgspec.ValidationError as error:
                raise ValueError(f"Mismatch value for {cls.__name__}.Insert({name}={value!r}) | {cls.__name__}.{name} {error}") from None

        try: return ModelInsert(cls).insert_for_connection(columns)
        except Exception as error:
            error = InsertError(f"Insert failed for {cls.__name__}.Insert({ columns }) | {error}")
            error.add_note(repr(columns))
            raise error

__all__ = ["SQLizer"]