import re

import pytest

from auryn.interpolate import interpolate, parse_arguments


def test_interpolate():
    assert list(interpolate("{x} + {y} = {x + y}")) == [
        ("x", True),
        (" + ", False),
        ("y", True),
        (" = ", False),
        ("x + y", True),
    ]
    assert list(interpolate("<% x %> + <% y %> = <% x + y %>", "<% %>")) == [
        ("x", True),
        (" + ", False),
        ("y", True),
        (" = ", False),
        ("x + y", True),
    ]


def test_interpolate_nested():
    assert list(interpolate("{ {'x': 1, 'y': 2}['x'] } == 1")) == [
        ("{'x': 1, 'y': 2}['x']", True),
        (" == 1", False),
    ]


def test_interpolate_delimiter_in_string():
    assert list(interpolate("{ {'{': 1}.get('}') } is None")) == [
        ("{'{': 1}.get('}')", True),
        (" is None", False),
    ]


def test_interpolate_escaping_in_string():
    assert list(interpolate(r"""{ {'\'{'}.get("\"{") } is None""")) == [
        ("{'\\'{'}.get(\"\\\"{\")", True),
        (" is None", False),
    ]


def test_interpolate_edge_cases():
    for s in ["", "{", "}", "a"]:
        assert list(interpolate(s)) == [(s, False)]


def test_interpolate_escape():
    assert list(interpolate("{{x}}")) == [("{x}", False)]
    assert list(interpolate("{{")) == [("{", False)]
    assert list(interpolate("}}")) == [("}", False)]
    assert list(interpolate("{{{x}}}")) == [("{", False), ("x", True), ("}", False)]
    assert list(interpolate("{{{{x}}}}", "{ }")) == [("{{x}}", False)]


def test_interpolate_invalid_delimiters():
    for delimiters in ["<%", "{}", "<% %> <%>"]:
        with pytest.raises(
            ValueError,
            match=rf"invalid delimiters {delimiters!r} \(expected space-separated pair\)",
        ):
            list(interpolate("", delimiters))
    for delimiters in ["{ ", " }", "| |"]:
        with pytest.raises(
            ValueError,
            match=rf"invalid delimiters {delimiters!r} \(delimiters must be non-empty and distinct\)",
        ):
            list(interpolate("", delimiters))


def test_interpolate_unmatched_open_delimiter():
    for s, delimiters in [
        ("{x} + {y} = {x + y", "{ }"),
        ("<% x %> + <% y %> = <% x + y", "<% %>"),
    ]:
        a, _ = delimiters.split(" ")
        offset = s.rfind(a)
        with pytest.raises(
            ValueError,
            match=re.escape(f"unable to interpolate {s!r}: unmatched {a!r} at offset {offset}"),
        ):
            list(interpolate(s, delimiters))


def test_interpolate_unmatched_close_delimiter():
    for s, delimiters in [
        ("{x} + {y} = x + y}", "{ }"),
        ("<% x %> + <% y %> = x + y %>", "<% %>"),
    ]:
        _, b = delimiters.split(" ")
        offset = s.rfind(b)
        with pytest.raises(
            ValueError,
            match=re.escape(f"unable to interpolate {s!r}: unmatched {b!r} at offset {offset}"),
        ):
            list(interpolate(s, delimiters))


def test_interpolate_unterminated_string():
    for s in ["{'hello}", '{"hello}']:
        with pytest.raises(
            ValueError,
            match=re.escape(f"unable to interpolate {s!r}: unterminated quote at offset 1"),
        ):
            list(interpolate(s))


def test_parse_arguments():
    assert list(parse_arguments("")) == []
    assert list(parse_arguments("x")) == ["x"]
    assert list(parse_arguments("x y")) == ["x", "y"]
    assert list(parse_arguments("x y z")) == ["x", "y", "z"]