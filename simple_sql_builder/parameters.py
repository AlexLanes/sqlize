from typing import Protocol, Literal

class IPositionalParameter (Protocol):
    identifier: str
    def next (self) -> str:
        """Return the next parameter when called"""
        ...

class QuestionMarkPositional (IPositionalParameter):
    identifier = "?"
    def next (self) -> str:
        return self.identifier

class PercentPositional (IPositionalParameter):
    identifier = "%s"
    def next (self) -> str:
        return self.identifier

class ColonNumberPositional (IPositionalParameter):
    identifier = ":N"
    def __init__ (self) -> None:
        self.n = 0

    def next (self) -> str:
        self.n += 1
        return f":{self.n}"

type DefaultsPositional = Literal["?", "%s", ":N"]
POSITIONAL_PARAMETERS: dict[str, type[IPositionalParameter]] = {
    "?": QuestionMarkPositional,
    "%s": PercentPositional,
    ":N": ColonNumberPositional
}

__all__ = [
    "DefaultsPositional",
    "POSITIONAL_PARAMETERS",
    "IPositionalParameter",
]