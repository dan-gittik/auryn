import contextlib
import pathlib
from typing import Any

from auryn import Junk, Lines

UNDEFINED = object()


def meta_include(junk: Junk, path: str | pathlib.Path) -> None:
    included_junk = junk.from_file(junk.path.parent / path)
    with contextlib.suppress(IndexError):
        included_junk.lines.align(junk.line.indent)
    included_junk.meta_state = junk.meta_state
    included_junk.transpile()
    junk.emit_code(included_junk.to_string())


def meta_define(junk: Junk, name: str) -> None:
    definitions = junk.meta_state.setdefault("definitions", {})
    definitions[name] = junk.line.children


def meta_insert(junk: Junk, name: str) -> None:
    definitions = junk.meta_state.get("definitions", {})
    junk.transpile(definitions[name].align(junk.line.indent))


def meta_extend(junk: Junk, template: str | pathlib.Path) -> None:
    def replace_code(junk: Junk) -> None:
        junk.code_lines.clear()
        junk.code_indent = 0
        meta_include(junk, template)

    junk.meta_callbacks.append(replace_code)


def meta_interpolate(junk: Junk, delimiters: str) -> None:
    if junk.line.children:
        prev_delimiters, junk.interpolation = junk.interpolation, delimiters
        junk.transpile(junk.line.children.align(junk.line.indent))
        junk.interpolation = prev_delimiters
    else:
        junk.interpolation = delimiters


def meta_raw(junk: Junk) -> None:
    if junk.line.children:
        junk.emit_text(0, to_string(junk.line.children.align(junk.line.indent)))
    else:
        junk.transpilers = {"": emit_raw}


def to_string(lines: Lines) -> str:
    text = []
    for line in lines:
        text.append(" " * line.indent + line.content)
        text.append(to_string(line.children))
    return "\n".join(text)


def emit_raw(junk: Junk, content: str) -> None:
    junk.emit_code(f"emit({junk.line.indent}, {content!r})")
    junk.transpile(junk.line.children)


def meta_stop(junk: Junk) -> None:
    junk.emit_code(f"raise {junk.StopEvaluation.__name__}()")


def meta_param(junk: Junk, name: str, default: Any = UNDEFINED) -> None:
    parameters = junk.meta_state.setdefault("parameters", {})
    parameters[name] = default if default is not UNDEFINED else "<required>"
    if default is UNDEFINED:
        message = f"missing required parameter {name!r} if {junk.source}"
        junk.emit_code(
            f"""
            if {name!r} not in globals():
                raise ValueError({message!r})
    I       """
        )
    else:
        junk.emit_code(
            f"""
            try:
                {name}
            except NameError:
                {name} = {default!r}
            """
        )


def meta_inline(junk: Junk) -> None:
    prev_inline = junk.inline
    try:
        junk.emit_text(junk.line.indent, "", newline=False)
        junk.inline = True
        junk.transpile(junk.line.children)
        junk.inline = False
        junk.emit_text(0, "")
    finally:
        junk.inline = prev_inline


def meta_strip(junk: Junk, suffix: str) -> None:
    junk.emit_code(f"strip({suffix!r})")


def eval_strip(junk: Junk, suffix: str) -> None:
    junk.output[-1] = junk.output[-1].rstrip().strip(suffix)


def eval_camel_case(junk: Junk, name: str) -> str:
    return "".join(word.capitalize() for word in name.split("_"))


def eval_concat(*args: Any) -> str:
    return "".join(map(str, args))
