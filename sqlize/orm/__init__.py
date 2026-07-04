"""Package for `Object Relational Mapping`
#### Use `sqlize.orm.introspect` to auto generate `Model`
#### See `sqlize.orm.SQLizer` docstring for more info"""

from sqlize.orm import exceptions
from sqlize.orm.model import SQLizer
from sqlize.orm.column import Column, PrimaryKey
from sqlize.orm.introspect import introspect