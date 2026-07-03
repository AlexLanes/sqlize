# std
from typing import (
    Any, Self, get_args,
    dataclass_transform,
    get_type_hints, get_origin
)
# internal
from sqlize.shared import SQLValue, stringify
from sqlize.table import Table
from sqlize.connections import Connection
from sqlize.dml import Select, Delete, Update
from sqlize.orm.exceptions import *
from sqlize.orm.column import *
from sqlize.orm.select import ModelSelect
from sqlize.orm.insert import ModelInsert

@dataclass_transform(eq_default=False, kw_only_default=True)
class SQLizer:
    """`Base Model` used as inheritance
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
        data = self.__data__
        for name, value in kwargs.items():
            if name in data.infos:
                setattr(self, name, value)
            elif alias := data.alias.get(name):
                setattr(self, alias, value)
            else: raise AttributeError(
                f"Unexpected atribute for {self.__class__.__name__}({name}={value!r})",
                name = name,
                obj = self
            )

    def __init_subclass__ (cls) -> None:
        super().__init_subclass__()

        table = getattr(cls, "__table__", cls.__name__)
        if not isinstance(table, Table):
            table = Table(str(table), None)

        data = ModelData(table, {}, {})
        cls.__data__ = data

        # Class Defaults with Alias
        pk_seen = False
        for name, hint in cls.__dict__.items():
            if not isinstance(hint, Column): continue
            if not (orig := getattr(hint, "__orig_class__", None)):
                raise ValueError(f"Missing GenericType for {cls.__name__}.{name}[T](alias={hint.column!r})")

            is_pk = isinstance(hint, PrimaryKey)
            if pk_seen and is_pk:
                raise ValueError(f"Multiples PrimaryKeys not Supported for {cls.__name__}")

            pk_seen = is_pk
            pytype = get_args(orig)[0]
            alias = str(hint.column)
            column = table.Column(alias)

            # Update Class Descriptor
            hint.column = column
            data.alias[alias] = name
            data.infos[name] = ColumnInfo(pytype, column, is_pk)

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
            data.infos[name] = ColumnInfo(pytype, column, is_pk)

            # Instance.attribute -> T
            descriptor = origin(column=column)
            descriptor.__set_name__(cls, name)
            setattr(cls, name, descriptor)

    def __repr__ (self) -> str:
        name = self.__class__.__name__
        return f"<{name} {self.to_dict()}>"

    def __eq__ (self, other: object) -> bool:
        return (
            self.to_dict() == other.to_dict()
            if isinstance(other, SQLizer)
            else False
        )

    def to_dict (self) -> dict[str, Any]:
        """transforms `Model` to `dict[str, Any]`"""
        return dict(self.__dict__)

    def stringify (self, indent: bool = False) -> str:
        """Tranforms `Model` to `JSON String`"""
        return stringify(self.to_dict(), indent=indent)

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
    def Get (cls, pk: SQLValue) -> Self:
        """Select row of `Model` by `PrimaryKey` value
        - `@classmethod`
        - `NotFoundError` `MultipleResultsError` `PrimaryKeyNotSetError`"""
        data = cls.__data__
        primary_key = data.primary_key
        if primary_key is None:
            raise PrimaryKeyNotSetError(f"No PrimaryKey set for {cls.__name__}.Get({pk=})", obj=cls)

        # Validate Value
        pk_name = data.alias.get(primary_key.name, primary_key.name)
        expected = data.infos[pk_name].pytype
        if not isinstance(pk, expected):
            raise ValueError(f"Mismatch value for PrimaryKey {cls.__name__}.Get({pk=}) | {cls.__name__}.{pk_name} expects {expected}")

        # SELECT
        result = cls.GetConnection().execute(
            Select(*data.all_columns)
            .From(data.table)
            .Where(primary_key == pk)
        )

        match result.returned:
            case 1: return cls(**result.first)
            case 0:
                raise NotFoundError(
                    f"No Result for {cls.__name__}.Get({pk=})",
                    cls = cls,
                    values = { pk_name: pk }
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
        `Model.Select().Where(Model.id < 100).All()`  
        `Model.Select().OrderBy(Model.id.DESC).Limit(1).First()`"""
        return ModelSelect(*cls.__data__.all_columns, model=cls)

    # ------ #
    # Delete #
    # ------ #

    def Remove (self) -> None:
        """Delete row of `Model` object by `PrimaryKey` value
        - `NotFoundError` `MultipleResultsError` `PrimaryKeyNotSetError`"""
        data = self.__data__
        pk = data.primary_key
        if pk is None:
            raise PrimaryKeyNotSetError(f"No PrimaryKey set for {self.__class__.__name__}().Remove()", obj=type(self))

        pk_name = data.alias.get(pk.name, pk.name)
        pk_value = getattr(self, pk_name)
        delete = Delete(data.table).Where(pk == pk_value)
        rowcount = self.GetConnection().execute(delete).rowcount

        match rowcount:
            case 1: return
            case 0:
                error = NotFoundError(
                    f"No Result for {self.__class__.__name__}({pk_name}={pk_value!r}).Remove()",
                    cls = type(self),
                    values = self.to_dict()
                )
                error.add_note(repr(self))
                raise error
            case _:
                error = MultipleResultsError(
                    f"Multiple Results({ rowcount }) for {self.__class__.__name__}({pk_name}={pk_value!r}).Remove(). "
                    "PrimaryKey should match 1 row only"
                )
                error.add_note(repr(self))
                raise error

    @classmethod
    def Delete (cls, pk: SQLValue, *, raise_if_not_found: bool = True) -> bool:
        """Delete row of `Model` by `PrimaryKey` value
        - Returns `deleted: bool`
        - `@classmethod`
        - `NotFoundError` `MultipleResultsError` `PrimaryKeyNotSetError`"""
        data = cls.__data__
        primary_key = data.primary_key
        if primary_key is None:
            raise PrimaryKeyNotSetError(f"No PrimaryKey set for {cls.__name__}.Delete({pk=})", obj=cls)

        # Validate Value
        pk_name = data.alias.get(primary_key.name, primary_key.name)
        expected = data.infos[pk_name].pytype
        if not isinstance(pk, expected):
            raise ValueError(f"Mismatch value for PrimaryKey {cls.__name__}.Delete({pk=}) | {cls.__name__}.{pk_name} expects {expected}")

        # DELETE
        result = cls.GetConnection().execute(
            Delete(data.table)
            .Where(primary_key == pk)
        )

        match result.rowcount:
            case 1: return True
            case 0 if not raise_if_not_found: return False
            case 0: raise NotFoundError(
                f"No Result for {cls.__name__}.Delete({pk=})",
                cls = cls,
                values = { pk_name: pk }
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
        - `columns` used to update `self` before executing `Update`
        - `Refresh()` can be chained to sync with `Connection`
        - `UpdateError` `MultipleResultsError` `PrimaryKeyNotSetError`"""
        data = self.__data__
        pk = data.primary_key
        if pk is None:
            raise PrimaryKeyNotSetError(f"No PrimaryKey set for {self.__class__.__name__}().Update()", obj=type(self))

        infos = data.infos
        for name, value in columns.items():
            if name not in infos:
                raise AttributeError(
                    f"Unexpected atribute for {self.__class__.__name__}().Update({name}={value!r})",
                    name = name,
                    obj = self
                )
            setattr(self, name, value)

        pk_name = data.alias.get(pk.name, pk.name)
        pk_value = getattr(self, pk_name)
        try:
            result = self.GetConnection().execute(
                Update(data.table)
                .Set(**{
                    info.column.name: getattr(self, name)
                    for name, info in data.infos.items()
                    if not info.is_pk
                })
                .Where(pk == pk_value)
            )
        except Exception:
            error = UpdateError(f"Update failed for {self.__class__.__name__}({pk_name}={pk_value!r}).Update()")
            error.add_note(repr(self))
            raise error

        match result.rowcount:
            case 1 | 0: return self
            case _:
                error = MultipleResultsError(
                    f"Multiple Results({ result.rowcount }) for {self.__class__.__name__}({pk_name}={pk_value!r}).Update(). "
                    "PrimaryKey should match 1 row only"
                )
                error.add_note(repr(self))
                raise error

    def Refresh (self) -> Self:
        """Refresh columns of `Model` object by `PrimaryKey` value
        - `NotFoundError` `PrimaryKeyNotSetError`"""
        data = self.__data__
        pk = data.primary_key
        if pk is None:
            raise PrimaryKeyNotSetError(f"No PrimaryKey set for {self.__class__.__name__}().Refresh()", obj=type(self))

        updated = self.Get(pk = getattr(self, data.alias.get(pk.name, pk.name)))
        for name, info in data.infos.items():
            if info.is_pk: continue
            value = getattr(updated, name)
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
        - `InsertError` `AttributeError`"""
        assert columns, f"At least 1 Column needed for {cls.__name__}.Insert()"

        infos = cls.__data__.infos
        for name, value in columns.items():
            if name not in infos:
                raise AttributeError(
                    f"Unexpected atribute for {cls.__name__}.Insert({name}={value!r})",
                    name = name,
                    obj = cls
                )

        try: return ModelInsert(cls).insert_for_connection(columns)
        except Exception:
            raise InsertError(f"Insert failed for {cls.__name__}.Insert({ columns })")

__all__ = ["SQLizer"]