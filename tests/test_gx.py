import pathlib

import pytest

from auryn import GX, Line, generate

from .conftest import this_line

THIS_FILE = pathlib.Path(__file__)


def test_gx_from_string() -> None:
    line_number = this_line(+1)
    gx = GX.parse(
        """
        !for i in range(n):
            line {i}
        """
    )
    assert gx.origin.path == THIS_FILE
    assert gx.origin.line_number == line_number
    assert gx.template.path is None
    assert str(gx) == f"GX at {THIS_FILE}:{line_number}"
    assert repr(gx) == f"<GX at {THIS_FILE}:{line_number}>"


def test_gx_from_file(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "template.aur"
    path.write_text("!for i in range(n):\n     line {i}")
    for path_ in [path, str(path)]:
        line_number = this_line(+1)
        gx = GX.parse(path_)
        assert gx.origin.path == THIS_FILE
        assert gx.origin.line_number == line_number
        assert gx.template.path == path
        assert str(gx) == f"GX of {path} at {THIS_FILE}:{line_number}"
        assert repr(gx) == f"<GX of {path} at {THIS_FILE}:{line_number}>"


def test_derived_gx_from_string() -> None:
    derived_gx: GX | None = None

    def g_derive(gx: GX) -> None:
        nonlocal derived_gx
        derived_gx = gx.derive(
            """
            hello world
            """
        )

    line_number = this_line(+2)
    gx = GX.parse(
        """
        %derive
        """
    )
    gx.load({"g_derive": g_derive})
    gx.generate()
    assert derived_gx is not None
    assert derived_gx.origin.path == THIS_FILE
    assert derived_gx.origin.line_number == line_number
    assert derived_gx.origin.gx is gx


def test_derived_gx_from_file(tmp_path: pathlib.Path) -> None:
    derived_gx: GX | None = None

    def g_derive(gx: GX) -> None:
        nonlocal derived_gx
        derived_gx = gx.derive(
            """
            hello world
            """
        )

    template_path = tmp_path / "template.aur"
    template_path.write_text("%derive")

    gx = GX.parse(template_path)
    gx.load({"g_derive": g_derive})
    gx.generate()
    assert derived_gx is not None
    assert derived_gx.origin.path == template_path
    assert derived_gx.origin.line_number == 1
    assert derived_gx.origin.gx is gx


def test_line() -> None:
    lines: list[Line] = []

    def g_line(gx: GX) -> None:
        lines.append(gx.line)

    generate(
        """
        %line
        %line
        """,
        load={"g_line": g_line},
    )
    assert len(lines) == 2
    assert lines[0].number == 1
    assert lines[1].number == 2


def test_no_line() -> None:
    gx = GX.parse(
        """
        %line
        """
    )
    with pytest.raises(RuntimeError, match=f"{gx} is not in generation"):
        gx.line


def test_generation_evaluation() -> None:
    gx = GX.parse(
        """
        hello world
        """,
    )
    gx.g_locals.update(x=1, y=2)
    assert gx.g_interpolate("{x} + {y} = {x + y}") == "1 + 2 = 3"
    assert gx.g_eval("x + y") == 3
    assert "z" not in gx.g_locals
    gx.g_exec("z = x + y")
    assert gx.g_locals["z"] == 3


def test_execution_evaluation() -> None:
    gx = GX.parse(
        """
        !x = 1
        !y = 2
        """,
    )
    gx.generate()
    gx.execute()
    assert gx.x_interpolate("{x} + {y} = {x + y}") == "1 + 2 = 3"
    assert gx.x_eval("x + y") == 3
    assert "z" not in gx.x_globals
    gx.x_exec("z = x + y")
    assert gx.x_globals["z"] == 3
