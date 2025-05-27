import pathlib
import re
from typing import Any, Iterable, Iterator, TypeGuard

LEADING_EMPTY_LINES = re.compile(r"^([ \t]*\r?\n)+")
INDENT_AND_CONTENT = re.compile(r"^(\s*)(.*)$", flags=re.DOTALL)


def concat(iterable: Iterable[Any]) -> str:
    """
    Concatenate items into a string.

        >>> and_([])
        '<none>'
        >>> and_([1])
        '1'
        >>> and_([1, 2])
        '1 and 2'
        >>> and_([1, 2, 3])
        '1, 2 and 3'

    Arguments:
        iterable: The items to concatenate.

    Returns:
        A string of the concatenated items.
    """
    items = list(iterable)
    if not items:
        return "<none>"
    if len(items) == 1:
        return str(items[0])
    if len(items) == 2:
        return f"{str(items[0])} and {str(items[1])}"
    return ", ".join(map(str, items[:-1])) + " and " + str(items[-1])


def split_indent(text: str) -> tuple[int, str]:
    """
    Split a text into its indentation and content.

        >>> split_line("text")
        (0, "text")
        >>> split_line("  text")
        (2, "text")
        >>> split_line("    text")
        (4, "text")

    Arguments:
        text: The text to split.

    Returns:
        The indentation and content.
    """
    # Regex is guaranteed to match, so we ignore the type check to avoid unreachable code.
    whitespace, content = INDENT_AND_CONTENT.match(text).groups()  # type: ignore
    indent = len(whitespace)
    return indent, content


def crop_lines(text: str) -> Iterator[tuple[int, str]]:
    """
    Split a text into lines, cropping off the indentation of the first non-empty line from each.

    This allows indenting multi-line strings to fit the code without the extra whitespace getting in the way.

        >>> for n, line in crop_lines('''
        ...     a
        ...         b
        ...     c
        ... '''):
        ...     print(n, line)
        1 a
        2     b
        3 c

    Arguments:
        text: The text to split.

    Returns:
        An iterator over pairs of line numbers and cropped lines.
    """
    # Skip leading empty lines, but count them to keep the line numbers correct.
    match = LEADING_EMPTY_LINES.match(text)
    if not match:
        skipped_lines = 0
    else:
        skipped_lines = match.group().count("\n")
        text = text[match.end() :]
    text = text.rstrip().expandtabs()
    indent: int | None = None
    for number, line in enumerate(text.splitlines(), skipped_lines):
        # First non-empty line determines the indentation to crop off.
        if indent is None:
            indent, content = split_indent(line)
            yield number, content
            continue
        if not line.strip():
            yield number, ""
            continue
        # Subsequent lines must start with at least the same indentation.
        prefix = line[:indent]
        if prefix and not prefix.isspace():
            raise ValueError(f"expected line {number} to start with {indent!r} spaces, but got {prefix!r}")
        line = line[indent:]
        yield number, line


def refers_to_file(arg: str | pathlib.Path) -> TypeGuard[pathlib.Path]:
    """
    Determine if an argument should be interpreted as a file or a string: true for path objects and strings that don't
    contain a newline.

    Arguments:
        arg: The argument to consider.

    Returns:
        Whether the argument refers to a file.
    """
    return isinstance(arg, pathlib.Path) or "\n" not in arg
