import os
import pathlib

import pytest

from auryn.utils import and_, is_path, or_, split_line, split_lines

from .conftest import trim


def test_and_none() -> None:
    for empty in ([], set(), (i for i in range(1, 1))):
        assert and_(empty) == "<none>"


def test_and_one() -> None:
    for one in ([1], {1}, (i for i in range(1, 2))):
        assert and_(one) == "1"


def test_and_two() -> None:
    for two in ([1, 2], {1, 2}, (i for i in range(1, 3))):
        assert and_(two) == "1 and 2"


def test_and_many() -> None:
    for many in ([1, 2, 3], {1, 2, 3}, (i for i in range(1, 4))):
        assert and_(many) == "1, 2 and 3"


def test_and_quote() -> None:
    items = ["a", "b", "c"]
    assert and_(items) == "a, b and c"
    assert and_(items, quote=True) == "'a', 'b' and 'c'"


def test_or_none() -> None:
    for empty in ([], set(), (i for i in range(1, 1))):
        assert or_(empty) == "<none>"


def test_or_one() -> None:
    for one in ([1], {1}, (i for i in range(1, 2))):
        assert or_(one) == "1"


def test_or_two() -> None:
    for two in ([1, 2], {1, 2}, (i for i in range(1, 3))):
        assert or_(two) == "1 or 2"


def test_or_many() -> None:
    for many in ([1, 2, 3], {1, 2, 3}, (i for i in range(1, 4))):
        assert or_(many) == "1, 2 or 3"


def test_or_quote() -> None:
    items = ["a", "b", "c"]
    assert or_(items) == "a, b or c"
    assert or_(items, quote=True) == "'a', 'b' or 'c'"


def test_split_line() -> None:
    assert split_line("") == (0, "")
    assert split_line("a") == (0, "a")
    assert split_line("a b") == (0, "a b")
    assert split_line("    a") == (4, "a")
    assert split_line("    a b") == (4, "a b")


def test_split_lines() -> None:
    assert (
        list(
            split_lines(
                """
        a
        b
        c
        """
            )
        )
        == [
            (2, "a"),
            (3, "b"),
            (4, "c"),
        ]
    )


def test_split_lines_with_indent() -> None:
    assert (
        list(
            split_lines(
                """
        a
            b
            c
        d
            e
            f
        """
            )
        )
        == [
            (2, "a"),
            (3, "    b"),
            (4, "    c"),
            (5, "d"),
            (6, "    e"),
            (7, "    f"),
        ]
    )


def test_split_lines_none() -> None:
    assert list(split_lines("")) == []


def test_split_lines_with_empty_lines() -> None:
    assert (
        list(
            split_lines(
                """


        a

        b


        c
        """
            )
        )
        == [
            (4, "a"),
            (5, ""),
            (6, "b"),
            (7, ""),
            (8, ""),
            (9, "c"),
        ]
    )


def test_split_line_with_open_lines() -> None:
    assert (
        list(
            split_lines(
                """
        a \\
        b
        c
    """
            )
        )
        == [
            (2, "a b"),
            (4, "c"),
        ]
    )
    assert (
        list(
            split_lines(
                """
        a
        b \\

            c \\
    d
        e
    """
            )
        )
        == [
            (2, "a"),
            (3, "b c d"),
            (7, "e"),
        ]
    )
    assert (
        list(
            split_lines(
                """
        a
        b \\
        c \\
        """
            )
        )
        == [
            (2, "a"),
            (3, "b c"),
        ]
    )


def test_split_line_error() -> None:
    with pytest.raises(
        ValueError,
        match="expected line 3 to start with 12 spaces, but got '        b'",
    ):
        list(
            split_lines(
                """
            a
        b
            c
            """
            )
        )


def test_is_path(tmp_path: pathlib.Path) -> None:
    name = "test.txt"
    path = tmp_path / name
    path.touch()
    assert is_path(path)
    assert is_path(str(path))
    assert not is_path(name)
    assert is_path(name, tmp_path)
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        assert is_path(name)
    finally:
        os.chdir(cwd)
    assert not is_path(f"{name}\n")
    assert not is_path(f"\n{name}")
    assert not is_path("a")
    text = trim(
        """
        !for i in range(n):
            line {i}
        """
    )
    assert not is_path(text)
    text = trim(
        """
        %hello
        """
    )
    assert not is_path(text)