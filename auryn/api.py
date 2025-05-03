import pathlib
from typing import Any

from .junk import Junk


def transpile(
    template: str | pathlib.Path,
    meta_context: dict[str, Any] | None = None,
    /,
    *,
    load_common: bool | None = None,
    add_source_comments: bool | None = None,
    load: str | pathlib.Path | dict[str, Any] | None = None,
    standalone: bool | None = None,
    **meta_context_kwargs: Any,
) -> str:
    junk = Junk(template, load_common=load_common, add_source_comments=add_source_comments, stack_level=1)
    if load:
        junk.load(load)
    junk.transpile(meta_context, **meta_context_kwargs)
    return junk.to_string(standalone=standalone)


def render(
    template: str | pathlib.Path,
    context: dict[str, Any] | None = None,
    /,
    *,
    load_common: bool | None = None,
    load: str | pathlib.Path | dict[str, Any] | None = None,
    meta_context: dict[str, Any] | None = None,
    **context_kwargs: Any,
) -> str:
    junk = Junk(template, load_common=load_common, stack_level=1)
    if load:
        junk.load(load)
    junk.transpile(meta_context)
    return junk.evaluate(context, **context_kwargs)


def evaluate(
    path: str | pathlib.Path,
    context: dict[str, Any] | None = None,
    /,
    **context_kwargs: Any,
) -> str:
    if isinstance(path, str) and "\n" in path:
        meta_lines = path.splitlines()
    else:
        path = pathlib.Path(path)
        meta_lines = path.read_text().splitlines()
    junk = Junk(stack_level=1)
    junk.meta_lines = meta_lines
    return junk.evaluate(context, **context_kwargs)
