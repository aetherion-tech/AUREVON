"""Render preserved Pine explanation expressions without executing source code.

Only literals, scalar operators and an explicit helper allowlist are interpreted.
This resource is repository-owned; callers cannot supply expressions/functions.
"""

import json
import math
import re
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

HELPERS: dict[str, Any] = json.loads(
    Path(__file__).with_name("text.json").read_text(encoding="utf-8")
)
TOKEN = re.compile(
    r'\s*("(?:\\.|[^"\\])*"|\d+(?:\.\d+)?|[A-Za-z_]\w*(?:\.\w+)*|>=|<=|==|!=|[-+*/%<>()?:,])'
)


@lru_cache(maxsize=64)
def parse(expression: str) -> Any:
    tokens: list[str] = []
    position = 0
    while position < len(expression):
        match = TOKEN.match(expression, position)
        if match is None:
            raise ValueError("unsupported explanation expression")
        tokens.append(match[1])
        position = match.end()
    index = 0
    powers = {
        "or": 1,
        "and": 2,
        "==": 3,
        "!=": 3,
        "<": 3,
        ">": 3,
        "<=": 3,
        ">=": 3,
        "+": 4,
        "-": 4,
        "*": 5,
        "/": 5,
        "%": 5,
    }

    def node(minimum: int = 0) -> Any:
        nonlocal index
        token = tokens[index]
        index += 1
        if token == "(":
            left = node()
            if tokens[index] != ")":
                raise ValueError("unclosed explanation group")
            index += 1
        elif token in ("not", "-", "+"):
            left = ("unary", token, node(6))
        elif token.startswith('"') or token[0].isdigit():
            left = ("literal", json.loads(token))
        elif index < len(tokens) and tokens[index] == "(":
            index += 1
            args = []
            while tokens[index] != ")":
                args.append(node())
                if tokens[index] != ",":
                    break
                index += 1
            if tokens[index] != ")":
                raise ValueError("unclosed explanation call")
            index += 1
            left = ("call", token, args)
        else:
            left = ("name", token)
        while index < len(tokens):
            op = tokens[index]
            if op == "?" and minimum == 0:
                index += 1
                yes = node()
                if tokens[index] != ":":
                    raise ValueError("invalid explanation ternary")
                index += 1
                left = ("if", left, yes, node())
            elif op in powers and powers[op] >= minimum:
                index += 1
                left = ("binary", op, left, node(powers[op] + 1))
            else:
                break
        return left

    result = node()
    if index != len(tokens):
        raise ValueError("trailing explanation expression")
    return result


def number_text(value: Any, pattern: str = "") -> str:
    if value is None:
        return "NaN"
    if isinstance(value, str):
        return value
    if type(value) is bool:
        return "true" if value else "false"
    if not pattern:
        return str(value)
    digits = len(pattern.split(".")[1]) if "." in pattern else 0
    scale = 10**digits
    rounded = math.floor(value * scale + 0.5) / scale
    text = f"{rounded:.{digits}f}"
    return text.rstrip("0").rstrip(".") if digits else text


def render(name: str, context: dict[str, Any], *args: Any) -> str:
    return str(_helper(name, context, list(args)))


def _helper(name: str, context: dict[str, Any], args: list[Any]) -> Any:
    if name == "f_riskLbl":
        return context["risk"]["label"]
    if name == "f_riskTxt":
        return context["risk"]["text"]
    spec = HELPERS[name]
    if len(args) != len(spec["arguments"]):
        raise ValueError("invalid explanation helper arguments")
    env = context | dict(zip(spec["arguments"], args))
    if name == "f_statTxt":
        env["n"] = env["cN"][env["i"]]
    return evaluate(parse(spec["expression"]), env)


def evaluate(tree: Any, env: dict[str, Any]) -> Any:
    kind = tree[0]
    if kind == "literal":
        return tree[1]
    if kind == "name":
        return (
            {"true": True, "false": False, "na": None}.get(tree[1])
            if tree[1] in ("true", "false", "na")
            else env[tree[1]]
        )
    if kind == "if":
        return evaluate(tree[2] if evaluate(tree[1], env) else tree[3], env)
    if kind == "unary":
        value = evaluate(tree[2], env)
        return (
            not value
            if tree[1] == "not"
            else None
            if value is None
            else -value
            if tree[1] == "-"
            else value
        )
    if kind == "call":
        name = tree[1]
        args = [evaluate(x, env) for x in tree[2]]
        functions: dict[str, Callable[..., Any]] = {
            "str.tostring": number_text,
            "math.abs": lambda x: abs(x) if x is not None else None,
            "math.round": lambda x: math.floor(x + 0.5) if x is not None else None,
            "array.get": lambda array, index: array[index],
        }
        return functions[name](*args) if name in functions else _helper(name, env, args)
    op = tree[1]
    a = evaluate(tree[2], env)
    if op == "and":
        return bool(a and evaluate(tree[3], env))
    if op == "or":
        return bool(a or evaluate(tree[3], env))
    b = evaluate(tree[3], env)
    if a is None or b is None:
        return False if op in ("==", "!=", "<", ">", "<=", ">=") else None
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        return a / b if b else None
    if op == "%":
        return a % b
    if op == "==":
        return a == b
    if op == "!=":
        return a != b
    if op == "<":
        return a < b
    if op == ">":
        return a > b
    if op == "<=":
        return a <= b
    if op == ">=":
        return a >= b
    raise ValueError("unsupported explanation operator")
