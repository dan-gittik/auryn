import pathlib
import re

import pytest

from auryn import GX, Error, ExecutionError, GenerationError, execute, generate

from .conftest import this_line, trim

THIS_FILE = pathlib.Path(__file__)


def test_generation_error() -> None:
    line_number = this_line(+5)
    with pytest.raises(
        GenerationError,
        match=rf"Failed to generate GX at {THIS_FILE}:{line_number}: unknown macro 'hello' on line 1 \(available macros are .*\).",  # noqa: E501 (line too long)
    ) as info:
        execute(
            """
            %hello
            """,
        )
    assert _is_main("%hello", info.value.report())


def test_execution_error() -> None:
    line_number = this_line(+5)
    with pytest.raises(
        ExecutionError,
        match=rf"Failed to execute GX at {THIS_FILE}:{line_number}: name 'n' is not defined.",
    ) as info:
        execute(
            """
            !for i in range(n):
                line {x}
            """,
        )
    assert _is_main("!for i in range(n):", info.value.report())

    line_number = this_line(+5)
    with pytest.raises(
        ExecutionError,
        match=rf"Failed to execute GX at {THIS_FILE}:{line_number}: name 'x' is not defined.",
    ) as info:
        execute(
            """
            !for i in range(n):
                line {x}
            """,
            n=3,
        )
    assert _is_main("line {x}", info.value.report())


def test_execution_error_nested(tmp_path: pathlib.Path) -> None:
    plugin_path = tmp_path / "plugin.py"
    plugin_code = trim(
        """
        def error(x):
            raise ValueError(x)

        def g_error(gx, x):
            gx.add_code(f"error({gx.interpolated(x)})")

        def x_error(gx, x):
            gx.emit(0, error(x))
        """
    )
    plugin_path.write_text(plugin_code)

    template_path = tmp_path / "template.aur"
    template_code = trim(
        """
        %error {x}
        """
    )
    template_path.write_text(template_code)

    line_number = this_line(+5)
    with pytest.raises(
        ExecutionError,
        match=rf"Failed to execute GX of {template_path} at {THIS_FILE}:{line_number}: 1.",
    ) as info:
        execute(template_path, load=plugin_path, x=1)
    assert _is_main("%error {x}", info.value.report())
    assert _is_main("raise ValueError(x)", info.value.report())
    assert _is_main("gx.emit(0, error(x))", info.value.report())


def test_execution_error_incomplete(tmp_path: pathlib.Path) -> None:
    plugin_path = tmp_path / "plugin.py"
    plugin_code = trim(
        """
        def g_error(gx, x):
            gx.add_code(f"error({gx.interpolated(x)})")

        def x_error(gx, x):
            raise ValueError(x)
        """
    )
    plugin_path.write_text(plugin_code)

    template_path = tmp_path / "template.aur"
    template_code = trim(
        """
        %error {x}
        """
    )
    template_path.write_text(template_code)

    line_number = this_line(+5)
    with pytest.raises(
        ExecutionError,
        match=rf"Failed to execute GX of {template_path} at {THIS_FILE}:{line_number}: 1.",
    ) as info:
        execute(template_path, load=plugin_path, x=1)
    assert _is_main("%error {x}", info.value.report())
    assert _is_main("raise ValueError(x)", info.value.report())

    line_number = this_line(+1)
    gx = GX.parse(template_path)
    gx.load(plugin_path)
    gx.generate()

    plugin_path.unlink()
    with pytest.raises(
        ExecutionError,
        match=rf"Failed to execute GX of {template_path} at {THIS_FILE}:{line_number}: 1.",
    ) as info:
        gx.execute(x=1)
    assert _is_main("%error {x}", info.value.report())
    assert _is_unknown(plugin_path, info.value.report())

    plugin_path.write_text("")
    with pytest.raises(
        ExecutionError,
        match=rf"Failed to execute GX of {template_path} at {THIS_FILE}:{line_number}: 1.",
    ) as info:
        gx.execute(x=1)
    assert _is_main("%error {x}", info.value.report())
    assert _is_unknown(plugin_path, info.value.report())


def test_generation_error_with_multiple_sources(tmp_path: pathlib.Path) -> None:
    template1_path = tmp_path / "template1.aur"
    template1_text = trim(
        """
        %include: template2 continue_generation=True
        !x
        """
    )
    template1_path.write_text(template1_text)

    template2_text = trim(
        """
        %include: "template3.aur" continue_generation=True
        !x
        """
    )

    template3_path = tmp_path / "template3.aur"
    template3_text = trim(
        """
        %error 1
        """
    )
    template3_path.write_text(template3_text)

    def g_error(gx, x):
        raise ValueError(x)

    with pytest.raises(
        GenerationError,
        match=rf"Failed to generate GX of {template3_path} at {template1_path}:1: 1.",
    ) as info:
        execute(template1_path, g_template2=template2_text, load={"g_error": g_error})
    assert _is_main("%error 1", info.value.report())
    assert _is_main('%include: "template3.aur" continue_generation=True', info.value.report())
    assert _is_main("%include: template2 continue_generation=True", info.value.report())
    assert _is_main("error(gx, '1')", info.value.report())


def test_execution_error_with_multiple_sources(tmp_path: pathlib.Path) -> None:
    template1_path = tmp_path / "template1.aur"
    template1_text = trim(
        """
        %include: template2
        !x
        """
    )
    template1_path.write_text(template1_text)

    template2_text = trim(
        """
        %include template3.aur
        !x
        """
    )

    template3_path = tmp_path / "template3.aur"
    template3_text = trim(
        """
        !x
        """
    )
    template3_path.write_text(template3_text)

    line_number = this_line(+5)
    with pytest.raises(
        ExecutionError,
        match=rf"Failed to execute GX of {template1_path} at {THIS_FILE}:{line_number}: name 'x' is not defined.",
    ) as info:
        execute(template1_path, g_template2=template2_text)
    assert _is_main("!x", info.value.report())
    assert _is_main("%include template3.aur", info.value.report())
    assert _is_main("%include: template2", info.value.report())


def test_double_generation_error(tmp_path: pathlib.Path) -> None:
    template_path = tmp_path / "template.aur"
    template_text = trim(
        """
        %hello
        """
    )
    template_path.write_text(template_text)

    line_number = this_line(+6)
    with pytest.raises(
        GenerationError,
        match=rf"Failed to generate GX of {template_path} at {THIS_FILE}:{line_number}: unknown macro 'hello' on line 1 \(available macros are .*\).",  # noqa: E501 (line too long)
    ):
        generate(
            """
            %include: template_path
            """,
            template_path=template_path,
        )


def test_double_execution_error(tmp_path: pathlib.Path) -> None:
    template_path = tmp_path / "template.aur"
    template_text = trim(
        """
        !x
        """
    )
    template_path.write_text(template_text)

    def g_execute(gx):
        gx.add_code("execute()")

    def x_execute(gx):
        execute(template_path)

    line_number = this_line(-2)
    with pytest.raises(
        ExecutionError,
        match=rf"Failed to execute GX of {template_path} at {THIS_FILE}:{line_number}: name 'x' is not defined.",
    ):
        execute(
            """
            %execute
            """,
            load={"g_execute": g_execute, "x_execute": x_execute},
        )


def test_error_base_class() -> None:
    gx = GX.parse(
        """
        !x
    """
    )
    with pytest.raises(NotImplementedError):
        Error(gx, ValueError("test")).report()


def _is_main(text: str, report: str) -> bool:
    return re.search(f"\x1b\\[1;33m\\s*{re.escape(text)}\\n\x1b\\[0m", report) is not None


def _is_unknown(path: pathlib.Path, report: str) -> bool:
    return (
        re.search(
            f"\x1b\\[1;34min /.*?/{path.name}:\\d+:\\n\x1b\\[0m\x1b\\[1;47;30m\\s*\\?\\?\\?\\n\x1b\\[0m",
            report,
            flags=re.DOTALL,
        )
        is not None
    )
