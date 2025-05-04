import contextlib
import pathlib
from typing import Any, Iterator

from auryn import Junk, Lines
from auryn.utils import and_, is_path

UNDEFINED = object()
DEFINITIONS = "definitions"
PARAMETERS = "parameters"
BOOKMARKS = "bookmarks"


class Bookmark:

    def __init__(self, indent: int) -> None:
        self.indent = indent
        self.lines: list[Any] = []

    def __str__(self) -> str:
        return "".join(map(str, self.lines))


def meta_eval(junk: Junk, code: str) -> None:
    code = eval(f"f{code!r}", junk.meta_namespace)
    junk.emit_code(code)
    junk.proceed()
    with junk.increase_code_indent():
        junk.proceed(junk.line.children.snap())


def meta_emit(junk: Junk, text: str) -> None:
    text = eval(f"f{text!r}", junk.meta_namespace)
    junk.emit_text(junk.line.indent, text)
    junk.proceed()


def meta_include(
    junk: Junk,
    template: str | pathlib.Path,
    load: str | pathlib.Path | dict[str, Any] | None = None,
    render: bool = True,
    interpolate: bool = True,
    with_namespace: bool = False,
) -> None:
    if not render:
        if is_path(template, junk.path.parent):
            path = junk.path.parent / template
            junk.emit_text_block(junk.line.indent, path.read_text(), interpolate=interpolate)
        else:
            junk.emit_text_block(junk.line.indent, str(template), interpolate=interpolate)
        return
    included_junk = junk.derive(template, with_namespace=with_namespace)
    if load:
        included_junk.load(load)
    if junk.has_line:
        included_junk.lines.snap(junk.line.indent)
    included_junk.transpile(junk.meta_context)
    junk.emit_code(included_junk.to_string(), add_source_comment=False)


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
        junk.proceed(junk.line.children.snap())
        return
    junk.proceed(definitions[name].snap(junk.line.indent))


def meta_extend(junk: Junk, template: str | pathlib.Path) -> None:
    if junk.line.children:
        with junk.patch(meta_lines=junk.meta_lines, code_indent=junk.code_indent):
            junk.proceed(junk.line.children.snap())
        meta_include(junk, template)
        return

    def replace_code(junk: Junk) -> None:
        junk.meta_lines.clear()
        junk.code_indent = 0
        meta_include(junk, template)

    junk.meta_callbacks.append(replace_code)


def meta_interpolate(junk: Junk, interpolation: str) -> None:
    if junk.line.children:
        with junk.patch(interpolation=interpolation):
            junk.proceed(junk.line.children.snap())
    else:
        junk.interpolation = interpolation


def meta_raw(junk: Junk) -> None:
    if junk.line.children:
        text = junk.line.children.snap().to_string()
        junk.emit_text_block(0, text, interpolate=False)
    else:
        junk.transpilers.clear()
        junk.transpilers[""] = emit_raw


def emit_raw(junk: Junk, content: str) -> None:
    junk.emit_code(f"{junk.EMIT}({junk.line.indent}, {content!r})")
    junk.proceed()


def meta_stop(junk: Junk) -> None:
    junk.emit_code(f"raise {junk.STOP_EVALUATION}()")


def meta_param(junk: Junk, name: str, default: Any = UNDEFINED) -> None:
    parameters: dict[str, Any] = junk.meta_state.setdefault(PARAMETERS, {})
    parameters[name] = default if default is not UNDEFINED else "<required>"
    if default is UNDEFINED:
        message = f"missing required parameter {name!r} in {junk.source}"
        junk.emit_code(
            f"""
            if {name!r} not in globals():
                raise ValueError({message!r})
            """
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
    junk.emit_text(junk.line.indent, "", newline=False)
    with junk.patch(inline=True):
        junk.proceed()
    with junk.patch(inline=False):
        junk.emit_text(None, "")


def meta_assign(junk: Junk, name: str) -> None:
    junk.emit_code("with assign() as _:")
    with junk.increase_code_indent():
        junk.proceed(junk.line.children.snap())
    junk.emit_code(f"{name} = ''.join(_).strip()")


@contextlib.contextmanager
def eval_assign(junk: Junk) -> Iterator[list[str]]:
    eval_lines: list[str] = []
    with junk.patch(eval_lines=eval_lines):
        yield eval_lines


def meta_bookmark(junk: Junk, name: str) -> None:
    junk.emit_code(f"bookmark({junk.line.indent}, {junk.interpolate(name)})")


def eval_bookmark(junk: Junk, indent: int, name: str) -> None:
    bookmark = Bookmark(indent)
    bookmarks: dict[str, Bookmark] = junk.meta_state.setdefault(BOOKMARKS, {})
    bookmarks[name] = bookmark
    junk.eval_lines.append(bookmark)


def meta_append(junk: Junk, name: str) -> None:
    junk.emit_code(f"with append({junk.interpolate(name)}, {str(junk.line)!r}):")
    with junk.increase_code_indent():
        junk.proceed(junk.line.children.snap(0))


@contextlib.contextmanager
def eval_append(junk: Junk, name: str, line: str) -> Iterator[None]:
    bookmarks: dict[str, Bookmark] = junk.meta_state.get(BOOKMARKS, {})
    if name not in bookmarks:
        raise ValueError(
            f"missing bookmark {name!r} referenced on {line} " f"(available bookmarks are {and_(bookmarks)})"
        )
    bookmark = bookmarks[name]
    with junk.patch(eval_lines=bookmark.lines, eval_indent=bookmark.indent):
        yield


def meta_strip(junk: Junk, suffix: str) -> None:
    junk.emit_code(f"strip({suffix!r})")


def eval_strip(junk: Junk, suffix: str) -> None:
    junk.eval_lines[-1] = junk.eval_lines[-1].rstrip().strip(suffix)


def eval_camel_case(junk: Junk, name: str) -> str:
    return "".join(word.capitalize() for word in name.split("_"))


def eval_concat(junk: Junk, *args: Any) -> str:
    return "".join(map(str, args))
