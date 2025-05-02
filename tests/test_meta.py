# flake8: noqa: W291

import pathlib

import pytest

from auryn import EvaluationError, Junk, render, transpile

from .conftest import this_line, trim

THIS_FILE = pathlib.Path(__file__)


def test_include(tmp_path: pathlib.Path) -> None:
    loop = trim(
        """
        !for i in range(n):
            line {i}
        """
    )
    path = tmp_path / "loop.template"
    path.write_text(loop)

    main = trim(
        """
        !n = 3
        %include loop.template
        """
    )
    path = tmp_path / "main.template"
    path.write_text(main)

    received = render(path)
    expected = trim(
        """
        line 0
        line 1
        line 2
        """
    )
    assert received == expected


def test_include_load(tmp_path: pathlib.Path) -> None:
    meta_path = tmp_path / "meta.py"
    meta_code = trim(
        """
        def on_load(junk):
            junk.transpilers[""] = text
        
        def text(junk, content):
            if content:
                return junk.emit_text(junk.line.indent, f"<p>{content}</p>")
            junk.transpile()
        """
    )
    meta_path.write_text(meta_code)

    template = trim(
        """
        !for i in range(n):
            line {i}
        """
    )

    received = render(
        """
        %include: template load=meta_path
        """,
        meta_context={
            "template": template,
            "meta_path": meta_path,
        },
        n=3,
    )
    expected = trim(
        """
        <p>line 0</p>
        <p>line 1</p>
        <p>line 2</p>
        """
    )
    assert received == expected


def test_insert() -> None:
    received = render(
        """
        %define one
            line 1
        %define: "two"
            line 2
        %insert two
        %insert: "one"
        """
    )
    expected = trim(
        """
        line 2
        line 1
        """
    )
    assert received == expected


def test_insert_missing() -> None:
    received = render(
        """
        %insert block
            default line
        """
    )
    expected = "default line"
    assert received == expected

    line_number = this_line(+9)
    with pytest.raises(
        ValueError,
        match=rf"missing required definition 'block' on line 3 at {THIS_FILE.name}:{line_number} \(available definitions are a and b\)",
    ):
        render(
            """
            %define a
            %define b
            %insert: "block" required=True
            """
        )

    received = render(
        """
        %define block
            inserted line
        %insert:: "block", required=True
        """
    )
    expected = "inserted line"
    assert received == expected


def test_extend(tmp_path: pathlib.Path) -> None:
    base = trim(
        """
        <head>
            %insert head
                <title>default title</title>
        </head>
        <body>
            %insert: "body" required=True
        </body>
        """
    )
    base_path = tmp_path / "base.template"
    base_path.write_text(base)

    main = trim(
        """
        %extend base.template
        %define head
            <title>inserted title</title>
        %define body
            <p>inserted body</p>
        """
    )
    main_path = tmp_path / "main.template"
    main_path.write_text(main)

    received = render(main_path)
    expected = trim(
        """
        <head>
            <title>inserted title</title>
        </head>
        <body>
            <p>inserted body</p>
        </body>
        """
    )
    assert received == expected

    body = trim(
        """
        %extend base.template
        %define body
            <p>inserted body</p>
        """
    )
    body_path = tmp_path / "body.template"
    body_path.write_text(body)

    received = render(body_path)
    expected = trim(
        """
        <head>
            <title>default title</title>
        </head>
        <body>
            <p>inserted body</p>
        </body>
        """
    )
    assert received == expected

    head = trim(
        """
        %extend base.template
        %define head
            <title>inserted title</title>
        """
    )
    head_path = tmp_path / "head.template"
    head_path.write_text(head)
    line_number = this_line(+5)
    with pytest.raises(
        ValueError,
        match=rf"missing required definition 'body' on line 6 of {base_path.name} at {THIS_FILE.name}:{line_number} \(available definitions are head\)",
    ):
        render(head_path)


def test_extend_block(tmp_path: pathlib.Path) -> None:
    base = trim(
        """
        %insert block
        """
    )
    base_path = tmp_path / "base.template"
    base_path.write_text(base)

    main = trim(
        """
        missing line
        %extend base.template
        %define block
            extended line
        missing line
        """
    )
    main_path = tmp_path / "main.template"
    main_path.write_text(main)

    received = render(main_path)
    expected = "extended line"
    assert expected == received

    main = trim(
        """
        first line
        %extend base.template
            %define block
                extended line
        last line
        """
    )
    main_path = tmp_path / "main.template"
    main_path.write_text(main)

    received = render(main_path)
    expected = trim(
        """
        first line
        extended line
        last line
        """
    )
    assert expected == received


def test_raw() -> None:
    received = render(
        """
        %raw
        !for i in range(n):
            line {i}
        %command
        """
    )
    expected = trim(
        """
        !for i in range(n):
            line {i}
        %command
        """
    )
    assert received == expected


def test_raw_block() -> None:
    received = render(
        """
        %raw
            !for i in range(n):
                line {i}
            %command
        !for i in range(n):
            line {i}
        """,
        n=3,
    )
    expected = trim(
        """
        !for i in range(n):
            line {i}
        %command
        line 0
        line 1
        line 2
        """
    )
    assert received == expected


def test_interpolate() -> None:
    received = render(
        """
        !for i in range(n):
            line {i}
            line <i>
        """,
        n=3,
    )
    expected = trim(
        """
        line 0
        line <i>
        line 1
        line <i>
        line 2
        line <i>
        """
    )
    assert received == expected

    received = render(
        """
        %interpolate < >
        !for i in range(n):
            line {i}
            line <i>
        """,
        n=3,
    )
    expected = trim(
        """
        line {i}
        line 0
        line {i}
        line 1
        line {i}
        line 2
        """
    )
    assert received == expected


def test_interpolate_block() -> None:
    received = render(
        """
        %interpolate < >
            !for i in range(n):
                line {i}
                line <i>
        line {i}
        line <i>
        """,
        n=3,
    )
    expected = trim(
        """
        line {i}
        line 0
        line {i}
        line 1
        line {i}
        line 2
        line 2
        line <i>
        """
    )
    assert received == expected


def test_interpolation_escaping() -> None:
    received = render(
        """
        { x }
        {{ x }}
        %interpolate {{ }}
            {{ x }}
            {{{{ x }}}}
        %interpolate <% %>
            <% x %>
            <%<% x %>%>
        %interpolate (| |)
            (| x |)
            (|(| x |)|)
        """,
        x=1,
    )
    expected = trim(
        """
        1
        { x }
        1
        {{ x }}
        1
        <% x %>
        1
        (| x |)
        """
    )
    assert received == expected


def test_stop() -> None:
    received = render(
        """
        line 1
        %stop
        line 2
        """
    )
    expected = "line 1"
    assert received == expected


def test_param() -> None:
    line_number = this_line(+5)
    with pytest.raises(
        EvaluationError,
        match=rf"missing required parameter 'x' in {THIS_FILE.name}:{line_number}",
    ):
        render(
            """
            %param x
            """
        )


def test_param_default() -> None:
    template = """
        %param: "x" 1
        {x + 1}
    """
    assert render(template) == "2"
    assert render(template, x=2) == "3"


def test_inline() -> None:
    received = render(
        """
        class {camel_case(name)}:
            !for name in fields:
                %inline
                    {name} = Field(
                        !if a != name:
                            a=1, 
                        !if b != name:
                            b=2, 
                        %strip ,
                    )
        """,
        name="my_model",
        fields=["x", "y", "z"],
        a="x",
        b="y",
    )
    expected = trim(
        """
        class MyModel:
            x = Field(b=2)
            y = Field(a=1)
            z = Field(a=1, b=2)
        """
    )
    assert received == expected


def test_assign(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "result.txt"
    assert not render(
        """
        %assign x
            !for i in range(n):
                line {i}
        !p.write_text(x)
        """,
        n=3,
        p=path,
    )

    received = path.read_text()
    expected = trim(
        """
        line 0
        line 1
        line 2
        """
    )
    assert received == expected


def test_bookmark() -> None:
    received = render(
        """
        %bookmark x
        line 4
        %append x
            line 1
            line 2
        line 5
        %append x
            line 3
        """
    )
    expected = trim(
        """
        line 1
        line 2
        line 3
        line 4
        line 5
        """
    )
    assert received == expected


def test_bookmark_indent() -> None:
    received = render(
        """
        line 1
            %bookmark foo
        line 5
            %append foo
                line 2
        line 6
        %append foo
            line 3
                line 4
        """
    )
    expected = trim(
        """
        line 1
            line 2
            line 3
                line 4
        line 5
        line 6
        """
    )
    assert received == expected


def test_bookmark_missing() -> None:
    line_number = this_line(+11)
    with pytest.raises(
        ValueError,
        match=rf"missing bookmark 'y' referenced on line 5 at {THIS_FILE.name}:{line_number} \(available bookmarks are x\)",
    ):
        render(
            """
            line 1
            %bookmark x
            %append x
                line 2
            %append y
                line 3
            """
        )


def test_invalid_meta_function() -> None:
    line_number = this_line(+6)
    with pytest.raises(
        ValueError,
        match=rf"expected meta function on line 1 at {THIS_FILE.name}:{line_number + 1} to be '<function> \[argument\]', '<function>: <arguments>' or '<function>:: <invocation>', but got 'include\(1, 2\)'",
    ):
        transpile(
            """
            %include(1, 2)
            """
        )
    line_number = this_line(+7)
    with pytest.raises(
        ValueError,
        match=rf"unknown meta function 'hello' on line 1 at {THIS_FILE.name}:{line_number} \(available meta functions are .*\)",
    ):
        transpile(
            """
            %hello
            """
        )


def test_load_absolute_path(tmp_path: pathlib.Path) -> None:
    hello_code = trim(
        """
        def meta_hello(junk, name):
            junk.emit_text(0, f"hello {name}")
        """
    )
    hello_path = tmp_path / "hello.py"
    hello_path.write_text(hello_code)
    for path in [hello_path, str(hello_path)]:
        received = render(
            """
            %hello world
            """,
            load=path,
        )
        expected = "hello world"
        assert received == expected


def test_load_relative_path(tmp_path: pathlib.Path) -> None:
    template_path = tmp_path / "template.txt"
    template_code = trim(
        """
        %hello world
        """
    )
    template_path.write_text(template_code)
    hello_code = trim(
        """
        def meta_hello(junk, name):
            junk.emit_text(0, f"hello {name}")
        """
    )
    hello_path = tmp_path / "hello.py"
    hello_path.write_text(hello_code)
    for path in [pathlib.Path(hello_path.name), hello_path.name]:
        received = render(template_path, load=path)
        expected = "hello world"
        assert received == expected


def test_load_builtin_module(tmp_path: pathlib.Path) -> None:
    hello_path = tmp_path / "hello.py"
    hello_code = trim(
        """
        def meta_hello(junk, name):
            junk.emit_text(0, f"hello {name}")
        """
    )
    hello_path.write_text(hello_code)
    try:
        Junk.builtins_directories.append(tmp_path)
        received = render(
            """
            %hello world
            """,
            load="hello",
        )
        expected = "hello world"
        assert received == expected
    finally:
        Junk.builtins_directories.pop()


def test_load_dictionary() -> None:
    def meta_hello(junk, name):
        junk.emit_text(0, f"hello {name}")

    received = render(
        """
        %hello world
        """,
        load={"meta_hello": meta_hello},
    )
    expected = "hello world"
    assert received == expected


def test_load_list(tmp_path: pathlib.Path) -> None:
    foo_code = trim(
        """
        def meta_foo(junk):
            junk.emit_text(0, "foo")
        """
    )
    foo_path = tmp_path / "foo.py"
    foo_path.write_text(foo_code)

    def meta_bar(junk):
        junk.emit_text(0, "bar")

    received = render(
        """
        %foo
        %bar
        """,
        load=[foo_path, {"meta_bar": meta_bar}],
    )
    expected = "foo\nbar"
    assert received == expected


def test_load_with_import(tmp_path: pathlib.Path) -> None:
    say_hello_code = trim(
        """
        def say_hello(name):
            return f"hello {name}"
        """
    )
    say_hello_path = tmp_path / "say_hello.py"
    say_hello_path.write_text(say_hello_code)

    hello_code = trim(
        """
        from say_hello import say_hello
        def meta_hello(junk, name):
            junk.emit_text(0, say_hello(name))
        """
    )
    hello_path = tmp_path / "hello.py"
    hello_path.write_text(hello_code)

    received = render(
        """
        %hello world
        """,
        load=hello_path,
    )
    expected = "hello world"
    assert received == expected


def test_load_error() -> None:
    with pytest.raises(
        ValueError,
        match=r"could not load 'hello.py' \(.*?hello.py does not exist, and available builtins are common and filesystem\)",
    ):
        render(
            """
            !for i in range(n):
                line {i}
            """,
            load="hello.py",
        )


def test_on_load() -> None:
    pass  # TODO
