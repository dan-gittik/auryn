import pathlib

from auryn import GX, Lines, Template


def test_template_from_string() -> None:
    template = Template.parse(
        """
        a
            b
            c
        d
        """
    )
    assert str(template) == "template"
    assert repr(template) == "<template: a b c d...>"
    assert template.text == (
        """
        a
            b
            c
        d
        """
    )
    assert template.path is None
    assert flatten(template.lines) == [
        (0, "a"),
        (4, "b"),
        (4, "c"),
        (0, "d"),
    ]


def test_template_from_file(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "template"
    path.write_text("a\n    b\n    c\nd")
    template = Template.parse(path)
    assert str(template) == f"template from {path}"
    assert repr(template) == f"<template from {path}: a b c d...>"
    assert template.text == "a\n    b\n    c\nd"
    assert template.path == path
    assert flatten(template.lines) == [
        (0, "a"),
        (4, "b"),
        (4, "c"),
        (0, "d"),
    ]


def test_template_from_template(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "template"
    template1 = Template("text", path, Lines())
    assert template1.text == "text"
    assert template1.path == path
    assert flatten(template1.lines) == []
    template2 = Template.parse(template1)
    assert template2 is template1

    gx = GX.parse(
        """
        !x
        """
    )
    template3 = gx.resolve_template(template1)
    assert template3 is template1


def test_empty_template() -> None:
    template = Template()
    assert str(template) == "template"
    assert repr(template) == "<template>"
    assert template.text == ""
    assert template.path is None
    assert flatten(template.lines) == []


def test_lines() -> None:
    template = Template.parse(
        """
        a
            b
                c
        d
            e
            f
        """
    )
    lines = template.lines
    assert str(lines) == "lines 1-6"
    assert repr(lines) == "<lines 1-6>"
    assert lines.parent is None
    assert lines
    assert len(lines) == 2
    assert list(lines) == [lines[0], lines[1]]
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


def test_lines_with_empty_lines() -> None:
    template = Template.parse(
        """
        a
            b
            
            c
        d

        e
        """  # noqa: W293 (blank line contains whitespace)
    )
    assert flatten(template.lines) == [
        (0, "a"),
        (4, "b"),
        (4, ""),
        (4, "c"),
        (0, "d"),
        (0, ""),
        (0, "e"),
    ]


def test_empty_lines() -> None:
    template = Template()
    lines = template.lines
    assert lines.parent is None
    assert str(lines) == "no lines"
    assert repr(lines) == "<no lines>"
    assert not lines
    assert len(lines) == 0
    assert list(lines) == []


def test_first_line_number_in_string(tmp_path: pathlib.Path) -> None:
    template = Template.parse(
        """
        a
        """
    )
    assert template.lines[0].number == 1


def test_first_line_number_in_file(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "template"
    path.write_text("a")
    template = Template.parse(path)
    assert template.lines[0].number == 1


def test_lines_append() -> None:
    template = Template()
    lines = template.lines
    assert flatten(lines) == []

    lines.append(1, 0, "a")
    assert flatten(lines) == [
        (0, "a"),
    ]

    lines.append(2, 0, "b")
    assert flatten(lines) == [
        (0, "a"),
        (0, "b"),
    ]


def test_lines_snap() -> None:
    template = Template.parse(
        """
        a
            b
                c
        d
            e
            f
        """
    )
    lines = template.lines
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


def test_lines_to_string() -> None:
    template = Template.parse(
        """
        a
            b
                c
        d
            e
            f
        """
    )
    assert template.lines.to_string() == "a\n    b\n        c\nd\n    e\n    f"


def test_line() -> None:
    template = Template.parse(
        """
        a
            b
                c
        """
    )
    lines = template.lines

    line1 = lines[0]
    assert line1.number == 1
    assert line1.indent == 0
    assert line1.content == "a"
    assert flatten(line1.children) == [
        (4, "b"),
        (8, "c"),
    ]
    assert str(line1) == "line 1"
    assert repr(line1) == "<line 1: 0 | a>"
    assert str(line1.children) == "children 2-3 of line 1"

    line2 = line1.children[0]
    assert line2.number == 2
    assert line2.indent == 4
    assert line2.content == "b"
    assert flatten(line2.children) == [
        (8, "c"),
    ]
    assert str(line2) == "line 2"
    assert repr(line2) == "<line 2: 4 | b>"
    assert str(line2.children) == "children 3-3 of line 2"

    line3 = line2.children[0]
    assert line3.number == 3
    assert line3.indent == 8
    assert line3.content == "c"
    assert flatten(line3.children) == []
    assert str(line3) == "line 3"
    assert repr(line3) == "<line 3: 8 | c>"


def flatten(lines: Lines) -> list[tuple[int, str]]:
    flat_lines: list[tuple[int, str]] = []
    for line in lines:
        flat_lines.append((line.indent, line.content))
        flat_lines.extend(flatten(line.children))
    return flat_lines
