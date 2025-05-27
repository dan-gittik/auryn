import pathlib

import pytest

from auryn import ExecutionError, GenerationError, execute, generate

from .conftest import this_line, trim

THIS_FILE = pathlib.Path(__file__)


def test_eval() -> None:
    received = execute(
        """
        %eval x = {a}
        {x}
        """,
        g_a=1,
    )
    expected = "1"
    assert received == expected


def test_eval_code() -> None:
    received = generate(
        """
        %!for i in range(n):
            %eval x = {i}
        """,
        n=3,
    )
    expected = trim(
        """
        x = 0
        x = 1
        x = 2
        """
    )
    assert received == expected


def test_emit() -> None:
    received = execute(
        """
        %!for i in range(n):
            %emit line {i}
        """,
        g_n=3,
    )
    expected = trim(
        """
        line 0
        line 1
        line 2
        """
    )
    assert received == expected


def test_emit_escaping() -> None:
    received = execute(
        """
        %emit {a} == {{x}}
        """,
        g_a=1,
        x=1,
    )
    expected = "1 == 1"
    assert received == expected


def test_s(capsys: pytest.CaptureFixture[str]) -> None:
    received = execute(
        """
        %!
            def print(gx, message):
                gx.add_code(f'print({gx.interpolated(message)})')
        %print hello {name}
        """,
        name="world",
    )
    assert received == ""
    assert capsys.readouterr().out == "hello world\n"


def test_include(tmp_path: pathlib.Path) -> None:
    loop_text = trim(
        """
        !for i in range(n):
            line {i}
        """
    )
    loop_path = tmp_path / "loop.aur"
    loop_path.write_text(loop_text)

    # We use a file so loop.template is resolved relatively to main.template.
    main_text = trim(
        """
        !n = 3
        %include loop.aur
        """
    )
    main_path = tmp_path / "main.aur"
    main_path.write_text(main_text)

    received = execute(main_path)
    expected = trim(
        """
        line 0
        line 1
        line 2
        """
    )
    assert received == expected

    received = execute(
        """
        !n = 3
        %include {path}
        """,
        g_path=loop_path,
    )
    assert received == expected


def test_include_with_load(tmp_path: pathlib.Path) -> None:
    plugin_path = tmp_path / "plugin.py"
    plugin_code = trim(
        """
        def on_load(gx):
            gx.line_transform(transform_text)

        def transform_text(gx, content):
            if content:
                return gx.add_text(gx.line.indent, f"<p>{content}</p>")
            gx.transform()
        """
    )
    plugin_path.write_text(plugin_code)

    template = trim(
        """
        !for i in range(n):
            line {i}
        """
    )

    received = execute(
        """
        %include: template load=plugin
        """,
        g_template=template,
        g_plugin=plugin_path,
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


def test_include_with_continue_generation(tmp_path: pathlib.Path) -> None:
    plugin_path = tmp_path / "plugin.py"
    plugin_code = trim(
        """
        def g_hello(gx, name):
            gx.add_text(0, f"hello {name}")
        """
    )
    plugin_path.write_text(plugin_code)

    include_text = """
        %hello inside
    """

    with pytest.raises(
        GenerationError,
        match=r"Failed to generate GX at .*?: unknown macro 'hello' on line 1 \(available macros are .*?\).",  # noqa: E501 (line too long)
    ):
        execute(
            """
            %hello outside
            %include: text
            """,
            g_text=include_text,
            load=plugin_path,
        )

    received = execute(
        """
        %hello outside
        %include: text continue_generation=True
        """,
        g_text=include_text,
        load=plugin_path,
    )
    expected = trim(
        """
        hello outside
        hello inside
        """
    )
    assert received == expected


def test_include_string_without_execution() -> None:
    include_text = trim(
        """
        !for i in range(n):
            line {i}
        """
    )

    received = execute(
        """
        %include: text
        """,
        g_text=include_text,
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

    received = execute(
        """
        %include: text generate=False
        """,
        g_text=include_text,
        i=0,
    )
    expected = trim(
        """
        !for i in range(n):
            line 0
        """
    )
    assert received == expected

    received = execute(
        """
        %include: text generate=False interpolate=False
        """,
        g_text=include_text,
    )
    expected = trim(
        """
        !for i in range(n):
            line {i}
        """
    )
    assert received == expected


def test_include_file_without_execution(tmp_path: pathlib.Path) -> None:
    include_path = tmp_path / "template.aur"
    include_text = trim(
        """
        !for i in range(n):
            line {i}
        """
    )
    include_path.write_text(include_text)

    received = execute(
        """
        %include: path
        """,
        g_path=include_path,
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

    received = execute(
        """
        %include: path generate=False
        """,
        g_path=include_path,
        i=0,
    )
    expected = trim(
        """
        !for i in range(n):
            line 0
        """
    )
    assert received == expected

    received = execute(
        """
        %include: path generate=False interpolate=False
        """,
        g_path=include_path,
    )
    expected = trim(
        """
        !for i in range(n):
            line {i}
        """
    )
    assert received == expected


def test_include_with_children() -> None:
    line_number = this_line(+5)
    with pytest.raises(
        GenerationError,
        match=rf"Failed to generate GX at {THIS_FILE}:{line_number}: %include macro must not have children.",
    ):
        execute(
            """
            %include template.aur
                line 1
            """,
        )


def test_ifdef() -> None:
    received = execute(
        """
        %define x
            hello
        %ifdef x
            %insert x
        %ifdef y
            %insert y
        """
    )
    expected = trim(
        """
        hello
        """
    )
    assert received == expected


def test_ifdef_without_children() -> None:
    line_number = this_line(+5)
    with pytest.raises(
        GenerationError,
        match=rf"Failed to generate GX at {THIS_FILE}:{line_number}: %ifdef macro must have children.",
    ):
        execute(
            """
            %ifdef x
            """,
        )


def test_ifndef() -> None:
    received = execute(
        """
        %define x
            hello
        %ifndef x
            no x
        %ifndef y
            no y
        """
    )
    expected = trim(
        """
        no y
        """
    )
    assert received == expected


def test_ifndef_without_children() -> None:
    line_number = this_line(+5)
    with pytest.raises(
        GenerationError,
        match=rf"Failed to generate GX at {THIS_FILE}:{line_number}: %ifndef macro must have children.",
    ):
        execute(
            """
            %ifndef x
            """,
        )


def test_insert() -> None:
    received = execute(
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
    received = execute(
        """
        %insert block
            default line
        """
    )
    expected = "default line"
    assert received == expected

    line_number = this_line(+5)
    with pytest.raises(
        GenerationError,
        match=rf"Failed to generate GX at {THIS_FILE}:{line_number}: missing required definition 'block' on line 3 \(available definitions are a and b\).",  # noqa: E501 (line too long)
    ):
        execute(
            """
            %define a
            %define b
            %insert: "block" required=True
            """
        )

    received = execute(
        """
        %define block
            inserted line
        %insert:: "block", required=True
        """
    )
    expected = "inserted line"
    assert received == expected


def test_required_insert_with_children() -> None:
    line_number = this_line(+5)
    with pytest.raises(
        GenerationError,
        match=rf"Failed to generate GX at {THIS_FILE}:{line_number}: %insert macro must not have children when required=True.",  # noqa: E501 (line too long)
    ):
        execute(
            """
            %insert: "block" required=True
                line 1
            """,
        )


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
    base_path = tmp_path / "base.aur"
    base_path.write_text(base)

    main = trim(
        """
        %extend base.aur
        %define head
            <title>inserted title</title>
        %define body
            <p>inserted body</p>
        """
    )
    main_path = tmp_path / "main.aur"
    main_path.write_text(main)

    received = execute(main_path)
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
        %extend base.aur
        %define body
            <p>inserted body</p>
        """
    )
    body_path = tmp_path / "body.aur"
    body_path.write_text(body)

    received = execute(body_path)
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
        %extend base.aur
        %define head
            <title>inserted title</title>
        """
    )
    head_path = tmp_path / "aur.template"
    head_path.write_text(head)
    with pytest.raises(
        GenerationError,
        match=rf"Failed to generate GX of {base_path} at {head_path}:1: missing required definition 'body' on line 6 \(available definitions are head\).",  # noqa: E501 (line too long)
    ):
        execute(head_path)


def test_extend_block(tmp_path: pathlib.Path) -> None:
    base = trim(
        """
        %insert block
        """
    )
    base_path = tmp_path / "base.aur"
    base_path.write_text(base)

    main = trim(
        """
        missing line
        %extend base.aur
        %define block
            extended line
        missing line
        """
    )
    main_path = tmp_path / "main.aur"
    main_path.write_text(main)

    received = execute(main_path)
    expected = "extended line"
    assert expected == received

    main = trim(
        """
        first line
        %extend base.aur
            %define block
                extended line
        last line
        """
    )
    main_path = tmp_path / "main.aur"
    main_path.write_text(main)

    received = execute(main_path)
    expected = trim(
        """
        first line
        extended line
        last line
        """
    )
    assert expected == received


def test_interpolate() -> None:
    received = execute(
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

    received = execute(
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
    received = execute(
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
    received = execute(
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


def test_raw() -> None:
    received = execute(
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
    received = execute(
        """
        before
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
        before
            !for i in range(n):
                line {i}
            %command
        line 0
        line 1
        line 2
        """
    )
    assert received == expected


def test_stop() -> None:
    received = execute(
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
        ExecutionError,
        match=rf"Failed to execute GX at {THIS_FILE}:{line_number}: missing required parameter 'x'.",
    ):
        execute(
            """
            %param x
            """
        )


def test_param_default() -> None:
    template = """
        %param: "x" 1
        {x + 1}
    """
    assert execute(template) == "2"
    assert execute(template, x=2) == "3"


def test_param_with_children() -> None:
    line_number = this_line(+5)
    with pytest.raises(
        GenerationError,
        match=rf"Failed to generate GX at {THIS_FILE}:{line_number}: %param macro must not have children.",
    ):
        execute(
            """
            %param x
                line 1
            """,
        )


def test_inline() -> None:
    received = execute(
        """
        %inline
        f(
        !for arg in args:
            {arg}, 
        4)
        """,  # noqa: W291 (trailing whitespace)
        args=[1, 2, 3],
    )
    expected = "f(1, 2, 3, 4)"
    assert received == expected


def test_inline_block() -> None:
    received = execute(
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
        """,  # noqa: W291 (trailing whitespace)
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


def test_strip_no_output() -> None:
    received = execute(
        """
        %strip x
        content
        %strip x
        """
    )
    expected = "content"
    assert received == expected


def test_assign(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "templa.txt"
    assert not execute(
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


def test_assign_without_children() -> None:
    line_number = this_line(+5)
    with pytest.raises(
        GenerationError,
        match=rf"Failed to generate GX at {THIS_FILE}:{line_number}: %assign macro must have children.",
    ):
        execute(
            """
            %assign x
            """,
        )


def test_bookmark() -> None:
    received = execute(
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
    received = execute(
        """
        line 1
            %bookmark x
                line 2
        line 6
            %append x
                line 3
        line 7
        %append x
            line 4
                line 5
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
        line 7
        """
    )
    assert received == expected


def test_bookmark_missing() -> None:
    line_number = this_line(+5)
    with pytest.raises(
        ExecutionError,
        match=rf"Failed to execute GX at {THIS_FILE}:{line_number}: missing bookmark 'y' referenced on line 5 \(available bookmarks are x\).",  # noqa: E501 (line too long)
    ):
        execute(
            """
            line 1
            %bookmark x
            %append x
                line 2
            %append y
                line 3
            """
        )


def test_append_without_children() -> None:
    line_number = this_line(+5)
    with pytest.raises(
        GenerationError,
        match=rf"Failed to generate GX at {THIS_FILE}:{line_number}: %append macro must have children.",
    ):
        execute(
            """
            %append x
            """,
        )
