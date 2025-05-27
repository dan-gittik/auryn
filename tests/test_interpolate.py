import re

import pytest

from auryn import interpolate, split


def test_interpolate():
    received = interpolate("{x} + {y} = {x + y}", "{ }")
    expected = [
        ("x", True),
        (" + ", False),
        ("y", True),
        (" = ", False),
        ("x + y", True),
    ]
    assert list(received) == expected

    received = interpolate("<% x %> + <% y %> = <% x + y %>", "<% %>")
    expected = [
        ("x", True),
        (" + ", False),
        ("y", True),
        (" = ", False),
        ("x + y", True),
    ]
    assert list(received) == expected


def test_interpolate_nested_delimiters():
    received = interpolate("{ {'x': 1, 'y': 2}['x'] } == 1", "{ }")
    expected = [
        ("{'x': 1, 'y': 2}['x']", True),
        (" == 1", False),
    ]
    assert list(received) == expected


def test_interpolate_nested_delimiters_in_string():
    received = interpolate("{ {'{': 1}.get('}') } is None", "{ }")
    expected = [
        ("{'{': 1}.get('}')", True),
        (" is None", False),
    ]
    assert list(received) == expected


def test_interpolate_escaping_in_string():
    received = interpolate(r"""{ {'\'{'}.get("\"{") } is None""", "{ }")
    expected = [
        ("{'\\'{'}.get(\"\\\"{\")", True),
        (" is None", False),
    ]
    assert list(received) == expected


def test_interpolate_edge_cases():
    for text in ["", "{", "}", "a"]:
        received = interpolate(text, "{ }")
        assert list(received) == [(text, False)]


def test_interpolate_escape():
    received = interpolate("{{x}}", "{ }")
    expected = [("{x}", False)]
    assert list(received) == expected

    received = interpolate("{{", "{ }")
    expected = [("{", False)]
    assert list(received) == expected

    received = interpolate("}}", "{ }")
    expected = [("}", False)]
    assert list(received) == expected

    received = interpolate("{{{x}}}", "{ }")
    expected = [("{", False), ("x", True), ("}", False)]
    assert list(received) == expected

    received = interpolate("{{{{x}}}}", "{ }")
    expected = [("{{x}}", False)]
    assert list(received) == expected


def test_interpolate_invalid_delimiters():
    for delimiters in ["<%", "{}", "<% %> <%>"]:
        with pytest.raises(
            ValueError,
            match=rf"invalid delimiters: {delimiters!r} \(expected a space-separated pair\)",
        ):
            received = interpolate("", delimiters)
            list(received)

    for delimiters in ["{ ", " }", "| |"]:
        with pytest.raises(
            ValueError,
            match=rf"invalid delimiters: {delimiters!r} \(delimiters must be non-empty and distinct\)",
        ):
            received = interpolate("", delimiters)
            list(received)


def test_interpolate_unmatched_start_delimiter():
    for text, delimiters in [
        ("{x} + {y} = {x + y", "{ }"),
        ("<% x %> + <% y %> = <% x + y", "<% %>"),
    ]:
        start, _ = delimiters.split(" ")
        offset = text.rfind(start)
        with pytest.raises(
            ValueError,
            match=re.escape(f"unable to interpolate {text!r}: unmatched {start!r} at offset {offset}"),
        ):
            received = interpolate(text, delimiters)
            list(received)


def test_interpolate_unmatched_end_delimiter():
    for text, delimiters in [
        ("{x} + {y} = x + y}", "{ }"),
        ("<% x %> + <% y %> = x + y %>", "<% %>"),
    ]:
        _, end = delimiters.split(" ")
        offset = text.rfind(end)
        with pytest.raises(
            ValueError,
            match=re.escape(f"unable to interpolate {text!r}: unmatched {end!r} at offset {offset}"),
        ):
            received = interpolate(text, delimiters)
            list(received)


def test_interpolate_unterminated_string():
    for text in ["{'hello}", '{"hello}']:
        with pytest.raises(
            ValueError,
            match=re.escape(f"unable to interpolate {text!r}: unterminated quote at offset 1"),
        ):
            received = interpolate(text, "{ }")
            list(received)


def test_split():
    received = split("")
    expected = []
    assert list(received) == expected

    received = split("flag")
    expected = ["flag"]
    assert list(received) == expected

    received = split("flag key=value")
    expected = ["flag", "key=value"]
    assert list(received) == expected

    received = split("flag key=value key='quoted value'")
    expected = ["flag", "key=value", "key='quoted value'"]
    assert list(received) == expected

    received = split('flag key=value key="quoted value"')
    expected = ["flag", "key=value", 'key="quoted value"']
    assert list(received) == expected
