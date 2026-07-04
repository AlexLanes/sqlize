# SQLize

Create SQL syntax with a natural python builder.  
Supports automatic execution on multiple `sqlize.connections`

### Table | Column | Expression
> See `E` docstring for full info on `Expression`
```python
from sqlize import E, A, T

# Table
users = T.users
users = T.users.Schema("public")

# Users.column_name
users.column_name
T.users.column_name
# Especial
T.users.Column("spaced named")
# Alias with no Table needed
A.All(), A.column_name

# Columns can build Expressions
users.id == 1
users.id + 1
users.name.Upper()
(users.id == 1) & (users.name == None)

# Constant Expression
E.CURRENT_TIMESTAMP
E.NULL
E.TRUE
E.Value("1")
```

### DMLs
`Select` `Update` `Delete` `Insert` `InsertMany` `Upsert`
> See `docstring` of each `Statement` for more info and examples
```python
from sqlize import E, A, T, Select

# Tables used
users = T.users
orders = T.orders

# Build
select = (
    Select(
        users.id,
        users.name.Trim().As("user_name"),
        orders.id.As("order_id"),
        (orders.quantity * orders.value).As("total_value"),
        E.LOCAL_TIMESTAMP.As("timestamp")
    )
    .From(users)
    .Join(orders, orders.user_id == users.id)
    .Where( (users.id == 1) | (users.role.Upper() == "ADMIN") )
    .OrderBy(
        users.id.ASC,
        A.user_name.ASC.NULLS_LAST,
        (users.id % 2).DESC
    )
    .Offset(0)
    .Limit(100)
)

# Transform
sql, params = select.to_sql()
```

### Connections
Package to automatically handle `Connections` of drivers and execute `Statements`
- `Connection(conn)` Simplified wrapper to `DB API 2.0`
- `ResultSQL` `@dataclass` used by `cursor.execute() cursor.executemany() Connection.execute()`

Database         | Extra Dependency | Module
:--------------- | :--------------: | :----:
`SQLite`         | -                | `sqlize.connections.sqlite`
`MySQL`          | `[mysql]`        | `sqlize.connections.mysql`
`Oracle`         | `[oracle]`       | `sqlize.connections.oracle`
`PostgreSQL`     | `[postgresql]`   | `sqlize.connections.postgresql`
`MicrosoftSQL`   | `[mssql]`        | `sqlize.connections.mssql`
`ConnectionODBC` | `[odbc]`         | `sqlize.connections.odbc`

```python
from sqlize import A, T, Select
from sqlize.connections.sqlite import SQLite

with SQLite() as conn:
    result = conn.execute(
        Select(A.All())
        .From(T.users)
    )
    result.rowcount
    result.returned
    result.rows
    result.first
    result.to_dict()

    conn.cursor()
    conn.commit()
    conn.rollback()

    conn.tables()
    conn.columns("users")
```

### ORM
Package for `Object Relational Mapping`

> Use `sqlize.orm.introspect` to auto generate `Model`
```python
from sqlize.orm import introspect
from sqlize.connections.postgresql import PostgreSQL

with PostgreSQL.Connect(user="postgres", password="admin") as conn:
    introspect(conn, table_name="users")
```

> Use `sqlize.orm.SQLizer` as `Model`
```python
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