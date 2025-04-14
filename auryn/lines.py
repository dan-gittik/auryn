from __future__ import annotations

import pathlib
from typing import Iterator

from .utils import LINE_REGEX, trim


class Lines:

    def __init__(self, lines: list[Line]) -> None:
        self.lines = lines

    def __bool__(self) -> bool:
        return bool(self.lines)

    def __len__(self) -> int:
        return len(self.lines)

    def __iter__(self) -> Iterator[Line]:
        yield from self.lines

    @classmethod
    def from_file(cls, path: str | pathlib.Path) -> Lines:
        path = pathlib.Path(path)
        return cls.from_string(path.name, path.read_text())

    @classmethod
    def from_string(cls, name: str, string: str) -> Lines:
        lines: list[Line] = []
        stack: list[Line] = []
        for number, line_string in enumerate(trim(string), 1):
            if not (match := LINE_REGEX.match(line_string)):
                continue
            whitespace, content = match.groups()
            indent = len(whitespace)
            if not content:
                continue
            line = Line(name, number, indent, content)
            while stack and stack[-1].indent >= indent:
                stack.pop()
            if stack:
                stack[-1].children.lines.append(line)
            else:
                lines.append(line)
            stack.append(line)
        return cls(lines)

    def dedent(self, offset: int) -> Lines:
        for line in self.lines:
            line.dedent(offset)
        return self

    def align(self, to: int = 0) -> Lines:
        for line in self.lines:
            line.align(to)
        return self


class Line:

    def __init__(self, source: str, number: int, indent: int, content: str) -> None:
        self.source = source
        self.number = number
        self.indent = indent
        self.content = content
        self.children = Lines([])

    def __str__(self) -> str:
        return f"line {self.number} of {self.source}"

    def __repr__(self) -> str:
        return f"<{self}: {self.content}>"

    def dedent(self, offset: int) -> Line:
        self.indent = max(self.indent - offset, 0)
        self.children.dedent(offset)
        return self

    def align(self, to: int = 0) -> Line:
        self.dedent(self.indent - to)
        return self
