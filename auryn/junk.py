from __future__ import annotations

import contextlib
import inspect
import pathlib
import re
import sys
from typing import Any, Callable, ClassVar, Iterator, Protocol

from .collect import collect_definitions, collect_global_references
from .interpolate import interpolate as interpolate_
from .lines import Line, Lines
from .utils import trim

type Transpiler = Callable[[Junk, str], None]
type MetaCallback = Callable[[Junk], None]


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
    builtins_directory: ClassVar[pathlib.Path] = pathlib.Path(__file__).parent / "builtins"
    load_common_by_default: ClassVar[bool] = True
    interpolate_by_default: ClassVar[bool] = True

    class StopEvaluation(Exception):
        pass

    def __init__(self, source: str, lines: Lines, path: str | pathlib.Path) -> None:
        self.source = source
        self.lines = lines
        self.path = pathlib.Path(path)
        self.code_indent = 0
        self.text_indent = 0
        self.code_lines: list[str] = []
        self.output: list[str] = []
        self.transpilers: dict[str, Transpiler] = {
            self.code_prefix: _transpile_code,
            self.meta_prefix: _transpile_meta,
            "": _transpile_text,
        }
        self.meta_namespace: dict[str, MetaFunction] = {
            "load": _load,
        }
        self.meta_state: dict[str, Any] = {}
        self.meta_callbacks: list[MetaCallback] = []
        self.eval_namespace: dict[str, Any] = {
            "emit": self.emit,
            "indent": self.indent,
            "StopEvaluation": self.StopEvaluation,
        }
        self.interpolation: str = "{ }"
        self.inline: bool = False
        self._active_lines: list[Line] = []

    def __repr__(self) -> str:
        if self.path:
            return f"<junk of {self.path} at {self.source}>"
        return f"<junk at {self.source}>"

    @classmethod
    def transpiler(cls, prefix: str = "") -> Callable[[Transpiler], Transpiler]:
        def decorator(transpiler: Transpiler) -> Transpiler:
            cls.transpilers[prefix] = transpiler
            return transpiler

        return decorator

    @classmethod
    def from_file(cls, path: str | pathlib.Path, *, stack_level: int = 0) -> Junk:
        source, source_path = cls._get_source(stack_level + 1)
        path = source_path.parent / path
        lines = Lines.from_file(path)
        return cls(source, lines, path)

    @classmethod
    def from_string(cls, string: str, *, stack_level: int = 0) -> Junk:
        source, path = cls._get_source(stack_level + 1)
        lines = Lines.from_string(source, string)
        return cls(source, lines, path)

    @classmethod
    def evaluate_standalone(
        cls,
        path: str | pathlib.Path,
        context: dict[str, Any] | None = None,
        /,
        *,
        stack_level: int = 0,
        **context_kwargs: Any,
    ) -> str:
        path = pathlib.Path(path)
        source, _ = cls._get_source(stack_level=stack_level + 1)
        junk = cls(source, Lines([]), path)
        junk.code_lines = path.read_text().splitlines()
        return junk.evaluate(context, junk=junk, **context_kwargs)

    @classmethod
    def _get_source(cls, stack_level: int) -> tuple[str, pathlib.Path]:
        frame = inspect.currentframe()
        for _ in range(stack_level + 1):
            frame = frame and frame.f_back
        if not frame:
            raise ValueError("unable to infer source")
        path = pathlib.Path(frame.f_code.co_filename)
        return f"{path.stem}:{frame.f_lineno}", path

    @property
    def line(self) -> Line:
        return self._active_lines[-1]

    def transpile(
        self,
        lines: Lines | None = None,
        load: str | pathlib.Path | dict[str, Any] | None = None,
        load_common: bool | None = None,
    ) -> str:
        if lines is None:
            lines = self.lines
            if load_common is None:
                load_common = self.load_common_by_default
            if load is not None:
                _load(self, load)
            if load_common:
                _load(self, "common")
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
                    raise ValueError(f"unable to transpile {line}")
        for callback in self.meta_callbacks:
            callback(self)
        return self.to_string()

    def to_string(self, standalone: bool = False) -> str:
        code = "\n".join(self.code_lines)
        if standalone:
            code = self._generate_intro(code)
        return code

    @contextlib.contextmanager
    def increase_code_indent(self) -> Iterator[None]:
        self.code_indent += 4
        try:
            yield
        finally:
            self.code_indent -= 4

    def emit_code(self, code: str) -> None:
        for code_line in trim(code):
            self.code_lines.append(self.code_indent * " " + code_line)

    def emit_text(
        self,
        indent: int,
        text: str,
        interpolate: bool | None = None,
        newline: bool = True,
    ) -> None:
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

    def emit(
        self,
        indent: int,
        *args: Any,
        inline: bool = False,
        newline: bool = True,
    ) -> None:
        if inline:
            self.output.append("".join(map(str, args)))
        else:
            end = "\n" if newline else ""
            indent += self.text_indent
            self.output.append(f'{" " * indent}{"".join(map(str, args))}{end}')

    @contextlib.contextmanager
    def indent(self, indent: int) -> Iterator[None]:
        self.text_indent += indent
        try:
            yield
        finally:
            self.text_indent -= indent

    def evaluate(
        self,
        context: dict[str, Any] | None = None,
        /,
        **context_kwargs: Any,
    ) -> str:
        if context is not None:
            self.eval_namespace.update(context)
        self.eval_namespace.update(context_kwargs)
        with contextlib.suppress(self.StopEvaluation):
            exec(self.to_string(), self.eval_namespace)
        return "".join(self.output).rstrip()

    def interpolate(self, string: str) -> str:
        args = []
        for snippet, is_code in interpolate_(string, self.interpolation):
            if is_code:
                args.append(f"{snippet}")
            else:
                args.append(repr(snippet))
        if not args:
            return "''"
        if len(args) == 1:
            return f"str({args[0]})"
        return f'concat({", ".join(args)})'

    @contextlib.contextmanager
    def redirect_output(self) -> Iterator[list[str]]:
        output: list[str] = []
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

    def _generate_intro(self, code: str) -> str:
        paths: set[pathlib.Path] = set()
        for name in collect_global_references(code):
            if name not in self.eval_namespace:
                continue
            func = self.eval_namespace[name]
            if getattr(self, name, None) == func:
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
        return "\n".join(intro) + "\n" + code


def _transpile_code(junk: Junk, content: str) -> None:
    text_indent = junk.line.indent
    if text_indent:
        junk.emit_code(f"with indent({text_indent}):")
        junk.code_indent += 4
    junk.emit_code(content)
    with junk.increase_code_indent():
        junk.transpile(junk.line.children.dedent(junk.line.indent + 4))
    if text_indent > 0:
        junk.code_indent -= 4


def _transpile_meta(junk: Junk, content: str) -> None:
    match = META_REGEX.match(content)
    if not match:
        raise ValueError(
            f"expected meta function on {junk.line} to be '<function> [<argument>]' or '<function>(<arguments>)',"
            f"but got {content!r}"
        )
    name, args, arg = match.groups()
    meta_functions = [name for name, value in junk.meta_namespace.items() if callable(value)]
    if name not in meta_functions:
        raise ValueError(
            f"unknown meta function {name!r} on {junk.line} "
            f"(available meta functions are {', '.join(meta_functions)})"
        )
    if args:
        meta_code = f"{name}(junk, {args})"
    elif arg:
        meta_code = f"{name}(junk, {repr(arg)})"
    else:
        meta_code = f"{name}(junk)"
    eval(meta_code, {"junk": junk}, junk.meta_namespace)


def _transpile_text(junk: Junk, content: str) -> None:
    junk.emit_text(junk.line.indent, junk.line.content)
    junk.transpile(junk.line.children)


def _load(junk: Junk, target: str | pathlib.Path | dict[str, Any]) -> None:
    if isinstance(target, dict):
        namespace = target
    else:
        path = junk.path.parent / target
        if not path.exists():
            path = junk.builtins_directory / f"{target}.py"
            if not path.exists():
                raise ValueError(f"could not load {target!r} " "(neither file nor builtin module found)")
        sys_path = sys.path.copy()
        sys_path.append(str(path.parent))
        try:
            text = path.read_text()
            code = compile(text, str(path), "exec")
            namespace = {}
            exec(code, namespace)
        finally:
            sys.path = sys_path
    for key, value in namespace.items():
        if key.startswith("meta_"):
            name = key.removeprefix("meta_")
            junk.meta_namespace[name] = value
        if key.startswith("eval_"):
            name = key.removeprefix("eval_")
            junk.eval_namespace[name] = value.__get__(junk)
    if "on_load" in namespace:
        namespace["on_load"](junk)
