from __future__ import annotations

import contextlib
import pathlib
import re
import sys
from typing import Any, Callable, ClassVar, Iterable, Iterator, Protocol

from .collect import collect_definitions, collect_global_references
from .errors import EvaluationError, StopEvaluation
from .interpolate import interpolate as interpolate_
from .lines import Line, Lines
from .utils import and_, split_lines

type Transpiler = Callable[[Junk, str], None]
type MetaCallback = Callable[[Junk], None]
type MetaModule = str | pathlib.Path | dict[str, Any] | Iterable[MetaModule]


class MetaFunction(Protocol):
    def __call__(self, junk: Junk, *args: Any, **kwargs: Any) -> None: ...


META_REGEX = re.compile(
    r"""
    ^
    ([a-zA-Z_][a-zA-Z0-9_]*)
    (?:
        \(
        (.*?)
        \)
        |
        [ ]+
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
    add_sourcemap_by_default: ClassVar[bool] = True
    load_common_by_default: ClassVar[bool] = True
    interpolate_by_default: ClassVar[bool] = True

    StopEvaluation: ClassVar[type[StopEvaluation]] = StopEvaluation
    EvaluationError: ClassVar[type[EvaluationError]] = EvaluationError

    def __init__(
        self,
        template: str | pathlib.Path | None = None,
        *,
        sourcemap: bool | None = None,
        stack_level: int = 0,
    ) -> None:
        if sourcemap is None:
            sourcemap = self.add_sourcemap_by_default
        self.lines = Lines(template, stack_level=stack_level + 1)
        self.path = self.lines.path or self.lines.source_path
        self.code_indent = 0
        self.text_indent = 0
        self.output_indent = 0
        self.sourcemap = sourcemap
        self.code_lines: list[Any] = []
        self.output: list[str] = []
        self.transpilers: dict[str, Transpiler] = {
            self.code_prefix: code,
            self.meta_prefix: meta,
            "": text,
        }
        self.meta_namespace: dict[str, MetaFunction] = {
            "load": load,
        }
        self.meta_state: dict[str, Any] = {}
        self.meta_callbacks: list[MetaCallback] = []
        self.eval_namespace: dict[str, Any] = {
            "junk": self,
            "emit": self.emit,
            "indent": self.indent,
            "StopEvaluation": StopEvaluation,
        }
        self.interpolation: str = "{ }"
        self.inline: bool = False
        self._active_lines: list[Line] = []

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
    def line(self) -> Line:
        return self._active_lines[-1]

    def transpile(
        self,
        lines: Lines | None = None,
        load: MetaModule | None = None,
        load_common: bool | None = None,
    ) -> str:
        if lines is None:
            lines = self.lines
            if load_common is None:
                load_common = self.load_common_by_default
            if load_common:
                self.meta_namespace["load"](self, "common")
            if load is not None:
                self.meta_namespace["load"](self, load)
        for line in lines:
            with self._set_active_line(line):
                for prefix, transpile in sorted(
                    self.transpilers.items(),
                    key=lambda x: len(x[0]),
                    reverse=True,
                ):
                    if line.content.startswith(prefix):
                        content = line.content.removeprefix(prefix).strip()
                        transpile(self, content)
                        break
                else:
                    transpilers = (f"{transpile.__name__} ({prefix})" for prefix, transpile in self.transpilers.items())
                    raise ValueError(f"unable to transpile {line} (considered {and_(transpilers)})")
        for callback in self.meta_callbacks:
            callback(self)
        return self.to_string()

    def to_string(self, standalone: bool = False) -> str:
        code = "\n".join(map(str, self.code_lines))
        if standalone:
            code = self._generate_intro(code)
        return code

    def emit_code(self, code: str) -> None:
        for _, code_line in split_lines(code):
            self.code_lines.append(self.code_indent * " " + code_line + self._source_comment)

    @contextlib.contextmanager
    def increase_code_indent(self) -> Iterator[None]:
        self.code_indent += 4
        try:
            yield
        finally:
            self.code_indent -= 4

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
        self.emit_code(f'emit({indent}, {", ".join(args)})')

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

    def derive(self, path: str | pathlib.Path) -> Junk:
        junk = type(self)(path)
        if self._active_lines:
            junk.lines.set_source(self.line.source_path, self.line.source_line_number)
        else:
            junk.lines.set_source(self.lines.source_path, self.lines.source_line_number)
        junk.meta_state = self.meta_state
        return junk

    def evaluate(
        self,
        context: dict[str, Any] | None = None,
        /,
        **context_kwargs: Any,
    ) -> str:
        if context is None:
            context = {}
        context.update(context_kwargs)
        self.eval_namespace.update(context)
        code = self.to_string()
        try:
            exec(compile(code, self.source, "exec"), self.eval_namespace)
        except StopEvaluation:
            pass
        except Exception as error:
            raise EvaluationError(self.source, code, context, error)
        return "".join(self.output).rstrip()

    def emit(
        self,
        indent: int | None,
        *args: Any,
        inline: bool = False,
        newline: bool = True,
    ) -> None:
        text = "".join(map(str, args))
        if inline:
            self.output.append(text)
        else:
            end = "\n" if newline else ""
            if indent is None:
                indent = 0
            else:
                indent += self.output_indent
            self.output.append(f'{" " * indent}{text}{end}')

    @contextlib.contextmanager
    def indent(self, indent: int) -> Iterator[None]:
        self.output_indent += indent
        try:
            yield
        finally:
            self.output_indent -= indent

    @contextlib.contextmanager
    def redirect_output(self, output: list[str] | None = None) -> Iterator[list[str]]:
        if output is None:
            output = []
        prev_output, self.output = self.output, output
        try:
            yield output
        finally:
            self.output = prev_output

    @contextlib.contextmanager
    def _set_active_line(self, line: Line) -> Iterator[None]:
        self._active_lines.append(line)
        try:
            yield
        finally:
            self._active_lines.pop()

    @property
    def _source_comment(self) -> str:
        if self.sourcemap and self._active_lines:
            if self.line.path:
                return f"  # {self.line.path}:{self.line.number}"
            else:
                return f"  # {self.line.source_path}:{self.line.source_line_number}"
        return ""

    def _generate_intro(self, code: str) -> str:
        paths: set[pathlib.Path] = set()
        for name in collect_global_references(code):
            if name not in self.eval_namespace:
                continue
            func = self.eval_namespace[name]
            if func is self or getattr(self, f"{self.eval_function_prefix}{name}", None) == func:
                continue
            while hasattr(func, "__wrapped__"):
                func = func.__wrapped__
            paths.add(pathlib.Path(func.__code__.co_filename))
        defs, imps = collect_definitions(code, paths)
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
        return "\n".join(intro) + code


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
    output_indent = junk.line.indent
    if output_indent:
        junk.emit_code(f"with indent({output_indent}):")
        junk.code_indent += 4
    junk.emit_code(content)
    with junk.increase_code_indent():
        junk.transpile(junk.line.children.snap(0))
    if output_indent > 0:
        junk.code_indent -= 4


def meta(junk: Junk, content: str) -> None:
    # empty line or meta block
    if not content:
        # empty line
        if not junk.line.children:
            junk.emit_text(0, "")
            return
        # meta block
        code = junk.line.children.snap(0).to_string()
        exec(code, {"junk": junk}, junk.meta_namespace)
        return
    # meta function
    match = META_REGEX.match(content)
    if not match:
        raise ValueError(
            f"expected meta function on {junk.line} to be '<function> [<argument>]' or '<function>(<arguments>)', "
            f"but got {content!r}"
        )
    name, args, arg = match.groups()
    meta_functions = [name for name, value in junk.meta_namespace.items() if callable(value)]
    if name not in meta_functions:
        raise ValueError(
            f"unknown meta function {name!r} on {junk.line} " f"(available meta functions are {and_(meta_functions)})"
        )
    if args:
        meta_code = f"{name}(junk, {args})"
    elif arg:
        meta_code = f"{name}(junk, {repr(arg)})"
    else:
        meta_code = f"{name}(junk)"
    eval(meta_code, {"junk": junk}, junk.meta_namespace)


def text(junk: Junk, content: str) -> None:
    junk.emit_text(junk.line.indent, junk.line.content)
    junk.transpile(junk.line.children)


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
