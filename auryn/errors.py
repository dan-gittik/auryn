from __future__ import annotations

import ast
import pathlib
import shutil
import textwrap
from typing import Any, ClassVar, Iterator

from .utils import crop_lines

ROOT = str(pathlib.Path(__file__).parent)


class StopExecution(Exception):
    pass


class Error(Exception):

    message: ClassVar[str] = "Error on {gx}: {error}."
    width: ClassVar[int] = shutil.get_terminal_size(fallback=(120, 30)).columns
    slice_size: ClassVar[int] = 10
    reset: ClassVar[str] = "\x1b[0m"
    styles: ClassVar[dict[str, str]] = {
        "error": "\x1b[1;31m",  # bold red
        "unknown": "\x1b[1;47;30m",  # bold white on black
        "title": "\x1b[1;4m",  # bold underline
        "info": "\x1b[1;34m",  # bold blue
        "main": "\x1b[1;33m",  # bold yellow
        "dim": "\x1b[2m",  # dim
        "dim_info": "\x1b[2;34m",  # dim blue
        "dim_main": "\x1b[2;33m",  # dim yellow
    }

    def __init__(self, gx: GX, error: Exception) -> None:
        self.gx = gx
        self.error = error

    def __str__(self) -> str:
        return self.message.format(gx=self.gx, error=str(self.error).strip("."))

    def report(self) -> str:
        self._indent = 0
        self._output: list[str] = []
        self._add_text(f"{self}", style="error")
        self._report()
        return "".join(self._output)

    def _report(self) -> None:
        raise NotImplementedError()

    def _add_text(self, text: str, style: str | None = None, dim: bool = False, newline: bool = True) -> None:
        if not text:
            return
        if dim:
            style = f"dim_{style}" if style else "dim"
        if style and style in self.styles:
            self._output.append(self.styles[style])
        for line in text.splitlines():
            line = "\n".join(self._wrap(line))
            self._output.append(line)
            if newline:
                self._output.append("\n")
        if style:
            self._output.append(self.reset)

    def _add_title(self, title: str) -> None:
        self._output.append(f"\n{self.styles['title']}{title.ljust(self.width)}{self.reset}\n")

    def _add_context(self, context: dict[str, Any]) -> None:
        self._add_title("CONTEXT")
        for key, value in context.items():
            if key == "__builtins__":
                continue
            dim = False
            # Dim and format GX.
            if isinstance(value, GX):
                dim = True
                value = str(value)
            # Peel wrappers from functions, format them, and dim internal ones.
            elif hasattr(value, "__name__") and hasattr(value, "__code__"):
                while hasattr(value, "__wrapped__"):
                    value = value.__wrapped__
                filename = value.__code__.co_filename
                line_number = value.__code__.co_firstlineno
                dim = filename.startswith(ROOT)
                value = f"{value.__name__} at {self._location(filename, line_number)}"
            # Format classes, and dim internal ones.
            elif isinstance(value, type):
                dim = value.__module__.startswith(__package__)
                value = f"{value.__module__}.{value.__name__}"
            else:
                value = repr(value)
            indent = len(key) + 2
            value = f"\n{' ' * indent}".join(self._wrap(value, indent))
            self._add_text(f"{key}:", style="info", dim=dim, newline=False)
            self._add_text(f" {value}", dim=dim)

    def _add_template(self, gx: GX, line_number: int) -> None:
        self._add_title("TEMPLATE")
        location = self._location(str(gx.template.path or gx.origin.path), line_number)
        self._add_text(f"in {location}:", style="info")
        while True:
            lines = gx.template.text.splitlines()
            # String templates are indexed from 1 (line 0 is just """), but file templates are indexed from 0.
            if gx.template.path:
                line_number -= 1
            self._indent += 4
            try:
                self._add_slice(lines, line_number)
            finally:
                self._indent -= 4
            if not gx.origin.gx:
                break
            location = self._location(str(gx.origin.path), gx.origin.line_number)
            self._add_text(f"derived from {location}:", style="info")
            gx, line_number = gx.origin.gx, gx.origin.line_number
            # If the source GX is a string, the line number needs to be offset by its source line number.
            if not gx.template.path:
                line_number -= gx.origin.line_number

    def _add_traceback(self) -> None:
        self._add_title("TRACEBACK")
        locations: list[tuple[str, int]] = []
        # Collect locations before and after we were raised.
        for traceback in [self.__traceback__, self.error.__traceback__]:
            while traceback:
                filename = traceback.tb_frame.f_code.co_filename
                line_number = traceback.tb_lineno
                locations.append((filename, line_number))
                traceback = traceback.tb_next
        for filename, line_number in locations:
            # Dim internal locations.
            dim = filename.startswith(ROOT)
            self._add_text(f"in {self._location(filename, line_number)}:", style="info", dim=dim)
            self._add_code(filename, line_number, dim=dim)
        self._add_text(f"{self.error.__class__.__name__}: {self.error}", style="error")

    def _add_unknown(self) -> None:
        self._add_text("???", style="unknown")

    def _add_code(self, filename: str, line_number: int, dim: bool = False) -> None:
        self._indent += 4
        try:
            code = pathlib.Path(filename).read_text()
            # Show the function definition in which this line is located.
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if not node.end_lineno or not node.lineno <= line_number <= node.end_lineno:
                        continue
                    block = ast.get_source_segment(code, node, padded=True) or ""
                    for n, line in crop_lines(block):
                        if n == line_number - node.lineno:
                            self._add_text(line, style="main", dim=dim)
                        else:
                            self._add_text(line, dim=dim)
                    break
            # Otherwise, show a slice around that line.
            else:
                lines = code.splitlines()
                # Line numbers start from 1, but a lines array is indexed from 0.
                line_number -= 1
                if line_number < len(lines):
                    self._add_slice(lines, line_number, dim=dim)
                else:
                    self._add_unknown()
        except Exception:
            self._add_unknown()
        finally:
            self._indent -= 4

    def _add_slice(self, lines: list[str], line_number: int, dim: bool = False) -> None:
        size = self.slice_size // 2
        self._add_text("\n".join(lines[line_number - size : line_number]).lstrip(), dim=dim)
        self._add_text(lines[line_number], style="main", dim=dim)
        self._add_text("\n".join(lines[line_number + 1 : line_number + size]).rstrip(), dim=dim)

    def _location(self, filename: str, line_number: int) -> str:
        # Dynamic code during generation is saved in temporary files with the name:
        # <temporary-directory>/<temporary-prefix>.<filename>-<line-number>.g.py
        if filename.endswith(GX.generation_file_suffix):
            location = self._parse_temp_location(GX.generation_file_suffix, filename)
            return f"generation of GX {location}"
        # Dynamic code during execution is saved in temporary files with the name:
        # <temporary-directory>/<temporary-prefix>.<filename>-<line-number>.x.py
        if filename.endswith(GX.execution_file_suffix):
            location = self._parse_temp_location(GX.execution_file_suffix, filename)
            return f"execution of GX {location}"
        # Otherwise, make the path relative if possible, and use the full path if not.
        path, cwd = pathlib.Path(filename), pathlib.Path.cwd()
        if path.is_relative_to(cwd):
            return f"{path.relative_to(cwd)}:{line_number}"
        return f"{filename}:{line_number}"

    def _wrap(self, text: str, width_offset: int = 0) -> Iterator[str]:
        for line in text.splitlines():
            for subline in textwrap.wrap(line, width=self.width - self._indent - width_offset):
                yield " " * self._indent + subline

    def _parse_temp_location(self, suffix: str, filename: str) -> str:
        name = filename.removesuffix(suffix).rsplit(".", 1)[1]
        if "-" in name:
            return f"at {name.replace('-', ':')}"
        return f"of {name}"


class GenerationError(Error):

    message: ClassVar[str] = "Failed to generate {gx}: {error}."

    def _report(self) -> None:
        self._add_context({**self.gx.g_globals, **self.gx.g_locals})
        self._add_template(self.gx, self.gx.line.number)
        self._add_traceback()


class ExecutionError(Error):

    message: ClassVar[str] = "Failed to execute {gx}: {error}."

    def _report(self) -> None:
        self._add_context(self.gx.x_globals)
        junk, line_number = self._find_source()
        if junk:
            self._add_template(junk, line_number)
        self._add_traceback()

    def _find_source(self) -> tuple[GX, int]:
        first_line_number = self.gx.code.lines[0].template_line_number
        # Dynamic code during execution is saved in temporary files with the name:
        # <temporary-directory>/<temporary-prefix>.<filename>-<line-number>.x.py
        traceback = self.error.__traceback__
        while traceback:
            if traceback.tb_frame.f_code.co_filename.endswith(GX.execution_file_suffix):
                line_number = traceback.tb_frame.f_lineno - first_line_number
                break
            traceback = traceback.tb_next
        line = self.gx.code.lines[line_number]
        return line.gx, line.template_line_number


from .gx import GX
