# internal
from sqlize.shared import SQLValue

class NotFoundException (Exception):
    def __init__ (self, *args: object, cls: type, values: dict[str, SQLValue]) -> None:
        super().__init__(*args)
        self.cls = cls
        self.values = values

class NoConnectionAvailableException (Exception):
    def __init__ (self) -> None:
        super().__init__("No connection available to use with ORM")
        self.add_note("Open Connection needed. Use Connection.AddInstance() and make sure to keep it alive")

__all__ = [
    "NotFoundException",
    "NoConnectionAvailableException",
]