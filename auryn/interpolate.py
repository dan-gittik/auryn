from typing import Iterator


def interpolate(s: str, delimiters: str) -> Iterator[tuple[str, bool]]:
    if delimiters.count(" ") != 1:
        raise ValueError(f"invalid delimiters {delimiters!r} (expected space-separated pair)")
    a, b = delimiters.split(" ")
    if s == a or s == b or (a not in s and b not in s):
        yield s, False
        return
    sL, aL, bL = len(s), len(a), len(b)
    i = 0
    text = []
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


def skip_expression(s, a, b, i):
    L, aL, bL = len(s), len(a), len(b)
    depth = 1
    while i < L:
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
        raise ValueError(f"unable to interpolate {s!r}: unmatched {a!r} at offset {i}")
    return i


def skip_string(s, i):
    sL = len(s)
    q = s[i]
    i += 1
    while i < sL:
        if s[i] == q:
            i += 1
            break
        if s[i] == "\\":
            i += 2
        else:
            i += 1
    else:
        raise ValueError(f"unable to interpolate {s!r}: unterminated quote at offset {i}")
    return i
