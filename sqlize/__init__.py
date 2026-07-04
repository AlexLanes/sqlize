"""
# SQLize

Create SQL syntax with a natural python builder.  
Supports automatic execution on multiple connections

### Table | Column | Expression
See `E` docstring for full info on `Expression`

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
See `docstring` of each `Statement` for more info and examples

### Connections
Package to automatically handle `Connections` of drivers and execute `Statements`  
See package `docstring` for more info

### ORM
Package for `Object Relational Mapping`  
See package `docstring` for more info
"""

from sqlize.expression import E # Expression     Builder
from sqlize.column     import A # AliasedColumn  Builder
from sqlize.table      import T # Table + Column Builder

# Connection
from sqlize.connections import Connection, ResultSQL

# DMLs
from sqlize.dml import *

# ORM
from sqlize import orm