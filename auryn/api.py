import pathlib
from typing import Any

from .junk import Junk


def transpile(
    template: str | pathlib.Path,
    /,
    *,
    sourcemap: bool | None = None,
    load: str | pathlib.Path | dict[str, Any] | None = None,
    load_common: bool | None = None,
    standalone: bool = False,
) -> str:
    junk = Junk(template, stack_level=1, sourcemap=sourcemap)
    junk.transpile(load=load, load_common=load_common)
    return junk.to_string(standalone=standalone)


def render(
    template: str | pathlib.Path,
    context: dict[str, Any] | None = None,
    /,
    *,
    load: str | pathlib.Path | dict[str, Any] | None = None,
    load_common: bool | None = None,
    **context_kwargs: Any,
) -> str:
    junk = Junk(template, stack_level=1)
    junk.transpile(load=load, load_common=load_common)
    return junk.evaluate(context, **context_kwargs)


def evaluate(
    path: str | pathlib.Path,
    context: dict[str, Any] | None = None,
    /,
    **context_kwargs: Any,
) -> str:
    if isinstance(path, str) and "\n" in path:
        code_lines = path.splitlines()
    else:
        path = pathlib.Path(path)
        code_lines = path.read_text().splitlines()
    junk = Junk(stack_level=1)
    junk.code_lines = code_lines
    return junk.evaluate(context, **context_kwargs)
