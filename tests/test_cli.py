import json
import pathlib
import subprocess
from typing import Any, Callable

import pytest

from .conftest import trim

type CLI = Callable[..., str]


@pytest.fixture
def cli() -> CLI:
    def cli(*args: Any) -> str:
        command = subprocess.run(["python", "-m", "auryn", *map(str, args)], capture_output=True, text=True)
        if command.returncode != 0:
            raise RuntimeError(command.stderr)
        return command.stdout.strip()

    return cli


def test_generate(tmp_path: pathlib.Path, cli: CLI) -> None:
    template_path = tmp_path / "template.aur"
    template_code = trim(
        """
        !for i in range(n):
            line {i}
        """
    )
    template_path.write_text(template_code)

    received = cli("generate", template_path)
    expected = trim(
        """
        for i in range(n):
            emit(0, 'line ', i)
        """
    )
    assert received == expected


def test_execute(tmp_path: pathlib.Path, cli: CLI) -> None:
    template_path = tmp_path / "template.aur"
    template_code = trim(
        """
        !for i in range(n):
            line {i}
        """
    )
    template_path.write_text(template_code)

    received = cli("execute", template_path, "n=3")
    expected = trim(
        """
        line 0
        line 1
        line 2
        """
    )
    assert received == expected

    context = tmp_path / "context.json"
    context.write_text(json.dumps({"n": 3}))
    received = cli("execute", template_path, "-c", context)
    assert received == expected


def test_non_json_context(tmp_path: pathlib.Path, cli: CLI) -> None:
    template_path = tmp_path / "template.aur"
    template_code = trim(
        """
        hello {name}
        """
    )
    template_path.write_text(template_code)

    received = cli("execute", template_path, "name=world")
    expected = trim(
        """
        hello world
        """
    )
    assert received == expected


def test_invalid_context(tmp_path: pathlib.Path, cli: CLI) -> None:
    template_path = tmp_path / "template.aur"
    template_path.write_text("")
    with pytest.raises(RuntimeError, match=r"invalid argument: name \(expected <key>=<value>\)"):
        cli("execute", template_path, "name")


def test_execute_standalone(tmp_path: pathlib.Path, cli: CLI) -> None:
    template_path = tmp_path / "template.aur"
    template_code = trim(
        """
        !for i in range(n):
            line {i}
        """
    )
    template_path.write_text(template_code)

    received = cli("generate", template_path, "-s")
    code_path = tmp_path / "code.py"
    code_path.write_text(received)

    received = cli("execute-standalone", code_path, "n=3")
    expected = trim(
        """
        line 0
        line 1
        line 2
        """
    )
    assert received == expected


def test_error(tmp_path: pathlib.Path, cli: CLI) -> None:
    template_path = tmp_path / "template.aur"
    template_code = trim(
        """
        !x
        """
    )
    template_path.write_text(template_code)
    with pytest.raises(RuntimeError, match=r"Failed to execute GX(.|\n)*?NameError: name 'x' is not defined(.|\n)*"):
        cli("execute", template_path)
