from typing import Iterator


def interpolate(text: str, delimiters: str) -> Iterator[tuple[str, bool]]:
    """
    Interpolate a string into code and text snippets.

        >>> for snippet, is_code in interpolate('{x} + {y} = {x + y}', '{ }'):
        ...     print(snippet, is_code)
        ('x', True)
        (' + ', False)
        ('y', True)
        (' = ', False)
        ('x + y', True)

    Arguments:
        text: The string to interpolate.
        delimiters: The delimiters to use.

    Returns:
        An iterator over snippets and booleans indicating whether they are code.
    """
    if delimiters.count(" ") != 1:
        raise ValueError(f"invalid delimiters: {delimiters!r} (expected a space-separated pair)")
    start, end = delimiters.split(" ")
    if not start or not end or start == end:
        raise ValueError(f"invalid delimiters: {delimiters!r} (delimiters must be non-empty and distinct)")
    # If the text is a single delimiter, or doesn't contain both delimiters, there's nothing to do.
    if text == start or text == end or (start not in text and end not in text):
        yield text, False
        return
    text_len, start_len, end_len = len(text), len(start), len(end)
    i = 0
    snippet: list[str] = []
    while i < text_len:
        if text[i : i + start_len] == start:
            # If the start delimiter appears twice, escape it.
            if text[i + start_len : i + 2 * start_len] == start:
                snippet.append(start)
                i += 2 * start_len
            # Otherwise, return the snippet that accumulated so far and the code that follows.
            else:
                fr = i + start_len
                to = _skip_expression(text, start, end, fr)
                code = text[fr:to].strip()
                if snippet:
                    yield "".join(snippet), False
                    snippet.clear()
                yield code, True
                i = to + end_len
        elif text[i : i + end_len] == end:
            # If the end delimiter appears twice, escape it.
            if text[i + end_len : i + 2 * end_len] == end:
                snippet.append(end)
                i += 2 * end_len
            # Otherwise, we have an unmatched end delimiter.
            else:
                raise ValueError(f"unable to interpolate {text!r}: unmatched {end!r} at offset {i}")
        else:
            snippet.append(text[i])
            i += 1
    if snippet:
        yield "".join(snippet), False


def split(text: str) -> Iterator[str]:
    """
    Split a string by whitespace, respecting quoted strings.

        >>> for snippet in split('flag word=value word="quoted value"'):
        ...     print(snippet)
        flag
        word=value
        word="quoted value"

    Arguments:
        text: The string to split.

    Returns:
        An iterator over snippets.
    """
    text_len, i = len(text), 0
    snippets: list[str] = []
    while i < text_len:
        if text[i] == " ":
            if snippets:
                yield "".join(snippets)
                snippets.clear()
            i += 1
        elif text[i] in ["'", '"']:
            to = _skip_string(text, i)
            snippets.append(text[i:to])
            i = to
        else:
            snippets.append(text[i])
            i += 1
    if snippets:
        yield "".join(snippets)


def _skip_expression(text: str, start: str, end: str, i: int) -> int:
    text_len, start_len, end_len, offset = len(text), len(start), len(end), i
    depth = 1
    while i < text_len:
        # Whenever the start delimiter is encountered, increase the depth.
        if text[i : i + start_len] == start:
            depth += 1
            i += start_len
        # Whenever the end delimiter is encountered, decrease the depth.
        elif text[i : i + end_len] == end:
            depth -= 1
            # If the depth reaches 0, we're done.
            if depth == 0:
                break
            i += end_len
        # If a quote is encountered, skip the string to ignore any delimiters it might contain.
        elif text[i] in ["'", '"']:
            i = _skip_string(text, i)
        else:
            i += 1
    # If the depth never reached 0, we have an unmatched start delimiter.
    if depth > 0:
        raise ValueError(f"unable to interpolate {text!r}: unmatched {start!r} at offset {offset - start_len}")
    return i


def _skip_string(text: str, i: int) -> int:
    text_len, offset = len(text), i
    quote = text[i]
    i += 1
    while i < text_len:
        if text[i] == quote:
            i += 1
            break
        # If a backslash is encountered, skip the next character to ignore escaped quotes.
        if text[i] == "\\":
            i += 2
        else:
            i += 1
    else:
        raise ValueError(f"unable to interpolate {text!r}: unterminated quote at offset {offset}")
    return i
