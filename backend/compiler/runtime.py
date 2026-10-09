"""Shared runtime semantics for EvoLang.

This single module defines what every operation *means*. It is used by the
IR interpreter (the Digital Twin's reference engine), the constant folder,
and EvoVM. Because all three call the same functions, "the optimized program
behaves like the original" is a real, checkable statement rather than two
engines that could silently disagree.

Semantics
---------
* ``int``    32-bit two's-complement, wrapping on overflow.
* ``float``  IEEE-754 double (Python float).
* ``/``      on ints truncates toward zero (C semantics); ``%`` takes the sign
             of the dividend.
* Division / modulo by zero is a *runtime error*, not a value.
* ``string`` ``+`` concatenates. ``bool`` prints as ``true`` / ``false``.
"""

from __future__ import annotations

from typing import Any

INT_MIN = -(2 ** 31)
INT_MAX = 2 ** 31 - 1

TYPES = ("int", "float", "string", "bool")


class EvoRuntimeError(Exception):
    """A runtime fault raised by EvoLang code (not a bug in the compiler)."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


def wrap_int(v: int) -> int:
    return ((v + 2 ** 31) % 2 ** 32) - 2 ** 31


def is_int(v: Any) -> bool:
    return type(v) is int


def default_value(type_name: str) -> Any:
    return {"int": 0, "float": 0.0, "string": "", "bool": False}[type_name]


def type_of_value(v: Any) -> str:
    if type(v) is bool:
        return "bool"
    if type(v) is int:
        return "int"
    if type(v) is float:
        return "float"
    if type(v) is str:
        return "string"
    return "unknown"


def format_value(v: Any) -> str:
    if v is None:
        return "void"
    if type(v) is bool:
        return "true" if v else "false"
    if type(v) is float:
        return repr(v)
    return str(v)


def _trunc_div(a: int, b: int) -> int:
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def binary_op(op: str, a: Any, b: Any) -> Any:
    """Evaluate a binary IR/VM opcode. Operand types are guaranteed equal by
    the semantic analyzer (which inserts explicit int->float conversions)."""
    if op == "ADD":
        if is_int(a):
            return wrap_int(a + b)
        return a + b  # float add or string concat
    if op == "SUB":
        return wrap_int(a - b) if is_int(a) else a - b
    if op == "MUL":
        return wrap_int(a * b) if is_int(a) else a * b
    if op == "DIV":
        if b == 0:
            raise EvoRuntimeError("DivisionByZero", "Division by zero")
        if is_int(a):
            return wrap_int(_trunc_div(a, b))
        return a / b
    if op == "MOD":
        if b == 0:
            raise EvoRuntimeError("DivisionByZero", "Modulo by zero")
        return wrap_int(a - _trunc_div(a, b) * b)
    if op == "SHL":
        return wrap_int(a << (b & 31))
    if op == "SHR":
        return a >> (b & 31)
    if op == "LT":
        return a < b
    if op == "LE":
        return a <= b
    if op == "GT":
        return a > b
    if op == "GE":
        return a >= b
    if op == "EQ":
        return a == b
    if op == "NE":
        return a != b
    raise ValueError(f"unknown binary opcode {op}")


def unary_op(op: str, a: Any) -> Any:
    if op == "NEG":
        return wrap_int(-a) if is_int(a) else -a
    if op == "NOT":
        return not a
    if op == "I2F":
        return float(a)
    raise ValueError(f"unknown unary opcode {op}")


BINARY_OPS = ("ADD", "SUB", "MUL", "DIV", "MOD", "SHL", "SHR",
              "LT", "LE", "GT", "GE", "EQ", "NE")
UNARY_OPS = ("NEG", "NOT", "I2F")
COMPARE_OPS = ("LT", "LE", "GT", "GE", "EQ", "NE")
