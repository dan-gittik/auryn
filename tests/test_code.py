import pathlib

from auryn import Code, execute_standalone, generate

from .conftest import trim


def test_code_from_string() -> None:
    code = generate(
        """
        !for i in range(n):
            line {i}
        """,
        standalone=True,
    )
    code, intro = Code.restore(code)
    assert intro == ""

    line1 = code.lines[0]
    assert line1.template_line_number == 1
    assert line1.indent == 0
    assert line1.content == "for i in range(n):"

    line2 = code.lines[1]
    assert line2.template_line_number == 2
    assert line2.indent == 4
    assert line2.content == "emit(0, 'line ', i)"


def test_code_from_file(tmp_path: pathlib.Path) -> None:
    code = generate(
        """
        !for i in range(n):
            line {i}
        """,
        standalone=True,
    )
    code_path = tmp_path / "code.py"
    code_path.write_text(code)

    code, intro = Code.restore(code_path)
    assert intro == ""

    line1 = code.lines[0]
    assert line1.template_line_number == 1
    assert line1.indent == 0
    assert line1.content == "for i in range(n):"

    line2 = code.lines[1]
    assert line2.template_line_number == 2
    assert line2.indent == 4
    assert line2.content == "emit(0, 'line ', i)"


def test_code_from_code() -> None:
    code1 = Code()
    code2, intro = Code.restore(code1)
    assert intro == ""
    assert code1 is code2


def test_execute_standalone() -> None:
    code = generate(
        """
        !n = x + y
        !for i in range(n):
            line {i}
        """,
        standalone=True,
    )
    received = execute_standalone(code, {"x": 1}, y=2)
    expected = trim(
        """
        line 0
        line 1
        line 2
        """
    )
    assert received == expected


def test_execute_standalone_with_plugin(tmp_path: pathlib.Path) -> None:
    plugin_path = tmp_path / "plugin.py"
    plugin_code = trim(
        """
        import base64
        from base64 import b64encode
        import binascii as BINASCII
        from binascii import hexlify as HEXLIFY

        def encode(name):
            return HEXLIFY(b64encode(name.encode())).decode()

        def decode(name):
            return base64.b64decode(BINASCII.unhexlify(name.encode())).decode()

        def g_transcode(gx, expression):
            gx.add_code(f"transcode({gx.interpolated(expression)})")

        def x_transcode(gx, expression):
            expression = encode(expression)
            gx.emit(0, decode(expression))
        """
    )
    plugin_path.write_text(plugin_code)

    template_path = tmp_path / "template.aur"
    template_text = trim(
        """
        %transcode {x} + {y} = {x + y}
        """
    )
    template_path.write_text(template_text)

    code = generate(template_path, load=plugin_path, standalone=True)
    received = execute_standalone(code, {"x": 1}, y=2)
    expected = "1 + 2 = 3"
    assert received == expected


def test_execute_standalone_with_decorator(tmp_path: pathlib.Path) -> None:
    plugin_path = tmp_path / "plugin.py"
    plugin_code = trim(
        """
        from contextlib import contextmanager

        @contextmanager
        def x_context_manager(gx):
            gx.emit(0, "before")
            yield
            gx.emit(0, "after")

        def g_hello(gx, name):
            gx.add_code("with context_manager():")
            with gx.increased_code_indent():
                gx.add_text(0, f"hello {name}")
        """
    )
    plugin_path.write_text(plugin_code)

    template_path = tmp_path / "template.aur"
    template_text = trim(
        """
        %hello world
        """
    )
    template_path.write_text(template_text)

    code = generate(template_path, load=plugin_path, standalone=True)
    received = execute_standalone(code, {"x": 1}, y=2)
    expected = "before\nhello world\nafter"
    assert received == expected


def test_execute_standalone_with_multiple_sources(tmp_path: pathlib.Path) -> None:
    template1_path = tmp_path / "template1.aur"
    template1_text = trim(
        """
        line 1
        %include template2.aur
        """
    )
    template1_path.write_text(template1_text)

    template2_path = tmp_path / "template2.aur"
    template2_text = trim(
        """
        line 2
        %include template3.aur
        """
    )
    template2_path.write_text(template2_text)

    template3_path = tmp_path / "template3.aur"
    template3_text = trim(
        """
        line 3
        """
    )
    template3_path.write_text(template3_text)

    code = generate(template1_path, standalone=True)
    received = execute_standalone(code, {"x": 1}, y=2)
    expected = "line 1\nline 2\nline 3"
    assert received == expected

    code_, _ = Code.restore(code)
    uids: set[str] = set()
    for line in code_.lines:
        assert line.template_line_number == 1
        uids.add(line.gx.id)
    assert len(uids) == 3
