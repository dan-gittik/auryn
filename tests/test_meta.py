# flake8: noqa: W291

import pathlib

import pytest

from auryn import render

from .conftest import trim, this_line

THIS_FILE = pathlib.Path(__file__)


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


def test_interpolationtrim() -> None:
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


def test_insert() -> None:
    received = render(
        """
        %define one
            line 1
        %define('two')
            line 2
        %insert two
        %insert('one')
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
            %insert('block', required=True)
            """
        )

    received = render(
        """
        %define block
            inserted line
        %insert('block', required=True)
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
            %insert('body', required=True)
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


def test_inline() -> None:
    received = render(
        """
        class Model:
            !for name in names:
                %inline
                    {name} = Field(
                        !if a != name:
                            a=1, 
                        !if b != name:
                            b=2, 
                        %strip ,
                    )
        """,
        names=["x", "y", "z"],
        a="x",
        b="y",
    )
    expected = trim(
        """
        class Model:
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


def test_bookmark():
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


def test_bookmark_indent():
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