# std
from typing import Self, get_args, get_type_hints, get_origin
# internal
from sqlize.shared import SQLValue, MappingAny, stringify
from sqlize.table import Table
from sqlize.column import E, A
from sqlize.dml import Select
from sqlize.connections import Connection
from sqlize.orm.exceptions import *
from sqlize.orm.column import *
from sqlize.orm.select import ModelSelect

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
    with SQLite().AddInstance() as sqlite:

        # Select PK
        print(Users.Get(id=1))

        # Select Custom
        for user in Users.Select().OrderBy(Users.id.ASC).Limit(10).All():
            print(user.id, user.name)
    ```
    """

    __table__: Table | str
    __data__: ModelData

    def __init__ (self, data: MappingAny) -> None:
        for name, value in data.items():
            setattr(self, name, value)

    def __repr__ (self) -> str:
        name = self.__class__.__name__
        return f"<{name} {self.__dict__}>"

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

    @staticmethod
    def GetConnection () -> Connection:
        """Get last opened `Instance: Connection`
        - `NoConnectionAvailableException`"""
        try: return Connection.GetInstance()
        except Exception:
            raise NoConnectionAvailableException

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
        - `NotFoundException`"""
        pks, columns = cls.__data__.columns
        assert pks, f"No PrimaryKey set for {cls}"

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
            if where is E: where = exp
            else: where.And(exp)

        # GET
        result = connection.execute(
            Select(*pks, *columns)
            .From(cls.__data__.table)
            .Where(where)
        )
        match result.returned:
            case 1:
                obj = object.__new__(cls)
                obj.__dict__.update(result.first)
                return obj
            case 0:
                raise NotFoundException(
                    f"No Result for {cls.__name__}.Get({ pk })",
                    cls = cls,
                    values = pk
                )
            case _:
                raise AssertionError(
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

    def to_dict (self) -> MappingAny:
        """transforms `Model` to `dict[str, Any]`"""
        return dict(self.__dict__)

    def stringify (self, indent: bool = False) -> str:
        """Tranforms `Model` to `JSON String`"""
        return stringify(self.to_dict(), indent=indent)

__all__ = ["SQLizer"]