from typing import Any, Iterable


def concat(iterable: Iterable[Any], conjunction: str, quote: bool = False) -> str:
    items = list(iterable)
    if quote:
        cast = repr
    else:
        cast = str
    if not items:
        return "<none>"
    if len(items) == 1:
        return cast(items[0])
    if len(items) == 2:
        return f"{cast(items[0])} {conjunction} {cast(items[1])}"
    return ", ".join(map(cast, items[:-1])) + f" {conjunction} {cast(items[-1])}"


def and_(iterable: Iterable[Any], quote: bool = False) -> str:
    return concat(iterable, "and", quote)


def or_(iterable: Iterable[Any], quote: bool = False) -> str:
    return concat(iterable, "or", quote)