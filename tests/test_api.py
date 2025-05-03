# flake8: noqa: W293

import pathlib

import pytest

from auryn import Junk, evaluate, render, transpile

from .conftest import this_line, trim

THIS_FILE = pathlib.Path(__file__)


def test_transpile() -> None:
    received = transpile(
        """
        !for i in range(n):
            line {i}
        """,
        add_source_comments=False,
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
        %!
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


def test_standalone() -> None:
    code = transpile(
        """
        !n = x + y
        !for i in range(n):
            line {i}
        """,
        standalone=True,
    )
    received = evaluate(code, {"x": 1}, y=2)
    expected = trim(
        """
        line 0
        line 1
        line 2
        """
    )
    assert received == expected


def test_standalone_with_meta_module(tmp_path: pathlib.Path) -> None:
    meta_path = tmp_path / "meta.py"
    meta_code = trim(
        """
        import base64
        from base64 import b64encode
        import binascii as BINASCII
        from binascii import hexlify as HEXLIFY

        def encode(name):
            return HEXLIFY(b64encode(name.encode())).decode()
        
        def decode(name):
            return base64.b64decode(BINASCII.unhexlify(name.encode())).decode()

        def meta_transcode(junk, expression):
            junk.emit_code(f"transcode({junk.interpolate(expression)})")
        
        def eval_transcode(junk, expression):
            expression = encode(expression)
            emit(0, decode(expression))
        """
    )
    meta_path.write_text(meta_code)

    template_path = tmp_path / "template.txt"
    template_code = trim(
        """
        %transcode {x} + {y} = {x + y}
        """
    )
    template_path.write_text(template_code)

    code = transpile(template_path, load=meta_path, standalone=True)
    code_path = tmp_path / "code.py"
    code_path.write_text(code)

    received = evaluate(code_path, {"x": 1}, y=2)
    expected = "1 + 2 = 3"
    assert received == expected


def test_interpolate(capsys: pytest.CaptureFixture[str]) -> None:
    render(
        """
        %!
            def print(junk, name=""):
                junk.emit_code(f'print({junk.interpolate(name)})')
        %print
        %print hello
        %print hello {name}
        """,
        name="world",
    )
    received = capsys.readouterr().out
    expected = "\nhello\nhello world\n"
    assert received == expected


def test_no_transpilers() -> None:
    line_number = this_line(+2)
    junk = Junk(
        """
        !for i in range(n):
            line {i}
        """
    )
    del junk.transpilers[""]
    with pytest.raises(
        ValueError,
        match=rf"unable to transpile line 2 at {THIS_FILE.name}:{line_number + 2} \(considered code \(!\) and meta \(%\)\)",
    ):
        junk.transpile()
    junk.transpilers.clear()
    with pytest.raises(
        ValueError,
        match=rf"unable to transpile line 1 at {THIS_FILE.name}:{line_number + 1} \(considered <none>\)",
    ):
        junk.transpile()