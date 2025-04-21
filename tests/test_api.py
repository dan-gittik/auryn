# flake8: noqa: W293

import pathlib

import pytest

from auryn import Junk, render, transpile
from auryn.utils import split_lines

from .conftest import trim

THIS_FILE = pathlib.Path(__file__)


def test_transpile() -> None:
    received = transpile(
        """
        !for i in range(n):
            line {i}
        """,
        sourcemap=False,
    )
    expected = trim(
        """
        for i in range(n):
            emit(0, 'line ', i)
        """
    )
    assert received == expected


def test_render() -> None:
    received = render(
        """
        !for i in range(n):
            line {i}
        """,
        n=3,
    )
    expected = trim(
        """
        line 0
        line 1
        line 2
        """
    )
    assert received == expected


def test_code_block() -> None:
    received = render(
        """
        !
            def f(n):
                return n + 1
        !for i in range(f(n)):
            line {i}
        """,
        n=3,
    )
    expected = trim(
        """
        line 0
        line 1
        line 2
        line 3
        """
    )
    assert received == expected


def test_comment() -> None:
    received = render(
        """
        !# this is a comment
        !for i in range(n):
            !# this is a comment, too
            line {i}
        """,
        n=3,
    )
    expected = trim(
        """
        line 0
        line 1
        line 2
        """
    )
    assert received == expected


def test_comment_block() -> None:
    received = render(
        """
        !#
            comment line 1
            comment line 2
            comment line 3
        !for i in range(n):
            line {i}
        """,
        n=3,
    )
    expected = trim(
        """
        line 0
        line 1
        line 2
        """
    )
    assert expected == received


def test_meta_block() -> None:
    junk = Junk(
        """
        %
            x = 1
            def f(junk, s):
                junk.emit_text(junk.line.indent, s)
        %f text
        """
    )
    assert "x" not in junk.meta_namespace
    junk.transpile()
    assert junk.meta_namespace["x"] == 1
    assert junk.evaluate() == "text"


def test_empty_line() -> None:
    received = render(
        """
        line 1
                            
        line 2
        %
        line 3
        """
    )
    expected = trim(
        """
        line 1
        line 2

        line 3
        """
    )
    assert received == expected


def test_indent() -> None:
    received = render(
        """
        line 1
            line 1.1
        !if True:
            line 2
                line 2.1
            line 3
                line 3.1
        line 4
        line 5
            line 5.1
        """
    )
    expected = trim(
        """
        line 1
            line 1.1
        line 2
            line 2.1
        line 3
            line 3.1
        line 4
        line 5
            line 5.1
        """
    )
    assert received == expected