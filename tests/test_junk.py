# flake8: noqa: W293

import inspect
import pathlib

from auryn import Junk

from .conftest import this_line

THIS_FILE = pathlib.Path(__file__)


def test_junk_from_string() -> None:
    line_number = this_line(+1)
    junk = Junk(
        """
        !for i in range(n):
            line {i}
        """
    )
    assert junk.path == THIS_FILE
    assert junk.source_path == THIS_FILE
    assert junk.source_line == line_number
    assert junk.source == f"{THIS_FILE.name}:{line_number}"
    assert str(junk) == f"junk at {THIS_FILE.name}:{line_number}"
    assert repr(junk) == f"<junk at {THIS_FILE.name}:{line_number}>"


def test_junk_from_file(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "test.template"
    path.write_text("!for i in range(n):\n .   line {i}")
    for path_ in [path, str(path)]:
        line_number = this_line(+1)
        junk = Junk(path_)
        assert junk.path == path
        assert junk.source_path == THIS_FILE
        assert junk.source_line == line_number
        assert junk.source == f"{THIS_FILE.name}:{line_number}"
        assert str(junk) == f"junk of {path} at {THIS_FILE.name}:{line_number}"
        assert repr(junk) == f"<junk of {path} at {THIS_FILE.name}:{line_number}>"