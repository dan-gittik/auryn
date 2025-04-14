import pathlib
from typing import Any

from .junk import Junk


def transpile(
    template: str | pathlib.Path,
    /,
    *,
    standalone: bool = False,
    load: str | pathlib.Path | dict[str, Any] | None = None,
    load_common: bool | None = None,
) -> str:
    if isinstance(template, str) and "\n" in template:
        junk = Junk.from_string(template, stack_level=1)
    else:
        junk = Junk.from_file(template, stack_level=1)
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
    if isinstance(template, str) and "\n" in template:
        junk = Junk.from_string(template, stack_level=1)
    else:
        junk = Junk.from_file(template, stack_level=1)
    junk.transpile(load=load, load_common=load_common)
    return junk.evaluate(context, **context_kwargs)


def evaluate(
    path: str | pathlib.Path,
    context: dict[str, Any] | None = None,
    /,
    **context_kwargs: Any,
) -> str:
    return Junk.evaluate_standalone(path, context, stack_level=1, **context_kwargs)
