import pathlib

import pytest

from auryn import GX, GenerationError, execute, generate

from .conftest import this_line, trim

THIS_FILE = pathlib.Path(__file__)


def test_generate() -> None:
    received = generate(
        """
        !for i in range(n):
            line {i}
        """,
    )
    expected = trim(
        """
        for i in range(n):
            emit(0, 'line ', i)
        """
    )
    assert received == expected


def test_execute() -> None:
    received = execute(
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


def test_indent() -> None:
    received = execute(
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


def test_code_block() -> None:
    received = execute(
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


def test_comment_line() -> None:
    received = execute(
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
    received = execute(
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


def test_macro_code() -> None:
    received = execute(
        """
        %!for n, snippet in enumerate(snippets):
            %!n += 1
            %eval n={n}
            %emit <p a="{n}" b="{{n}}">
                %include: snippet
            </p>
        """,
        g_snippets=[
            """
            hello {n}
            """,
            """
            world {n}
            """,
            """
            !for i in range(n):
                line {i}
            """,
        ],
    )
    expected = trim(
        """
        <p a="1" b="1">
            hello 1
        </p>
        <p a="2" b="2">
            world 2
        </p>
        <p a="3" b="3">
            line 0
            line 1
            line 2
        </p>
        """
    )
    assert received == expected


def test_macro_code_block() -> None:
    gx = GX.parse(
        """
        %!
            x = 1
            def f(gx, s):
                gx.add_text(gx.line.indent, s)
        %f text
        """
    )
    assert "x" not in gx.g_locals
    gx.generate()
    assert gx.g_locals["x"] == 1
    assert gx.execute() == "text"


def test_macro_empty_line() -> None:
    received = execute(
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


def test_invalid_macro() -> None:
    line_number = this_line(+5)
    with pytest.raises(
        GenerationError,
        match=rf"Failed to generate GX at {THIS_FILE}:{line_number}: expected macro on line 1 to be '<macro> \[argument\]', '<macro>: <arguments>' or '<macro>:: <arguments>', but got 'include\(1, 2\)'.",  # noqa: E501 (line too long)
    ):
        generate(
            """
            %include(1, 2)
            """
        )
    line_number = this_line(+5)
    with pytest.raises(
        GenerationError,
        match=rf"Failed to generate GX at {THIS_FILE}:{line_number}: unknown macro 'hello' on line 1 \(available macros are .*?\).",  # noqa: E501 (line too long)
    ):
        generate(
            """
            %hello
            """
        )


def test_load_plugin_from_absolute_path(tmp_path: pathlib.Path) -> None:
    hello_code = trim(
        """
        def g_hello(gx, name):
            gx.add_text(0, f"hello {name}")
        """
    )
    hello_path = tmp_path / "hello.py"
    hello_path.write_text(hello_code)

    for path in [hello_path, str(hello_path)]:
        received = execute(
            """
            %hello world
            """,
            load=path,
        )
        expected = "hello world"
        assert received == expected


def test_load_plugin_from_relative_path(tmp_path: pathlib.Path) -> None:
    template_path = tmp_path / "template.aur"
    template_code = trim(
        """
        %hello world
        """
    )
    template_path.write_text(template_code)

    plugin_code = trim(
        """
        def g_hello(gx, name):
            gx.add_text(0, f"hello {name}")
        """
    )
    plugin_path = tmp_path / "plugin.py"
    plugin_path.write_text(plugin_code)

    for path in [pathlib.Path(plugin_path.name), plugin_path.name]:
        received = execute(template_path, load=path)
        expected = "hello world"
        assert received == expected


def test_load_builtin_plugin(tmp_path: pathlib.Path) -> None:
    plugin_path = tmp_path / "plugin.py"
    plugin_code = trim(
        """
        def g_hello(gx, name):
            gx.add_text(0, f"hello {name}")
        """
    )
    plugin_path.write_text(plugin_code)

    try:
        GX.add_plugins_directory(tmp_path)
        received = execute(
            """
            %hello world
            """,
            load="plugin",
        )
        expected = "hello world"
        assert received == expected
    finally:
        GX.plugin_directories.pop()


def test_load_dictionary() -> None:
    def g_hello(gx, name):
        gx.add_text(0, f"hello {name}")

    received = execute(
        """
        %hello world
        """,
        load={"g_hello": g_hello},
    )
    expected = "hello world"
    assert received == expected


def test_load_list(tmp_path: pathlib.Path) -> None:
    foo_code = trim(
        """
        def g_foo(gx):
            gx.add_text(0, "foo")
        """
    )
    foo_path = tmp_path / "foo.py"
    foo_path.write_text(foo_code)

    def g_bar(gx):
        gx.add_text(0, "bar")

    received = execute(
        """
        %foo
        %bar
        """,
        load=[foo_path, {"g_bar": g_bar}],
    )
    expected = "foo\nbar"
    assert received == expected


def test_load_plugin_from_template(tmp_path: pathlib.Path) -> None:
    plugin_code = trim(
        """
        def g_hello(gx, name):
            gx.add_text(0, f"hello {name}")
        """
    )
    plugin_path = tmp_path / "plugin.py"
    plugin_path.write_text(plugin_code)

    template_path = tmp_path / "template.aur"
    template_code = trim(
        """
        %load: plugin_path
        %hello world
        """,
    )
    template_path.write_text(template_code)

    received = execute(template_path, g_plugin_path=plugin_path)
    expected = "hello world"
    assert received == expected


def test_load_with_import(tmp_path: pathlib.Path) -> None:
    hello_code = trim(
        """
        def hello(name):
            return f"hello {name}"
        """
    )
    hello_path = tmp_path / "hello.py"
    hello_path.write_text(hello_code)

    plugin_code = trim(
        """
        from hello import hello
        def g_hello(gx, name):
            gx.add_text(0, hello(name))
        """
    )
    plugin_path = tmp_path / "plugin.py"
    plugin_path.write_text(plugin_code)

    received = execute(
        """
        %hello world
        """,
        load=plugin_path,
    )
    expected = "hello world"
    assert received == expected


def test_load_error(tmp_path: pathlib.Path) -> None:
    plugin_path = tmp_path / "plugin.py"
    plugin_path.touch()
    GX.add_plugins_directory(tmp_path)
    try:
        with pytest.raises(
            ValueError,
            match=r"unable to load 'hello.py' \(.*?hello.py does not exist and available plugins are core, filesystem and plugin\)",  # noqa: E501 (line too long)
        ):
            generate(
                """
                !for i in range(n):
                    line {i}
                """,
                load="hello.py",
            )
    finally:
        GX.plugin_directories.pop()


def test_generation_context() -> None:
    received = generate(
        """
        %!
            def f(gx, x):
                gx.add_code(f'print({x!r})')
        %f: a
        %f: b
        """,
        {"a": 1},
        b="hello",
    )
    expected = trim(
        """
        print(1)
        print('hello')
        """
    )
    assert received == expected


def test_text_with_cropping() -> None:
    received = execute(
        """
        %!
            def f(gx, interpolate=None):
                gx.add_text(gx.line.indent,
                    '''
                    line {a}
                    line {b}
                    ''',
                    interpolate=interpolate,
                    crop=True,
                )
        %f
        %f: interpolate=False
        """,
        a=1,
        b=2,
    )
    expected = trim(
        """
        line 1
        line 2
        line {a}
        line {b}
        """
    )
    assert received == expected


def test_interpolated(capsys: pytest.CaptureFixture[str]) -> None:
    execute(
        """
        %!
            def print(gx, name=""):
                gx.add_code(f'print({gx.interpolated(name)})')
        %print
        %print hello
        %print hello {name}
        """,
        name="world",
    )
    received = capsys.readouterr().out
    expected = "\nhello\nhello world\n"
    assert received == expected


def test_no_line_transforms() -> None:
    line_number = this_line(+1)
    gx = GX.parse(
        """
        !for i in range(n):
            line {i}
        """
    )
    del gx.line_transforms[""]
    with pytest.raises(
        GenerationError,
        match=rf"Failed to generate GX at {THIS_FILE}:{line_number}: unable to transform line 2 \(considered transform_code \(!\) and transform_macro \(%\)\).",  # noqa: E501 (line too long)
    ):
        gx.generate()
    gx.line_transforms.clear()
    with pytest.raises(
        GenerationError,
        match=rf"Failed to generate GX at {THIS_FILE}:{line_number}: unable to transform line 1 \(considered <none>\).",  # noqa: E501 (line too long)
    ):
        gx.generate()
