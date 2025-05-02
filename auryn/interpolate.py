from typing import Iterator

default_delimiters = "{ }"


def interpolate(s: str, delimiters: str | None = None) -> Iterator[tuple[str, bool]]:
    if delimiters is None:
        delimiters = default_delimiters
    if delimiters.count(" ") != 1:
        raise ValueError(f"invalid delimiters {delimiters!r} (expected space-separated pair)")
    a, b = delimiters.split(" ")
    if not a or not b or a == b:
        raise ValueError(f"invalid delimiters {delimiters!r} (delimiters must be non-empty and distinct)")
    if s == a or s == b or (a not in s and b not in s):
        yield s, False
        return
    sL, aL, bL = len(s), len(a), len(b)
    i = 0
    text: list[str] = []
    while i < sL:
        if s[i : i + aL] == a:
            if s[i + aL : i + 2 * aL] == a:
                text.append(a)
                i += 2 * aL
            else:
                fr = i + aL
                to = skip_expression(s, a, b, fr)
                code = s[fr:to].strip()
                if text:
                    yield "".join(text), False
                    text.clear()
                yield code, True
                i = to + bL
        elif s[i : i + bL] == b:
            if s[i + bL : i + 2 * bL] == b:
                text.append(b)
                i += 2 * bL
            else:
                raise ValueError(f"unable to interpolate {s!r}: unmatched {b!r} at offset {i}")
        else:
            text.append(s[i])
            i += 1
    if text:
        yield "".join(text), False


def parse_arguments(s: str) -> Iterator[str]:
    sL, i = len(s), 0
    text: list[str] = []
    while i < sL:
        if s[i] == " ":
            if text:
                yield "".join(text)
                text.clear()
            i += 1
        elif s[i] in ["'", '"']:
            to = skip_string(s, i)
            text.append(s[i:to])
            i = to
        else:
            text.append(s[i])
            i += 1
    if text:
        yield "".join(text)


def skip_expression(s, a, b, i):
    sL, aL, bL, i0 = len(s), len(a), len(b), i
    depth = 1
    while i < sL:
        if s[i : i + aL] == a:
            depth += 1
            i += aL
        elif s[i : i + bL] == b:
            depth -= 1
            if depth == 0:
                break
            i += bL
        elif s[i] in ["'", '"']:
            i = skip_string(s, i)
        else:
            i += 1
    else:
        raise ValueError(f"unable to interpolate {s!r}: unmatched {a!r} at offset {i0 - aL}")
    return i


def skip_string(s, i):
    sL, i0 = len(s), i
    q = s[i]
    i += 1
    while i < sL:
        if s[i] == q:
            i += 1
            break
        if s[i] == "\\":
            print(s[i : i + 2])
            i += 2
        else:
            i += 1
    else:
        raise ValueError(f"unable to interpolate {s!r}: unterminated quote at offset {i0}")
    return i
