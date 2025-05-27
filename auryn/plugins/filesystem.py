import contextlib
import os
import pathlib
import re
import subprocess
from typing import Iterator

from ..gx import GX, LineTransform
from ..interpolate import split

PATH_INVOCATION = re.compile(
    r"""
    ^
    ([^:]+?)
    (?:
        (:{0,2})
        \s+
        (.*)
    )?
    $
    """,
    flags=re.VERBOSE,
)
SHELL_INVOCATION = re.compile(
    r"""
    ^
    ([^#]+)
    (?:
        (\#{0,2})
        \s+
        (.*)
    )?
    $
    """,
    flags=re.VERBOSE,
)
core_line_transforms: dict[str, LineTransform] = {}


def on_load(gx: GX) -> None:
    """
    Adds navigation to the root specified in the execution context, if provided, or to the generation/execution root if
    not, and installs the path and shell line transforms.

    Arguments:
        gx: The generation/execution.
    """
    gx.add_code(
        """
        try:
            __import__("os").chdir(root)
        except NameError:
            __import__("os").chdir(gx.root)
        """
    )
    core_line_transforms.update(gx.line_transforms)
    gx.line_transform(transform_path)
    gx.line_transform(transform_shell, "$")


def transform_path(gx: GX, content: str) -> None:
    """
    Transforms path lines to directory generation (if they end with /) or file generation (otherwise) instructions,
    passing on arguments that appear after : (string-delimited) or :: (as-is).

        >>> # Creates a directory d, with a file f, with content "hello world".
        >>> execute('''
        ...     d/
        ...         f
        ...             hello world
        ... ''')

        >>> # Creates a directory d with the contents of source_dir, as well as a file f generated from source_template.
        >>> execute('''
        ...     d/ source_dir
        ...         f: "source_template" generate=True
        ... ''')

    Arguments:
        gx: The generation/execution.
        content: The line content.
    """
    match = PATH_INVOCATION.match(content)
    if not match:
        raise ValueError(
            f"expected path on {gx.line} to be '<path> [argument]', '<path>: <arguments>' or "
            f"'<path>:: <arguments>', but got {content!r}"
        )
    path, invocation_type, arg = match.groups()
    macro = "directory" if path.endswith("/") else "file"
    # There are three ways to call path macros:
    # 1. <path> [argument] - called with 0-1 arguments, passed in as a string;
    # 2. <path>: <arguments> - called with arguments split by whitespace, respecting quoted strings;
    # 3. <path>:: <arguments> - called with arguments as-is.
    if not arg:
        code = f"{macro}(gx, {path!r})"
    elif not invocation_type:
        code = f"{macro}(gx, {path!r}, {arg!r})"
    elif invocation_type == ":":
        code = f"{macro}(gx, {path!r}, {', '.join(split(arg))})"
    else:  # invocation_type == "::"
        code = f"{macro}(gx, {path!r}, {arg})"
    gx.g_exec(code)


def transform_shell(gx: GX, content: str) -> None:
    """
    Transforms shell lines to shell execution instructions, passing on arguments that appear after # (string-delimited)
    or ## (as-is).

        >>> # Makes a file executable.
        >>> execute('''
        ...     $ echo chmod +x script
        ... ''')

        >>> # Downloads content from the web into a variable (with a timeout)
        >>> output = execute('''
        ...     $ curl {url} # into="x" timeout=1
        ...     {x}
        ... ''', url='...')
        >>> print(output)
        <URL data>

    Arguments:
        gx: The generation/execution.
        content: The line content.
    """
    match = SHELL_INVOCATION.match(content)
    if not match:
        raise ValueError(
            f"expected shell command on {gx.line} to be '<command>', '<command> # <arguments>' or "
            f"'<command> ## <arguments>', but got {content!r}"
        )
    command, invocation_type, arg = match.groups()
    command = command.strip()
    # There are three ways to call shell command macros:
    # 1. $<command> - called with 0 keyword arguments;
    # 2. $<command> # <keywords> - called with keyword arguments split by whitespace, respecting quoted strings;
    # 3. $<command> ## <keywords> - called with keyword arguments as-is.
    if not invocation_type:
        code = f"shell(gx, {command!r})"
    elif invocation_type == "#":
        code = f"shell(gx, {command!r}, {', '.join(split(arg))})"
    else:  # invocation_type == "##"
        code = f"shell(gx, {command!r}, {arg})"
    gx.g_exec(code)


def g_directory(
    gx: GX,
    path: str,
    source: str | pathlib.Path | None = None,
    *,
    generate: bool = False,
    interpolate: bool | None = None,
) -> None:
    """
    Generate a directory.

        >>> # Generates a directory d, with a subdirectory sd with the contents of source_dir.
        >>> execute('''
        ...     d/
        ...         sd/ source_dir
        ... ''')

    Arguments:
        gx: The generation/execution.
        path: The directory path (relative to its parent; support interpolation).
        source: An optional source directory (relative to the generation/execution root; supports interpolation).
        generate: Whether to generate files in the the source directory.
        interpolate: Whether to interpolate files in the source directory.
    """
    gx.add_code(f"with directory({gx.interpolated(path)}):")
    with gx.increased_code_indent():
        if source:
            root = gx.root / gx.g_interpolate(str(source))
            for entry in root.rglob("*"):
                if entry.is_file():
                    file_path = str(entry.relative_to(root))
                    g_file(gx, file_path, entry, generate=generate, interpolate=interpolate)
                elif entry.is_dir():
                    directory_path = str(entry.relative_to(root))
                    g_directory(gx, directory_path, entry, generate=generate, interpolate=interpolate)
        if gx.line.children:
            gx.transform(gx.line.children.snap())
        else:
            gx.add_code("pass")


@contextlib.contextmanager
def x_directory(gx: GX, name: str) -> Iterator[None]:
    """
    The corresponding hook to the %directory macro (path ending with /).
    """
    cwd = os.getcwd()
    path = pathlib.Path(name)
    path.mkdir(parents=True, exist_ok=True)
    os.chdir(path)
    yield
    os.chdir(cwd)


def g_file(
    gx: GX,
    name: str,
    source: str | pathlib.Path | None = None,
    *,
    generate: bool = False,
    interpolate: bool | None = None,
) -> None:
    """
    Generate a file.

        >>> # Generates a file f1 with the content "hello world", a file f2 with the contents of source_file, and a file
        ... # f3 generated from source_template.
        >>> execute('''
        ...     f1
        ...         hello world
        ...     f2 source_file
        ...     f3: "source_template" generate=True
        ... ''')

    Arguments:
        gx: The generation/execution.
        path: The file path (relative to its parent; support interpolation).
        source: An optional source file (relative to the generation/execution root; supports interpolation).
        generate: Whether to generate the source file as a template; if source is not provided, this is ignored.
        interpolate: Whether to interpolate the file content; if generate=True, this is ignored.
    """
    gx.add_code(f"with file({gx.interpolated(name)}):")
    with gx.increased_code_indent():
        if source:
            path = gx.root / gx.g_interpolate(str(source))
            if generate:
                source_gx = gx.derive(path)
                source_gx.generate(gx.g_locals)
                gx.extend(source_gx)
            else:
                source_text = path.read_text()
                gx.add_text(0, source_text, interpolate=interpolate)
        elif gx.line.children:
            with gx.patch(line_transforms=core_line_transforms):
                gx.transform(gx.line.children.snap())
        else:
            gx.add_code("pass")


@contextlib.contextmanager
def x_file(gx: GX, name: str) -> Iterator[None]:
    """
    The corresponding hook to the %file macro (path not ending with /).
    """
    path = pathlib.Path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    output: list[str] = []
    with gx.patch(output=output):
        yield
        path.write_text("".join(output).strip())


def g_shell(
    gx: GX,
    command: str,
    *,
    into: str | None = None,
    stderr_into: str | None = None,
    status_into: str | None = None,
    timeout: int | None = None,
    strict: bool | None = False,
):
    """
    Generate a shell command.

        >>> # Makes a file executable.
        >>> execute('''
        ...     $ echo chmod +x script
        ... ''')

        >>> # Downloads content from the web into a variable (with a timeout)
        >>> output = execute('''
        ...     $ curl {url} # into="x" timeout=1
        ...     {x}
        ... ''', url='...')
        >>> print(output)
        <URL data>

    Arguments:
        gx: The generation/execution.
        command: The command to run (supports interpolation).
        into: The variable to store the command output in.
        stderr_into: The variable to store the command stderr in.
        status_into: The variable to store the command status in.
        timeout: The command timeout (in seconds).
        strict: Whether to raise an error if the command fails (default is False).
    """
    args = [gx.interpolated(command)]
    if timeout:
        args.append(f"timeout={timeout!r}")
    if strict:
        args.append("strict=True")
    retvals = [
        into if into else "_",
        stderr_into if stderr_into else "_",
        status_into if status_into else "_",
    ]
    gx.add_code(f"{', '.join(retvals)} = shell({', '.join(args)})")


def x_shell(
    gx: GX,
    command: str,
    *,
    timeout: int | None = None,
    strict: bool | None = False,
) -> tuple[str, str, int]:
    """
    The corresponding hook to the %shell macro ($).
    """
    result = subprocess.run(command, shell=True, capture_output=True, timeout=timeout)
    if strict and result.returncode:
        raise RuntimeError(f"failed to run {command!r}: " f"[{result.returncode}] {result.stderr.decode()}")
    return result.stdout.decode(), result.stderr.decode(), result.returncode
