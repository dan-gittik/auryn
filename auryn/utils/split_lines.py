import re
from typing import Iterator

LEADING_EMPTY_LINES = re.compile(r"^([ \t]*\r?\n)+")
LINE_REGEX = re.compile(r"^(\s*)(.*)$")
OPEN_LINE_SUFFIX = "\\"


def split_line(text: str) -> tuple[int, str]:
    whitespace, content = LINE_REGEX.match(text).groups()  # type: ignore
    indent = len(whitespace)
    return indent, content


def split_lines(text: str) -> Iterator[tuple[int, str]]:
    match = LEADING_EMPTY_LINES.match(text)
    if not match:
        skipped_lines = 0
    else:
        skipped_lines = match.group().count("\n")
        text = text[match.end() :]
    text = text.rstrip().expandtabs()
    indent: int | None = None
    open_line: list[str] = []
    open_line_number = 0
    for number, line in enumerate(text.splitlines(), skipped_lines + 1):
        if indent is None:
            indent, content = split_line(line)
            if content.endswith(OPEN_LINE_SUFFIX):
                open_line.append(content.removesuffix(OPEN_LINE_SUFFIX).strip())
                open_line_number = number
                continue
            yield number, content
            continue
        if not line.strip():
            continue
        if open_line:
            open_line.append(line.removesuffix(OPEN_LINE_SUFFIX).strip())
            if line.endswith(OPEN_LINE_SUFFIX):
                continue
            yield open_line_number, " ".join(open_line)
            open_line.clear()
            continue
        prefix = line[:indent]
        if prefix and not prefix.isspace():
            raise ValueError(f"expected line {number} to start with {indent!r} spaces, but got {prefix!r}")
        line = line[indent:]
        if line.endswith(OPEN_LINE_SUFFIX):
            open_line.append(line.removesuffix(OPEN_LINE_SUFFIX).strip())
            open_line_number = number
            continue
        yield number, line
    if open_line:
        yield open_line_number, " ".join(open_line)
