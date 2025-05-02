import pytest

from auryn.utils import split_line, split_lines


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
