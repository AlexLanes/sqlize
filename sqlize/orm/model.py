# std
from typing import (
    Self, get_args,
    get_type_hints, get_origin
)
from typing import dataclass_transform
# internal
from sqlize.shared import SQLValue, MappingAny, stringify
from sqlize.table import Table
from sqlize.column import E, A
from sqlize.connections import Connection
from sqlize.dml import Select, Delete, Update
from sqlize.orm.exceptions import *
from sqlize.orm.column import *
from sqlize.orm.select import ModelSelect

@dataclass_transform(eq_default=False, kw_only_default=True)
class SQLizer:
    """`Base Model` used as inheritance
    - `__table__` to set the name of table `Default: str(Model.__name__)`
    - `Model.property` are transformed into `Columns`
    - `Instance.property` type is preserved

    ### Example
    ```
    from sqlize.connections.sqlite import SQLite
    from sqlize.orm import SQLizer, PrimaryKey, Column

    # Define Model
    class Users (SQLizer):
        __table__ = "Users"
        id: PrimaryKey[int]
        name: Column[str]

    # Open a Connection
    # Add to be used by other methods
    with SQLite().AddInstance() as connection:

        # Select PK
        user_1 = Users.Get(id=1)
        print(user_1)
        # Select Custom
        for user in Users.Select().OrderBy(Users.id.ASC).Limit(10).All():
            print(user.id, user.name)

        # Update
        user_1.name = "Foo"
        user_1.Update(name="Foo", ...)
        # Refresh Columns
        user_1.Refresh()

        # Delete PK
        deleted = Users.Delete(raise_if_not_found=False, id=1)
        # Delete Object
        user_1.Remove()

        # Save
        connection.commit()
    ```
    """

    __table__: Table | str
    __data__: ModelData

    def __init__ (self, **kwargs: SQLValue) -> None:
        infos = self.__data__.infos
        for name, value in kwargs.items():
            if name not in infos:
                raise AttributeError(
                    f"Unexpected atribute for {self.__class__.__name__}({name}={value!r})",
                    name = name,
                    obj = self
                )
            setattr(self, name, value)

    def __repr__ (self) -> str:
        name = self.__class__.__name__
        return f"<{name} {self.to_dict()}>"

    def __init_subclass__ (cls) -> None:
        super().__init_subclass__()

        table = getattr(cls, "__table__", cls.__name__)
        if not isinstance(table, Table):
            table = Table(str(table), None)

        columns = ([], [])
        infos: dict[str, ColumnInfo] = {}
        cls.__data__ = ModelData(table, infos, columns)

        for name, hint in get_type_hints(cls, include_extras=True).items():
            origin = get_origin(hint)
            match origin:
                case _ if origin is PrimaryKey:
                    is_pk = True
                case _ if origin is Column:
                    is_pk = False
                case _ if hint in (PrimaryKey, Column):
                    raise ValueError(f"Missing type of {hint.__name__}[T] for {cls.__name__}.{name}")
                case _: continue

            # Class.attribute -> Column[T]
            pytype = get_args(hint)[0]
            column = table.Column(name)
            columns[0 if is_pk else 1].append(column)
            infos[name] = ColumnInfo(name, pytype, column)

            # Instance.attribute -> T
            descriptor = origin(column)
            descriptor.__set_name__(cls, name)
            setattr(cls, name, descriptor)

    def to_dict (self) -> MappingAny:
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
    def Count (cls) -> int:
        """Count total of rows of `Model`"""
        result = cls.GetConnection().execute(
            Select(A.All().Count().As("total"))
            .From(cls.__data__.table)
        )
        return int(result.first["total"])

    @classmethod
    def Get (cls, **pk: SQLValue) -> Self:
        """Select columns of `Model` by named `PrimaryKey` values
        - `NotFoundError` `MultipleResultsError` `PrimaryKeyNotSetError`"""
        pks, columns = cls.__data__.columns
        if not pks or not pk:
            raise PrimaryKeyNotSetError(f"No PrimaryKey set for {cls.__name__}.Get({ pk })", obj=cls)

        connection = cls.GetConnection()
        infos = cls.__data__.infos
        pk_names = [pk.name for pk in pks]

        # Validate name value
        # Create Where Expression
        where = E
        for pk_name, pk_value in pk.items():
            assert pk_name in pk_names, f"Mismatch PrimaryKey({ pk_name }) on {cls}. Expected {pk_names}"
            info = infos[pk_name]
            assert isinstance(pk_value, info.pytype), f"Mismatch PrimaryKey({ pk_name }) Value({pk_value!r}) on {cls}"

            # Combine where expression
            exp = info.column == pk_value
            where = exp if where is E else where.And(exp)

        # GET
        result = connection.execute(
            Select(*pks, *columns)
            .From(cls.__data__.table)
            .Where(where)
        )
        match result.returned:
            case 1: return cls(**result.first)
            case 0:
                raise NotFoundError(
                    f"No Result for {cls.__name__}.Get({ pk })",
                    cls = cls,
                    values = pk
                )
            case _:
                raise MultipleResultsError(
                    f"Multiple Results({ result.returned }) for {cls.__name__}.Get({ pk }). "
                    f"PrimaryKey(s) should match 1 row only"
                )

    @classmethod
    def Select (cls) -> ModelSelect[Self]:
        """Build custom `Select` with `Select().From()` already set
        - New Methods `All()` `First()` `Count()`
        ### Example
        `Model.Select().Where(Model.id < 100).All()`  
        `Model.Select().OrderBy(Model.id.DESC).Limit(1).First()`"""
        columns = cls.__data__.columns
        return ModelSelect(*columns[0], *columns[1], model=cls)

    # ------ #
    # Delete #
    # ------ #

    def Remove (self) -> None:
        """Delete `Model` object by `PrimaryKey` values
        - `NotFoundError` `MultipleResultsError` `PrimaryKeyNotSetError`"""
        pks, _ = self.__data__.columns
        if not pks:
            raise PrimaryKeyNotSetError(f"No PrimaryKey set for {self}", obj=self)

        connection = self.GetConnection()

        where = E
        for pk in pks:
            exp = pk == getattr(self, pk.name)
            where = exp if where is E else where.And(exp)

        delete = Delete(self.__data__.table).Where(where)
        rowcount = connection.execute(delete).rowcount
        match rowcount:
            case 1: return
            case 0: raise NotFoundError(
                f"No Result for {self.__class__.__name__}().Remove()",
                cls = type(self),
                values = self.to_dict()
            )
            case _: raise MultipleResultsError(
                f"Multiple Results({ rowcount }) for {self.__class__.__name__}().Remove({ self.to_dict() }). "
                f"PrimaryKey(s) should match 1 row only"
            )

    @classmethod
    def Delete (cls, raise_if_not_found: bool = True, **pk: SQLValue) -> bool:
        """Delete `Model` by named `PrimaryKey` values
        - Returns `deleted: bool`
        - `NotFoundError` `MultipleResultsError` `PrimaryKeyNotSetError`"""
        pks, _ = cls.__data__.columns
        if not pks or not pk:
            raise PrimaryKeyNotSetError(f"No PrimaryKey set for {cls.__name__}.Delete({ pk })", obj=cls)

        connection = cls.GetConnection()
        infos = cls.__data__.infos
        pk_names = [pk.name for pk in pks]

        # Validate name value
        # Create Where Expression
        where = E
        for pk_name, pk_value in pk.items():
            assert pk_name in pk_names, f"Mismatch PrimaryKey({ pk_name }) on {cls}. Expected {pk_names}"
            info = infos[pk_name]
            assert isinstance(pk_value, info.pytype), f"Mismatch PrimaryKey({ pk_name }) Value({pk_value!r}) on {cls}"

            # Combine where expression
            exp = info.column == pk_value
            where = exp if where is E else where.And(exp)

        # Delete
        delete = Delete(cls.__data__.table).Where(where)
        rowcount = connection.execute(delete).rowcount
        match rowcount:
            case 1: return True
            case 0 if not raise_if_not_found: return False
            case 0: raise NotFoundError(
                f"No Result for {cls.__name__}.Delete({ pk })",
                cls = cls,
                values = pk
            )
            case _: raise MultipleResultsError(
                f"Multiple Results({ rowcount }) for {cls.__name__}.Delete({ pk }). "
                f"PrimaryKey(s) should match 1 row only"
            )

    # ------ #
    # Update #
    # ------ #

    def Update (self, **update: SQLValue) -> Self:
        """Update columns of `Model` by `PrimaryKey` values
        - `update` used to update `self` before executing `Update`
        - `NotFoundError` `PrimaryKeyNotSetError` `MultipleResultsError`"""
        pks, columns = self.__data__.columns
        if not pks:
            raise PrimaryKeyNotSetError(f"No PrimaryKey set for {self}", obj=self)

        connection = self.GetConnection()

        infos = self.__data__.infos
        for name, value in update.items():
            if name not in infos:
                raise AttributeError(
                    f"Unexpected atribute for {self.__class__.__name__}().Update({name}={value!r})",
                    name = name,
                    obj = self
                )
            setattr(self, name, value)

        where = E
        for pk in pks:
            exp = pk == getattr(self, pk.name)
            where = exp if where is E else where.And(exp)

        result = connection.execute(
            Update(self.__data__.table)
            .Set(**{
                column.name: getattr(self, column.name)
                for column in columns
            })
            .Where(where)
        )

        match result.rowcount:
            case 1: return self
            case 0: raise NotFoundError(
                f"No Result for {self.__class__.__name__}().Update()",
                cls = type(self),
                values = self.to_dict()
            )
            case _: raise MultipleResultsError(
                f"Multiple Results({ result.rowcount }) for {self.__class__.__name__}().Update(). "
                f"PrimaryKey(s) should match 1 row only"
            )

    def Refresh (self) -> Self:
        """Refresh Columns of `Model` object by `PrimaryKey` values
        - `NotFoundError` `PrimaryKeyNotSetError`"""
        pks, columns = self.__data__.columns
        if not pks:
            raise PrimaryKeyNotSetError(f"No PrimaryKey set for {self}", obj=self)

        updated = self.Get(**{ pk.name: getattr(self, pk.name) for pk in pks })
        for column in columns:
            name = column.name
            value = getattr(updated, name)
            setattr(self, name, value)

        return self

__all__ = ["SQLizer"]