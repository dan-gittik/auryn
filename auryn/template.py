from __future__ import annotations

import pathlib
from typing import ClassVar, Iterator, Self

from .utils import crop_lines, refers_to_file, split_indent

type TemplateArgument = str | pathlib.Path | Template


class Template:
    """
    A template used by a generation/execution.

        >>> template = Template.parse('''
        ...     a
        ...         b
        ...         c
        ...     d
        ... ''')
        >>> template
        <template: a b c d...>
        >>> template.lines
        <lines 1-4>
        >>> template.lines[0]
        <line 1: 0 | a>
        >>> template.lines[0].children
        <children 2-3 of line 1>
        >>> template.lines[0].children[0]
        <line 2: 4 | b>

    Attributes:
        text: The template text.
        path: The template path (or None if it's a string).
        lines: The root lines of the template (see Lines).
    """

    # How much of the template's content is included in its string representation.
    preview_length: ClassVar[int] = 60

    def __init__(self, text: str = "", path: pathlib.Path | None = None, lines: Lines | None = None) -> None:
        if lines is None:
            lines = Lines()
        self.text = text
        self.path = path
        self.lines = lines

    def __str__(self) -> str:
        output = ["template"]
        if self.path:
            output.append(f" from {self.path}")
        return "".join(output)

    def __repr__(self) -> str:
        output = [str(self)]
        preview = " ".join(line.strip() for line in self.lines.to_string().splitlines())[: self.preview_length]
        if preview:
            output.append(f": {preview}...")
        return f"<{''.join(output)}>"

    @classmethod
    def parse(cls, template: TemplateArgument) -> Template:
        """
        Parse a template from a string, a path, or another template object.

        Arguments:
            template: The template to parse.
                If it's a template object, it's returned as is; if it's a path object or a string refering to a valid
                file, its contents are parsed; otherwise, *it* is parsed.

        Returns:
            The parsed template.
        """
        if isinstance(template, Template):
            return template
        if refers_to_file(template):
            path = pathlib.Path(template)
            text = path.read_text()
        else:
            path = None
            text = str(template)
        # Line numbers should start at 1, but crop_lines returns 0-indexed numbers. This works for strings where the
        # first line is empty (e.g. """\n...\n"""), but for files it should be offset by 1.
        offset = 1 if path else 0
        lines = Lines()
        stack: list[Line] = []
        for number, line_text in crop_lines(text):
            number += offset
            indent, content = split_indent(line_text)
            # If the line is empty, use the indentation of the previous line.
            if not content:
                indent = stack[-1].indent if stack else 0
            # Find the last line with greater or equal indentation.
            while stack and stack[-1].indent >= indent:
                stack.pop()
            # If the stack is not empty, this line is a child of the last line in the stack.
            if stack:
                line = stack[-1].children.append(number, indent, content)
            # Otherwise, it's a root line.
            else:
                line = lines.append(number, indent, content)
            stack.append(line)
        return cls(text, path, lines)


class Lines:
    """
    A collection of template lines.

        >>> template = Template.parse('''
        ...     a
        ...         b
        ...         c
        ...     d
        ... ''')
        >>> lines = template.lines
        >>> lines
        <lines 1-4>

    The lines object behaves like a list of lines with the same indentation. In a template, these are the *root* lines:

        >>> bool(lines)
        True
        >>> len(lines)
        2  # Not 4: lines 2 and 3 are nested in line 1.
        >>> for line in lines:
        ...     print(line)
        line 1: 0 | a
        line 4: 0 | d
        >>> lines[0]
        line 1: 0 | a
        >>> lines[1]
        line 4: 0 | d

    With each line's children being a nested lines object:

        >>> children = lines[0].children
        >>> children
        <children 2-3 of line 1>
        >>> children[0]
        line 2: 4 | b
        >>> children[1]
        line 3: 4 | c

    Attributes:
        parent: The line under which these lines are nested (or None for root lines).
    """

    def __init__(self, parent: Line | None = None) -> None:
        self.parent = parent
        self._lines: list[Line] = []

    def __str__(self) -> str:
        if not self._lines:
            return "no lines"
        first, last = self._lines[0], self._lines[-1]
        while last.children:
            last = last.children[-1]
        if self.parent:
            return f"children {first.number}-{last.number} of {self.parent}"
        return f"lines {first.number}-{last.number}"

    def __repr__(self) -> str:
        return f"<{self}>"

    def __bool__(self) -> bool:
        return bool(self._lines)

    def __len__(self) -> int:
        return len(self._lines)

    def __iter__(self) -> Iterator[Line]:
        yield from self._lines

    def __getitem__(self, index: int) -> Line:
        return self._lines[index]

    def append(self, number: int, indent: int, content: str) -> Line:
        """
        Append a line.

        Arguments:
            number: The line number.
            indent: The line indentation.
            content: The line content.

        Returns:
            The appended line.
        """
        line = Line(number, indent, content)
        self._lines.append(line)
        return line

    def snap(self, to: int | None = None) -> Self:
        """
        Align the lines to a given indentation.

            >>> lines = Lines('''
            ...      a
            ...         b
            ... ''')
            >>> lines[0][0]
            line 2: 4 | b  # Line 2 indentation is 4.
            >>> lines.snap(2)[0][0]
            line 2: 6 | b  # Line 1 was aligned to 2, so Line 2's indentation is now 6.
            >>> lines[0].children.snap()
            >>> lines[0][0]
            line 2: 2 | b  # Line 1's children were aligned to its indentation, so Line 2's indentation is now 2.
            >>> lines.snap()
            >>> lines[0][0]
            line 1: 0 | b  # Line 1's indentation was aligned to 0, so Line 2's indentation is now 0 as well.

        Arguments:
            to: The indentation to align to.
                If not provided, the lines are aligned to the indentation of their parent.
                If there is no parent, the lines are aligned to 0.

        Returns:
            This lines object, for chaining.
        """
        if to is None:
            if self.parent:
                to = self.parent.indent
            else:
                to = 0
        for line in self._lines:
            line._dedent(line.indent - to)
        return self

    def to_string(self) -> str:
        """
        Return the lines as a string.

            >>> lines = Lines('''
            ...     a
            ...         b
            ...         c
            ...     d
            ... ''')
            >>> lines.to_string()
            'a\n    b\n    c\nd'
            >>> print(_)
            a
                b
                c
            d

        Returns:
            The lines as a string.
        """
        output: list[str] = []
        for line in self._lines:
            output.append(" " * line.indent + line.content)
            if line.children:
                output.append(line.children.to_string())
        return "\n".join(output)


class Line:
    """
    A template line.

        >>> line = Line(1, 0, "a")
        >>> line
        line 1: 0 | a
        >>> line.number
        1
        >>> line.indent
        0
        >>> line.content
        'a'
        >>> line.children
        <no lines>

    Line objects are usually created (and organized into parents and children) when a template is parsed:

        >>> template = Template.parse('''
        ...     a
        ...         b
        ...         c
        ... ''')
        >>> line = template.lines[0]
        >>> line
        line 1: 0 | a
        >>> line.children
        <children 2-3 of line 1>

    Arguments:
        number: The line number.
        indent: The indentation level.
        content: The content of the line.
    """

    def __init__(self, number: int, indent: int, content: str) -> None:
        self.number = number
        self.indent = indent
        self.content = content
        self.children = Lines(parent=self)

    def __str__(self) -> str:
        return f"line {self.number}"

    def __repr__(self) -> str:
        return f"<{self}: {self.indent} | {self.content}>"

    def _dedent(self, offset: int) -> Self:
        self.indent = max(self.indent - offset, 0)
        for line in self.children:
            line._dedent(offset)
        return self
