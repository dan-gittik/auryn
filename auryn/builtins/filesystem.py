import contextlib
import os
import pathlib
import subprocess
from typing import Iterator

from auryn import Junk


def on_load(junk: Junk) -> None:
    junk.emit_code(
        """
        try:
            __import__("os").chdir(root)
        except NameError:
            __import__("os").chdir(junk.path.parent)
        """
    )


def meta_d(
    junk: Junk,
    name: str,
    source: str | pathlib.Path | None = None,
    render: bool = False,
    interpolate: bool | None = None,
) -> None:
    junk.emit_code(f"with directory({junk.interpolate(name)}):")
    with junk.increase_code_indent():
        if source:
            root = junk.path.parent / source
            print(root)
            for path in root.rglob("*"):
                if path.is_file():
                    name = str(path.relative_to(root))
                    meta_f(junk, name, path, render, interpolate)
        if junk.line.children:
            junk.transpile(junk.line.children.snap(junk.line.indent))
        else:
            junk.emit_code("pass")


@contextlib.contextmanager
def eval_directory(junk: Junk, name: str) -> Iterator[None]:
    cwd = os.getcwd()
    path = pathlib.Path(name)
    path.mkdir(parents=True, exist_ok=True)
    os.chdir(path)
    yield
    os.chdir(cwd)


def meta_f(
    junk: Junk,
    name: str,
    source: str | pathlib.Path | None = None,
    render: bool = False,
    interpolate: bool | None = None,
) -> None:
    junk.emit_code(f"with file({junk.interpolate(name)}):")
    with junk.increase_code_indent():
        if source:
            if render:
                source_junk = junk.from_file(junk.path.parent / source)
                source_junk.meta_state = junk.meta_state
                source_junk.transpile()
                junk.emit_code(source_junk.to_string())
            else:
                source_text = (junk.path.parent / source).read_text()
                junk.emit_text(0, source_text, interpolate=interpolate)
        elif junk.line.children:
            junk.transpile(junk.line.children.snap(junk.line.indent))
        else:
            junk.emit_code("pass")


@contextlib.contextmanager
def eval_file(junk: Junk, name: str) -> Iterator[None]:
    path = pathlib.Path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with junk.redirect_output() as output:
        yield
        path.write_text("".join(output).strip())


def meta_x(
    junk,
    command,
    *,
    into: str | None = None,
    stderr_into: str | None = None,
    status_into: str | None = None,
    timeout: int | None = None,
    strict: bool | None = None,
):
    args = [junk.interpolate(command)]
    if timeout:
        args.append(f"timeout={timeout!r}")
    if strict:
        args.append("strict=True")
    retvals = [
        into if into else "_",
        stderr_into if stderr_into else "_",
        status_into if status_into else "_",
    ]
    junk.emit_code(f"{', '.join(retvals)} = shell({', '.join(args)})")


def eval_shell(
    junk: Junk,
    command: str,
    *,
    timeout: int | None = None,
    strict: bool | None = None,
) -> tuple[str, str, int]:
    result = subprocess.run(command, shell=True, capture_output=True, timeout=timeout)
    if strict and result.returncode:
        raise RuntimeError(f"failed to run {command!r}: " f"[{result.returncode}] {result.stderr.decode()}")
    return result.stdout.decode(), result.stderr.decode(), result.returncode
