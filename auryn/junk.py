from __future__ import annotations

import contextlib
import pathlib
import re
import sys
from typing import Any, Callable, ClassVar, Iterable, Iterator

from .collect import collect_definitions, collect_global_references
from .interpolate import interpolate as interpolate_, parse_arguments
from .lines import Line, Lines
from .utils import and_, is_path, split_lines

type Transpiler = Callable[[Junk, str], None]
type MetaCallback = Callable[[Junk], None]
type MetaModule = str | pathlib.Path | dict[str, Any] | Iterable[MetaModule]


META_REGEX = re.compile(
    r"""
    ^
    ([a-zA-Z_][a-zA-Z0-9_]*)
    (?:
        (:{0,2})
        \s+
        (.*)
    )?
    $
    """,
    flags=re.VERBOSE,
)


class Junk:

    code_prefix: ClassVar[str] = "!"
    meta_prefix: ClassVar[str] = "%"
    comment_prefix: ClassVar[str] = "#"
    meta_function_prefix: ClassVar[str] = "meta_"
    eval_function_prefix: ClassVar[str] = "eval_"
    on_load_function_name: ClassVar[str] = "on_load"
    builtins_directories: ClassVar[list[pathlib.Path]] = [pathlib.Path(__file__).parent / "builtins"]
    common_module_name: ClassVar[str] = "common"

    add_source_comments_by_default: ClassVar[bool] = True
    load_common_by_default: ClassVar[bool] = True
    transpile_standalone_by_default: ClassVar[bool] = False
    default_interpolation: ClassVar[str] = "{ }"
    interpolate_by_default: ClassVar[bool] = True

    EMIT: ClassVar[str] = "emit"
    INDENT: ClassVar[str] = "indent"
    STOP_EVALUATION: ClassVar[str] = "StopEvaluation"

    def __init__(
        self,
        template: str | pathlib.Path | None = None,
        *,
        load_common: bool | None = None,
        add_source_comments: bool | None = None,
        stack_level: int = 0,
    ) -> None:
        if load_common is None:
            load_common = self.load_common_by_default
        if add_source_comments is None:
            add_source_comments = self.add_source_comments_by_default
        self.lines = Lines(template, stack_level=stack_level + 1)
        self.path = self.lines.path or self.lines.source_path
        self.add_source_comments = add_source_comments
        self.code_indent = 0
        self.text_indent = 0
        self.eval_indent = 0
        self.meta_lines: list[Any] = []
        self.eval_lines: list[Any] = []
        self.transpilers: dict[str, Transpiler] = {
            self.code_prefix: code,
            self.meta_prefix: meta,
            "": text,
        }
        self.meta_context: dict[str, Any] = {}
        self.meta_namespace: dict[str, Any] = {
            "junk": self,
            "load": load,
        }
        self.meta_state: dict[str, Any] = {}
        self.meta_callbacks: list[MetaCallback] = []
        self.eval_context: dict[str, Any] = {}
        self.eval_namespace: dict[str, Any] = {
            "junk": self,
            self.EMIT: self.emit,
            self.INDENT: self.indent,
            self.STOP_EVALUATION: StopEvaluation,
        }
        self.eval_state: dict[str, Any] = {}
        self.interpolation: str = self.default_interpolation
        self.inline: bool = False
        self._active_lines: list[Line] = []
        if load_common:
            self.load(self.common_module_name)

    def __str__(self) -> str:
        if self.path != self.lines.source_path:
            return f"junk of {self.path} at {self.source}"
        return f"junk at {self.source}"

    def __repr__(self) -> str:
        return f"<{self}>"

    @property
    def source_path(self) -> pathlib.Path:
        return self.lines.source_path

    @property
    def source_line_number(self) -> int:
        return self.lines.source_line_number

    @property
    def source(self) -> str:
        return self.lines.source
    
    @property
    def has_line(self) -> bool:
        return bool(self._active_lines)

    @property
    def line(self) -> Line:
        return self._active_lines[-1]
    
    def load(self, target: MetaModule) -> None:
        load(self, target)

    def transpile(self, context: dict[str, Any] | None = None, /, **context_kwargs: Any) -> str:
        if context:
            self.meta_context.update(context)
        if context_kwargs:
            self.meta_context.update(context_kwargs)
        self.meta_namespace.update(self.meta_context)
        self.proceed(self.lines)
        for callback in self.meta_callbacks:
            callback(self)
        return self.to_string()

    def to_string(self, standalone: bool | None = None) -> str:
        if standalone is None:
            standalone = self.transpile_standalone_by_default
        meta = "\n".join(map(str, self.meta_lines))
        if standalone:
            meta = self._generate_intro(meta)
        return meta

    def evaluate(self, context: dict[str, Any] | None = None, /, **context_kwargs: Any) -> str:
        if context:
            self.eval_context.update(context)
        if context_kwargs:
            self.eval_context.update(context_kwargs)
        self.eval_namespace.update(self.eval_context)
        meta = self.to_string()
        try:
            exec(compile(meta, self.source, "exec"), self.eval_namespace)
        except StopEvaluation:
            pass
        except Exception as error:
            raise EvaluationError(self, error) from None
        return "".join(map(str, self.eval_lines)).rstrip()
    
    def proceed(self, lines: Lines | None = None) -> None:
        if lines is None:
            lines = self.line.children
        for line in lines:
            with self._set_active_line(line):
                for prefix, transpile in sorted(
                    self.transpilers.items(),
                    key=lambda x: len(x[0]),
                    reverse=True,
                ):
                    if line.content.startswith(prefix):
                        content = line.content.removeprefix(prefix).lstrip()
                        transpile(self, content)
                        break
                else:
                    transpilers = (f"{transpile.__name__} ({prefix})" for prefix, transpile in self.transpilers.items())
                    raise ValueError(f"unable to transpile {line} (considered {and_(transpilers)})")

    @contextlib.contextmanager
    def patch(self, **state: Any) -> Iterator[None]:
        prev_state: dict[str, Any] = {}
        for key, value in state.items():
            prev_state[key] = getattr(self, key)
            setattr(self, key, value)
        try:
            yield
        finally:
            for key, value in prev_state.items():
                setattr(self, key, value)

    def emit_code(self, code: str, add_source_comment: bool | None = None) -> None:
        if add_source_comment is None:
            add_source_comment = self.add_source_comments
        for _, code_line in split_lines(code):
            code_line = self.code_indent * " " + code_line
            if add_source_comment:
                code_line += self._source_comment
            self.meta_lines.append(code_line)

    @contextlib.contextmanager
    def increase_code_indent(self) -> Iterator[None]:
        with self.patch(code_indent=self.code_indent + 4):
            yield

    def emit_text(
        self,
        indent: int | None,
        text: str,
        interpolate: bool | None = None,
        newline: bool = True,
    ) -> None:
        if indent is not None:
            indent += self.text_indent
        if interpolate is None:
            interpolate = self.interpolate_by_default
        if not interpolate:
            args = [repr(text)]
        else:
            args = []
            for snippet, is_code in interpolate_(text, self.interpolation):
                if is_code:
                    args.append(f"{snippet}")
                else:
                    args.append(repr(snippet))
        if not newline:
            args.append("newline=False")
        if self.inline:
            args.append("inline=True")
        self.emit_code(f'{self.EMIT}({indent}, {", ".join(args)})')
    
    def emit_text_block(self, indent: int, text: str, interpolate: bool | None = None) -> None:
        if interpolate is None:
            interpolate = self.interpolate_by_default
        for _, line in split_lines(text):
            self.emit_text(indent, line, interpolate=interpolate)

    def interpolate(self, string: str) -> str:
        args = []
        for snippet, is_code in interpolate_(string, self.interpolation):
            if is_code:
                args.append(f"{snippet}")
            else:
                args.append(repr(snippet))
        if len(args) == 1:
            return f"str({args[0]})"
        return f'concat({", ".join(args)})'

    def derive(self, template: str | pathlib.Path, with_namespace: bool = False) -> Junk:
        if is_path(template, self.path.parent):
            template = self.path.parent / template
        junk = type(self)(template)
        if self.has_line:
            junk.lines.set_source(self.line.source_path, self.line.source_line_number)
        else:
            junk.lines.set_source(self.lines.source_path, self.lines.source_line_number)
        junk.add_source_comments = self.add_source_comments
        junk.meta_state = self.meta_state
        if with_namespace:
            junk.meta_namespace = self.meta_namespace.copy()
            junk.meta_namespace["junk"] = junk
        return junk

    def emit(
        self,
        indent: int | None,
        *args: Any,
        inline: bool = False,
        newline: bool = True,
    ) -> None:
        text = "".join(map(str, args))
        if inline:
            self.eval_lines.append(text)
        else:
            end = "\n" if newline else ""
            if indent is None:
                indent = 0
            else:
                indent += self.eval_indent
            self.eval_lines.append(f'{" " * indent}{text}{end}')

    @contextlib.contextmanager
    def indent(self, indent: int) -> Iterator[None]:
        self.eval_indent += indent
        try:
            yield
        finally:
            self.eval_indent -= indent

    @contextlib.contextmanager
    def _set_active_line(self, line: Line) -> Iterator[None]:
        self._active_lines.append(line)
        try:
            yield
        finally:
            self._active_lines.pop()

    @property
    def _source_comment(self) -> str:
        if self.line.path:
            return f"  # {self.line.path}:{self.line.number}"
        return f"  # {self.line.source_path}:{self.line.source_line_number}"

    def _generate_intro(self, meta: str) -> str:
        paths: set[pathlib.Path] = set()
        for name in collect_global_references(meta):
            if name not in self.eval_namespace:
                continue
            func = self.eval_namespace[name]
            if func is self or getattr(self, f"{self.eval_function_prefix}{name}", None) == func:
                continue
            while hasattr(func, "__wrapped__"):
                func = func.__wrapped__
            paths.add(pathlib.Path(func.__code__.co_filename))
        defs, imps = collect_definitions(meta, paths)
        intro: list[str] = []
        for name, (what, whence) in imps.items():
            if whence is None:
                if name == what:
                    intro.append(f"import {name}")
                else:
                    intro.append(f"import {what} as {name}")
            elif name == what:
                intro.append(f"from {whence} import {name}")
            else:
                intro.append(f"from {whence} import {what} as {name}")
        if intro:
            intro.append("")
        for name, def_ in defs.items():
            intro.append(f"{def_}\n")
        if intro:
            intro.append("")
        return "\n".join(intro) + meta


def code(junk: Junk, content: str) -> None:
    # comment line or block
    if content.startswith(junk.comment_prefix):
        return
    # code block
    if not content:
        code = junk.line.children.to_string()
        junk.emit_code(code)
        return
    # code line
    eval_indent = junk.line.indent
    if eval_indent:
        junk.emit_code(f"with {junk.INDENT}({eval_indent}):")
        junk.code_indent += 4
    junk.emit_code(content)
    with junk.increase_code_indent():
        junk.line.children.snap(0)
        junk.proceed()
    if eval_indent > 0:
        junk.code_indent -= 4


def meta(junk: Junk, content: str) -> None:
    # empty line
    if not content:
        junk.emit_text(0, "")
        return
    # meta code
    if content.startswith(junk.code_prefix):
        meta_code = content.removeprefix(junk.code_prefix).lstrip()
        # meta code block
        if not meta_code:
            meta_code = junk.line.children.snap(0).to_string()
            exec(meta_code, junk.meta_namespace)
            return
        # meta code line
        if not junk.line.children:
            exec(meta_code, junk.meta_namespace)
            return
        # meta code line with children
        proceed = lambda: junk.proceed(junk.line.children.snap())
        meta_code += "\n    _()"
        exec(meta_code, {"_": proceed}, junk.meta_namespace)
        return
    # meta function
    match = META_REGEX.match(content)
    if not match:
        raise ValueError(
            f"expected meta function on {junk.line} to be '<function> [argument]', '<function>: <arguments>' or "
            f"'<function>:: <invocation>', but got {content!r}"
        )
    name, call_type, arg = match.groups()
    meta_functions = [name for name, value in junk.meta_namespace.items() if callable(value)]
    if name not in meta_functions:
        raise ValueError(
            f"unknown meta function {name!r} on {junk.line} " f"(available meta functions are {and_(meta_functions)})"
        )
    if not arg:
        meta_code = f"{name}(junk)"
    elif not call_type:
        meta_code = f"{name}(junk, {repr(arg)})"
    elif call_type == ":":
        args = ", ".join(parse_arguments(arg))
        meta_code = f"{name}(junk, {args})"
    else:
        meta_code = f"{name}(junk, {arg})"
    eval(meta_code, junk.meta_namespace)


def text(junk: Junk, content: str) -> None:
    if content:
        junk.emit_text(junk.line.indent, content)
    junk.proceed()


def load(junk: Junk, target: MetaModule) -> None:
    if isinstance(target, dict):
        namespace = target
    elif isinstance(target, str | pathlib.Path):
        path = junk.path.parent / target
        if not path.exists():
            for builtin_directory in junk.builtins_directories:
                builtin_path = builtin_directory / f"{target}.py"
                if builtin_path.exists():
                    path = builtin_path
                    break
            else:
                builtin_modules = []
                for builtin_directory in junk.builtins_directories:
                    for builtin_module in builtin_directory.glob("*.py"):
                        builtin_modules.append(builtin_module.stem)
                raise ValueError(
                    f"could not load {target!r} "
                    f"({path} does not exist, and available builtins are {and_(sorted(builtin_modules))})"
                )
        sys_path = sys.path.copy()
        sys.path.append(str(path.parent))
        try:
            text = path.read_text()
            code = compile(text, str(path), "exec")
            namespace = {}
            exec(code, namespace)
        finally:
            sys.path = sys_path
    else:
        for meta_module in target:
            load(junk, meta_module)
        return
    for key, value in namespace.items():
        if key.startswith(junk.meta_function_prefix):
            name = key.removeprefix(junk.meta_function_prefix)
            junk.meta_namespace[name] = value
        if key.startswith(junk.eval_function_prefix):
            name = key.removeprefix(junk.eval_function_prefix)
            junk.eval_namespace[name] = value.__get__(junk)
    if junk.on_load_function_name in namespace:
        namespace[junk.on_load_function_name](junk)


from .errors import EvaluationError, StopEvaluation