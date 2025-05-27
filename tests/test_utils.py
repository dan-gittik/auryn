import pathlib

import pytest

from auryn.utils import concat, crop_lines, refers_to_file, split_indent


def test_concat_none() -> None:
    for empty in ([], set(), (i for i in range(1, 1))):
        assert concat(empty) == "<none>"


def test_concat_one() -> None:
    for one in ([1], {1}, (i for i in range(1, 2))):
        assert concat(one) == "1"


def test_concat_two() -> None:
    for two in ([1, 2], {1, 2}, (i for i in range(1, 3))):
        assert concat(two) == "1 and 2"


def test_concat_many() -> None:
    for many in ([1, 2, 3], {1, 2, 3}, (i for i in range(1, 4))):
        assert concat(many) == "1, 2 and 3"


def test_split_indent() -> None:
    assert split_indent("") == (0, "")
    assert split_indent("a") == (0, "a")
    assert split_indent("a b") == (0, "a b")
    assert split_indent("    a") == (4, "a")
    assert split_indent("    a b") == (4, "a b")


def test_crop_lines() -> None:
    received = crop_lines(
        """
        a
        b
        c
        """
    )
    expected = [
        (1, "a"),
        (2, "b"),
        (3, "c"),
    ]
    assert list(received) == expected


def test_crop_lines_with_indent() -> None:
    received = crop_lines(
        """
        a
            b
            c
        d
            e
            f
        """
    )
    expected = [
        (1, "a"),
        (2, "    b"),
        (3, "    c"),
        (4, "d"),
        (5, "    e"),
        (6, "    f"),
    ]
    assert list(received) == expected


def test_crop_lines_with_empty_lines() -> None:
    received = crop_lines(
        """

        a

        b


        c
        """
    )
    expected = [
        (2, "a"),
        (3, ""),
        (4, "b"),
        (5, ""),
        (6, ""),
        (7, "c"),
    ]
    assert list(received) == expected


def test_crop_empty_lines() -> None:
    assert list(crop_lines("")) == []


def test_crop_lines_with_invalid_indent() -> None:
    with pytest.raises(
        ValueError,
        match=r"expected line 2 to start with 12 spaces, but got '\s+b'",
    ):
        received = crop_lines(
            """
            a
        b
            c
            """
        )
        list(received)


def test_refers_to_file(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "test.txt"
    assert refers_to_file(path)
    assert refers_to_file(str(path))
    assert not refers_to_file(f"{path}\n")
    assert not refers_to_file(f"\n{path}")
    assert not refers_to_file(
        f"""
        {path}
    """
    )
