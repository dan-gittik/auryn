import contextlib
import pathlib
from typing import Any, Iterator

from auryn import Junk, Lines
from auryn.utils import and_

UNDEFINED = object()
DEFINITIONS = "definitions"
PARAMETERS = "parameters"
BOOKMARKS = "bookmarks"


class Bookmark:

    def __init__(self, code_indent: int, text_indent: int) -> None:
        self.code_indent = code_indent
        self.text_indent = text_indent
        self.code_lines: list[str] = []
    
    def __str__(self) -> str:
        return "\n".join(self.code_lines)
    
    @contextlib.contextmanager
    def inject(self, junk: Junk) -> Iterator[None]:
        code_indent, text_indent, code_lines = junk.code_indent, junk.text_indent, junk.code_lines
        junk.code_indent, junk.text_indent, junk.code_lines = self.code_indent, self.text_indent, self.code_lines
        try:
            yield
        finally:
            junk.code_indent, junk.text_indent, junk.code_lines = code_indent, text_indent, code_lines


def meta_include(junk: Junk, path: str | pathlib.Path) -> None:
    included_junk = junk.derive(junk.path.parent / path)
    try:
        included_junk.lines.snap(junk.line.indent)
    except IndexError:
        pass
    included_junk.transpile()
    junk.emit_code(included_junk.to_string())


def meta_define(junk: Junk, name: str) -> None:
    definitions: dict[str, Lines] = junk.meta_state.setdefault(DEFINITIONS, {})
    definitions[name] = junk.line.children


def meta_insert(junk: Junk, name: str, required: bool = False) -> None:
    definitions: dict[str, Lines] = junk.meta_state.get(DEFINITIONS, {})
    if name not in definitions:
        if required:
            raise ValueError(
                f"missing required definition {name!r} on {junk.line} "
                f"(available definitions are {and_(definitions)})"
            )
        junk.transpile(junk.line.children.snap())
        return
    junk.transpile(definitions[name].snap(junk.line.indent))


def meta_extend(junk: Junk, template: str | pathlib.Path) -> None:
    if junk.line.children:
        code_lines, code_indent = junk.code_lines, junk.code_indent
        junk.transpile(junk.line.children.snap())
        junk.code_lines, junk.code_indent = code_lines, code_indent
        meta_include(junk, template)
        return

    def replace_code(junk: Junk) -> None:
        junk.code_lines.clear()
        junk.code_indent = 0
        meta_include(junk, template)

    junk.meta_callbacks.append(replace_code)


def meta_interpolate(junk: Junk, delimiters: str) -> None:
    if junk.line.children:
        prev_delimiters, junk.interpolation = junk.interpolation, delimiters
        junk.transpile(junk.line.children.snap())
        junk.interpolation = prev_delimiters
    else:
        junk.interpolation = delimiters


def meta_raw(junk: Junk) -> None:
    if junk.line.children:
        text = junk.line.children.snap().to_string()
        junk.emit_text(0, text, interpolate=False)
    else:
        junk.transpilers.clear()
        junk.transpilers[""] = emit_raw


def emit_raw(junk: Junk, content: str) -> None:
    junk.emit_code(f"emit({junk.line.indent}, {content!r})")
    junk.transpile(junk.line.children)


def meta_stop(junk: Junk) -> None:
    junk.emit_code(f"raise StopEvaluation()")


def meta_param(junk: Junk, name: str, default: Any = UNDEFINED) -> None:
    parameters: dict[str, Any] = junk.meta_state.setdefault(PARAMETERS, {})
    parameters[name] = default if default is not UNDEFINED else "<required>"
    if default is UNDEFINED:
        message = f"missing required parameter {name!r} in {junk.source}"
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
        junk.emit_text(None, "")
    finally:
        junk.inline = prev_inline


def meta_assign(junk: Junk, name: str) -> None:
    junk.emit_code(f"with assign() as _:")
    with junk.increase_code_indent():
        junk.transpile(junk.line.children.snap(junk.line.indent))
    junk.emit_code(f"{name} = ''.join(_).strip()")


@contextlib.contextmanager
def eval_assign(junk: Junk) -> Iterator[list[str]]:
    with junk.redirect_output() as output:
        yield output


def meta_bookmark(junk: Junk, name: str) -> None:
    bookmarks: dict[str, Bookmark] = junk.meta_state.setdefault(BOOKMARKS, {})
    bookmarks[name] = bookmark = Bookmark(junk.code_indent, junk.line.indent)
    junk.code_lines.append(bookmark)


def meta_append(junk: Junk, name: str) -> None:
    bookmarks: dict[str, Bookmark] = junk.meta_state.get(BOOKMARKS, {})
    if name not in bookmarks:
        raise ValueError(
            f"missing required bookmark {name!r} on {junk.line} "
            f"(available bookmarks are {and_(bookmarks)})"
        )
    with bookmarks[name].inject(junk):
        junk.transpile(junk.line.children.snap(0))


def meta_strip(junk: Junk, suffix: str) -> None:
    junk.emit_code(f"strip({suffix!r})")


def eval_strip(junk: Junk, suffix: str) -> None:
    junk.output[-1] = junk.output[-1].rstrip().strip(suffix)


def eval_camel_case(junk: Junk, name: str) -> str:
    return "".join(word.capitalize() for word in name.split("_"))


def eval_concat(*args: Any) -> str:
    return "".join(map(str, args))