# internal
from sqlize.shared import MappingAny

class InsertError (ValueError): ...
class UpdateError (ValueError): ...
class MultipleResultsError  (AttributeError): ...
class PrimaryKeyNotSetError (AttributeError): ...

class NotFoundError (Exception):
    def __init__ (self, *args: object, cls: type, values: MappingAny) -> None:
        super().__init__(*args)
        self.cls = cls
        self.values = values

class NoConnectionAvailableError (Exception):
    def __init__ (self) -> None:
        super().__init__("No connection available to use with ORM")
        self.add_note("Open Connection needed. Use Connection.AddInstance() and make sure to keep it alive")

__all__ = [
    "UpdateError",
    "InsertError",
    "NotFoundError",
    "MultipleResultsError",
    "PrimaryKeyNotSetError",
    "NoConnectionAvailableError",
]