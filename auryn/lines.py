from __future__ import annotations

import inspect
import pathlib
from typing import Iterator

from .utils import is_path, split_line, split_lines


class Lines:

    def __init__(
        self,
        template: str | pathlib.Path | None = None,
        *,
        parent: Line | None = None,
        stack_level: int = 0,
    ) -> None:
        self.parent = parent
        if not self.parent:
            self._path = None
            self._source_path, self._source_line_number = self._get_source(stack_level + 1)
        self.lines: list[Line] = []
        if template:
            if is_path(template):
                self._path = pathlib.Path(template)
                text = self._path.read_text()
                offset = 0
            else:
                text = template
                offset = 1
            stack: list[Line] = []
            for number, line_text in split_lines(text):
                indent, content = split_line(line_text)
                line = Line(number - offset, indent, content)
                while stack and stack[-1].indent >= indent:
                    stack.pop()
                if stack:
                    stack[-1].children.append(line)
                else:
                    self.append(line)
                stack.append(line)

    def __str__(self) -> str:
        if self.path:
            return f"{self.path.name} at {self.source}"
        return self.source

    def __repr__(self) -> str:
        return f"<{self}>"

    def __bool__(self) -> bool:
        return bool(self.lines)

    def __len__(self) -> int:
        return len(self.lines)

    def __iter__(self) -> Iterator[Line]:
        yield from self.lines

    def __getitem__(self, index: int) -> Line:
        return self.lines[index]

    @property
    def path(self) -> pathlib.Path | None:
        if self.parent:
            return self.parent.path
        return self._path

    @property
    def source_path(self) -> pathlib.Path:
        if self.parent:
            return self.parent.source_path
        if self._source_path:
            return self._source_path
        raise RuntimeError("source path not set")

    @property
    def source_line_number(self) -> int:
        if self.parent and self.parent.container:
            return self.parent.container.source_line_number
        if self._source_line_number:
            return self._source_line_number
        raise RuntimeError("source line not set")

    @property
    def source(self) -> str:
        return f"{self.source_path.name}:{self.source_line_number}"

    def append(self, line: Line) -> None:
        self.lines.append(line)
        line.container = self

    def set_source(self, path: pathlib.Path, line_number: int) -> None:
        self._source_path, self._source_line_number = path, line_number

    def snap(self, to: int | None = None) -> Lines:
        if to is None:
            if self.parent:
                to = self.parent.indent
            else:
                to = 0
        for line in self.lines:
            line.dedent(line.indent - to)
        return self

    def to_string(self) -> str:
        output: list[str] = []
        for line in self.lines:
            output.append(line.to_string())
            if line.children:
                output.append(line.children.to_string())
        return "\n".join(output)

    def _get_source(self, stack_level: int) -> tuple[pathlib.Path, int]:
        frame = inspect.currentframe()
        for _ in range(stack_level + 1):
            frame = frame and frame.f_back
        if not frame:
            raise RuntimeError("unable to infer source")
        path = pathlib.Path(frame.f_code.co_filename)
        return path, frame.f_lineno


class Line:

    def __init__(self, number: int, indent: int, content: str) -> None:
        self.number = number
        self.indent = indent
        self.content = content
        self.container: Lines | None = None
        self.children = Lines(parent=self)

    def __str__(self) -> str:
        if self.path:
            return f"line {self.number} of {self.path.name} at {self.source}"
        return f"line {self.number} at {self.source}"

    def __repr__(self) -> str:
        return f"<{self}: {self.indent} | {self.content}>"

    @property
    def path(self) -> pathlib.Path | None:
        return self.container.path if self.container is not None else None

    @property
    def source_path(self) -> pathlib.Path:
        if not self.container:
            raise RuntimeError("source path not set")
        return self.container.source_path

    @property
    def source_line_number(self) -> int:
        if not self.container:
            raise RuntimeError("source line not set")
        if self.container.path:
            return self.container.source_line_number
        return self.container.source_line_number + 1 + self.number

    @property
    def source(self) -> str:
        return f"{self.source_path.name}:{self.source_line_number}"

    def dedent(self, offset: int) -> Line:
        self.indent = max(self.indent - offset, 0)
        for line in self.children.lines:
            line.dedent(offset)
        return self

    def to_string(self) -> str:
        return " " * self.indent + self.content
