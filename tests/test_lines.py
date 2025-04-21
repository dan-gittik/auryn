import inspect
import pathlib

import pytest

from auryn import Lines

from .conftest import this_line

THIS_FILE = pathlib.Path(__file__)


def flatten(lines: Lines) -> list[tuple[int, str]]:
    flat_lines: list[tuple[int, str]] = []
    for line in lines:
        flat_lines.append((line.indent, line.content))
        flat_lines.extend(flatten(line.children))
    return flat_lines


def test_lines_empty() -> None:
    line_number = this_line(+1)
    lines = Lines()
    assert lines.source_path == THIS_FILE
    assert lines.source_line == line_number
    assert lines.parent is None
    assert lines.path is None
    assert lines.lines == []
    assert lines.source == f"{THIS_FILE.name}:{line_number}"
    assert str(lines) == f"{THIS_FILE.name}:{line_number}"
    assert repr(lines) == f"<{THIS_FILE.name}:{line_number}>"
    assert not lines
    assert len(lines) == 0
    assert list(lines) == []


def test_lines_from_string() -> None:
    line_number = this_line(+1)
    lines = Lines(
        """
        a
            b
                c
        d
            e
            f
        """
    )
    assert lines.parent is None
    assert lines.path is None
    assert lines.source_path == THIS_FILE
    assert lines.source_line == line_number
    assert lines.source == f"{THIS_FILE.name}:{line_number}"
    assert flatten(lines.lines) == [
        (0, "a"),
        (4, "b"),
        (8, "c"),
        (0, "d"),
        (4, "e"),
        (4, "f"),
    ]
    assert str(lines) == f"{THIS_FILE.name}:{line_number}"
    assert repr(lines) == f"<{THIS_FILE.name}:{line_number}>"
    assert lines
    assert len(lines) == 2
    assert flatten(lines) == [
        (0, "a"),
        (4, "b"),
        (8, "c"),
        (0, "d"),
        (4, "e"),
        (4, "f"),
    ]
    assert lines[0].content == "a"
    assert lines[1].content == "d"


def test_lines_from_path(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "lines.txt"
    path.write_text(
        """
        a
            b
                c
        d
            e
            f
        """
    )
    line_number = this_line(+1)
    lines = Lines(path)
    assert lines.parent is None
    assert lines.path == path
    assert lines.source_path == THIS_FILE
    assert lines.source_line == line_number
    assert lines.source == f"{THIS_FILE.name}:{line_number}"
    assert flatten(lines.lines) == [
        (0, "a"),
        (4, "b"),
        (8, "c"),
        (0, "d"),
        (4, "e"),
        (4, "f"),
    ]
    assert str(lines) == f"{path.name} at {THIS_FILE.name}:{line_number}"
    assert repr(lines) == f"<{path.name} at {THIS_FILE.name}:{line_number}>"
    assert lines
    assert len(lines) == 2
    assert flatten(lines) == [
        (0, "a"),
        (4, "b"),
        (8, "c"),
        (0, "d"),
        (4, "e"),
        (4, "f"),
    ]
    assert lines[0].content == "a"
    assert lines[1].content == "d"


def test_snap() -> None:
    lines = Lines(
        """
        a
            b
                c
        d
            e
            f
        """
    )
    assert flatten(lines) == [
        (0, "a"),
        (4, "b"),
        (8, "c"),
        (0, "d"),
        (4, "e"),
        (4, "f"),
    ]

    lines.snap(to=4)
    assert flatten(lines) == [
        (4, "a"),
        (8, "b"),
        (12, "c"),
        (4, "d"),
        (8, "e"),
        (8, "f"),
    ]

    lines.snap()
    assert flatten(lines) == [
        (0, "a"),
        (4, "b"),
        (8, "c"),
        (0, "d"),
        (4, "e"),
        (4, "f"),
    ]

    lines[0].children.snap()
    assert flatten(lines) == [
        (0, "a"),
        (0, "b"),
        (4, "c"),
        (0, "d"),
        (4, "e"),
        (4, "f"),
    ]

    lines[0].children[0].children.snap(to=2)
    assert flatten(lines) == [
        (0, "a"),
        (0, "b"),
        (2, "c"),
        (0, "d"),
        (4, "e"),
        (4, "f"),
    ]

    lines.snap(to=2)
    assert flatten(lines) == [
        (2, "a"),
        (2, "b"),
        (4, "c"),
        (2, "d"),
        (6, "e"),
        (6, "f"),
    ]

    lines[1].children.snap()
    assert flatten(lines) == [
        (2, "a"),
        (2, "b"),
        (4, "c"),
        (2, "d"),
        (2, "e"),
        (2, "f"),
    ]


def test_to_string() -> None:
    lines = Lines(
        """
        a
            b
                c
        d
            e
            f
        """
    )
    assert lines.to_string() == "a\n    b\n        c\nd\n    e\n    f"


def test_line_from_string() -> None:
    line_number = this_line(+3)
    lines = Lines(
        """
        a
            b
                c
        """
    )

    line1 = lines[0]
    assert line1.number == 1
    assert line1.indent == 0
    assert line1.content == "a"
    assert line1.container is lines
    assert line1.path is None
    assert line1.source_path == THIS_FILE
    assert line1.source_line == line_number
    assert line1.source == f"{THIS_FILE.name}:{line_number}"
    assert flatten(line1.children) == [
        (4, "b"),
        (8, "c"),
    ]
    assert str(line1) == f"line 1 at {THIS_FILE.name}:{line_number}"
    assert repr(line1) == f"<line 1 at {THIS_FILE.name}:{line_number}: 0 | a>"

    line2 = line1.children[0]
    assert line2.number == 2
    assert line2.indent == 4
    assert line2.content == "b"
    assert line2.container.parent is line1
    assert line2.path is None
    assert line2.source_path == THIS_FILE
    assert line2.source_line == line_number + 1
    assert line2.source == f"{THIS_FILE.name}:{line_number + 1}"
    assert flatten(line2.children) == [
        (8, "c"),
    ]
    assert str(line2) == f"line 2 at {THIS_FILE.name}:{line_number + 1}"
    assert repr(line2) == f"<line 2 at {THIS_FILE.name}:{line_number + 1}: 4 | b>"

    line3 = line2.children[0]
    assert line3.number == 3
    assert line3.indent == 8
    assert line3.content == "c"
    assert line3.container.parent is line2
    assert line3.path is None
    assert line3.source_path == THIS_FILE
    assert line3.source_line == line_number + 2
    assert line3.source == f"{THIS_FILE.name}:{line_number + 2}"
    assert flatten(line3.children) == []
    assert str(line3) == f"line 3 at {THIS_FILE.name}:{line_number + 2}"
    assert repr(line3) == f"<line 3 at {THIS_FILE.name}:{line_number + 2}: 8 | c>"


def test_line_from_path(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "lines.txt"
    path.write_text("a\n    b\n        c")
    line_number = this_line(+1)
    lines = Lines(path)

    line1 = lines[0]
    assert line1.number == 1
    assert line1.indent == 0
    assert line1.content == "a"
    assert line1.container is lines
    assert line1.path == path
    assert line1.source_path == THIS_FILE
    assert line1.source_line == line_number
    assert line1.source == f"{THIS_FILE.name}:{line_number}"
    assert flatten(line1.children) == [
        (4, "b"),
        (8, "c"),
    ]
    assert str(line1) == f"line 1 of {path.name} at {THIS_FILE.name}:{line_number}"
    assert repr(line1) == f"<line 1 of {path.name} at {THIS_FILE.name}:{line_number}: 0 | a>"

    line2 = line1.children[0]
    assert line2.number == 2
    assert line2.indent == 4
    assert line2.content == "b"
    assert line2.container.parent is line1
    assert line2.path == path
    assert line2.source_path == THIS_FILE
    assert line2.source_line == line_number
    assert line2.source == f"{THIS_FILE.name}:{line_number}"
    assert flatten(line2.children) == [
        (8, "c"),
    ]
    assert str(line2) == f"line 2 of {path.name} at {THIS_FILE.name}:{line_number}"
    assert repr(line2) == f"<line 2 of {path.name} at {THIS_FILE.name}:{line_number}: 4 | b>"

    line3 = line2.children[0]
    assert line3.number == 3
    assert line3.indent == 8
    assert line3.content == "c"
    assert line3.container.parent is line2
    assert line3.path == path
    assert line3.source_path == THIS_FILE
    assert line3.source_line == line_number
    assert line3.source == f"{THIS_FILE.name}:{line_number}"
    assert flatten(line3.children) == []
    assert str(line3) == f"line 3 of {path.name} at {THIS_FILE.name}:{line_number}"
    assert repr(line3) == f"<line 3 of {path.name} at {THIS_FILE.name}:{line_number}: 8 | c>"


def test_set_source() -> None:
    line_number = this_line(+1)
    lines = Lines(
        """
        a
        %include test.txt
        """
    )
    other_file = THIS_FILE.parent / "test.txt"
    assert lines.source_path == THIS_FILE
    assert lines.source_line == line_number
    assert lines[0].children.source_path == THIS_FILE
    assert lines[0].children.source_line == line_number
    lines.set_source(other_file, line_number + 3)
    assert lines.source_path == other_file
    assert lines.source_line == line_number + 3
    assert lines[0].children.source_path == other_file
    assert lines[0].children.source_line == line_number + 3


def test_no_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(inspect, "currentframe", lambda: None)
    with pytest.raises(RuntimeError, match="unable to infer source"):
        Lines()
    


def test_no_source() -> None:
    lines = Lines("a\n")
    line = lines[0]

    line.container = None
    with pytest.raises(RuntimeError, match="source path not set"):
        line.source_path
    with pytest.raises(RuntimeError, match="source line not set"):
        line.source_line

    lines._source_path = None
    with pytest.raises(RuntimeError, match="source path not set"):
        lines.source_path

    lines._source_line = None
    with pytest.raises(RuntimeError, match="source line not set"):
        lines.source_line