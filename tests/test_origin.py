import pathlib

import pytest

from auryn import GX, Origin

from .conftest import this_line

THIS_FILE = pathlib.Path(__file__)


def test_infer_origin() -> None:
    line_number = this_line(+1)
    origin = Origin.infer(0)
    assert origin.path == THIS_FILE
    assert origin.line_number == line_number
    assert origin.gx is None
    assert str(origin) == f"{THIS_FILE}:{line_number}"
    assert repr(origin) == f"<{THIS_FILE}:{line_number}>"


def test_infer_origin_stack_level() -> None:
    def f() -> Origin:
        return g()

    def g() -> Origin:
        return Origin.infer(2)

    line_number = this_line(+1)
    origin = f()
    assert origin.path == THIS_FILE
    assert origin.line_number == line_number
    assert origin.gx is None
    assert str(origin) == f"{THIS_FILE}:{line_number}"
    assert repr(origin) == f"<{THIS_FILE}:{line_number}>"


def test_infer_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("inspect.currentframe", lambda: None)
    with pytest.raises(RuntimeError, match="unable to infer origin"):
        Origin.infer(0)


def test_derive_origin_from_string() -> None:
    origin: Origin | None = None

    def g_derive(gx: GX) -> None:
        nonlocal origin
        derived_gx = gx.derive(
            """
            hello world
            """
        )
        origin = derived_gx.origin

    line_number = this_line(+3)
    gx = GX.parse(
        """
        line 1
        %derive
        """
    )
    gx.load({"g_derive": g_derive})
    assert origin is None
    gx.generate()
    assert origin is not None
    assert origin.path == THIS_FILE
    assert origin.line_number == line_number
    assert origin.gx is gx
    assert str(origin) == f"{THIS_FILE}:{line_number}"
    assert repr(origin) == f"<{THIS_FILE}:{line_number}>"


def test_derive_origin_from_file(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "template"
    path.write_text("line 1\n%derive")
    origin: Origin | None = None

    def g_derive(gx: GX) -> None:
        nonlocal origin
        derived_gx = gx.derive(path)
        origin = derived_gx.origin

    gx = GX.parse(path)
    gx.load({"g_derive": g_derive})
    assert origin is None
    gx.generate()
    assert origin is not None
    assert origin.path == path
    assert origin.line_number == 2
    assert origin.gx is gx
    assert str(origin) == f"{path}:2"
    assert repr(origin) == f"<{path}:2>"
