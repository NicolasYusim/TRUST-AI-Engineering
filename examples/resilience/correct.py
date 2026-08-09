"""Executable reference: bounded model fallback for generated Python text.

Guarantees:
- deterministic fallback order;
- explicit unavailable result when all candidates fail;
- syntax and a conservative forbidden-operation screen before return;
- no generated code is executed.

Does not guarantee functional correctness or make returned code safe to execute.
A production code runner still needs isolation and task-specific tests.
"""

from __future__ import annotations

import ast
import math
import time
from dataclasses import dataclass, field
from typing import Callable, Protocol


class TemporaryModelError(RuntimeError):
    pass


class ModelClient(Protocol):
    name: str

    def generate(self, description: str, timeout_ms: int) -> str:
        ...


@dataclass
class FakeModelClient:
    name: str
    result: str | Exception
    calls: int = 0
    timeouts_ms: list[int] = field(default_factory=list)

    def generate(self, description: str, timeout_ms: int) -> str:
        self.calls += 1
        self.timeouts_ms.append(timeout_ms)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@dataclass(frozen=True)
class GenerationResult:
    code: str | None
    route: str
    degraded: bool
    reason: str | None


FORBIDDEN_IMPORTS = frozenset({"os", "subprocess", "socket", "shutil"})
FORBIDDEN_CALLS = frozenset({"eval", "exec", "open", "compile", "__import__"})


def validate_generated_code(code: str) -> tuple[bool, str | None]:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return False, f"syntax_error:{exc.msg}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".", 1)[0] in FORBIDDEN_IMPORTS for alias in node.names):
                return False, "forbidden_import"
        if isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".", 1)[0] in FORBIDDEN_IMPORTS:
                return False, "forbidden_import"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_CALLS:
                return False, "forbidden_call"
    return True, None


def generate_code(
    description: str,
    *,
    primary: ModelClient,
    secondary: ModelClient,
    timeout_ms: int = 4000,
    clock: Callable[[], float] = time.monotonic,
) -> GenerationResult:
    # Evidence label: illustrative. The timeout demonstrates a bound and must be
    # calibrated in a deployment-specific manifest.
    if timeout_ms <= 0:
        raise ValueError("timeout_ms must be positive")

    deadline = clock() + timeout_ms / 1000
    failures: list[str] = []
    for index, client in enumerate((primary, secondary)):
        remaining_seconds = deadline - clock()
        if remaining_seconds <= 0:
            failures.append("total_timeout")
            break
        remaining_ms = max(1, math.ceil(remaining_seconds * 1000))
        try:
            candidate = client.generate(description, remaining_ms)
        except Exception as exc:
            category = (
                "temporary"
                if isinstance(exc, TemporaryModelError)
                else f"error:{type(exc).__name__}"
            )
            failures.append(f"{client.name}:{category}:{exc}")
            continue

        valid, reason = validate_generated_code(candidate)
        if valid:
            return GenerationResult(
                code=candidate,
                route=client.name,
                degraded=index > 0,
                reason=None,
            )
        failures.append(f"{client.name}:{reason}")

    return GenerationResult(
        code=None,
        route="unavailable",
        degraded=True,
        reason=";".join(failures),
    )
