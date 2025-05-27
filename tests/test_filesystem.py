import pathlib

import pytest

from auryn import ExecutionError, GenerationError, execute, execute_standalone, generate

from .conftest import this_line, trim

THIS_FILE = pathlib.Path(__file__)


def test_filesystem(tmp_path: pathlib.Path) -> None:
    output = execute(
        """
        %load filesystem
        dir/
            file
                hello world
            subdir/
                subfile
                    hello {name}
        """,
        root=tmp_path,
        name="alice",
    )

    assert output == ""
    dir = tmp_path / "dir"
    assert dir.is_dir()
    file = dir / "file"
    assert file.is_file()
    assert file.read_text() == "hello world"
    subdir = dir / "subdir"
    assert subdir.is_dir()
    subfile = subdir / "subfile"
    assert subfile.is_file()
    assert subfile.read_text() == "hello alice"


def test_filesystem_standalone(tmp_path: pathlib.Path) -> None:
    code = generate(
        """
        %load filesystem
        dir/
            file
                hello world
            subdir/
                subfile
                    hello {name}
        """,
        standalone=True,
    )
    assert execute_standalone(code, root=tmp_path, name="alice") == ""

    dir = tmp_path / "dir"
    assert dir.is_dir()
    file = dir / "file"
    assert file.is_file()
    assert file.read_text() == "hello world"
    subdir = dir / "subdir"
    assert subdir.is_dir()
    subfile = subdir / "subfile"
    assert subfile.is_file()
    assert subfile.read_text() == "hello alice"


def test_filesystem_simple(tmp_path: pathlib.Path) -> None:
    file = tmp_path / "file"
    file.write_text("")

    received = execute(
        """
        %load filesystem
        dir/
        file
        """,
        root=tmp_path,
    )
    assert received == ""
    dir = tmp_path / "dir"
    assert dir.is_dir()
    file = tmp_path / "file"
    assert file.is_file()
    assert file.read_text() == ""


def test_path_interpolation(tmp_path: pathlib.Path) -> None:
    received = execute(
        """
        %load filesystem
        {dirname}/
            {filename}
                {content}
        """,
        root=tmp_path,
        dirname="dir",
        filename="file",
        content="hello world",
    )
    assert received == ""

    dir = tmp_path / "dir"
    assert dir.is_dir()
    file = dir / "file"
    assert file.is_file()
    assert file.read_text() == "hello world"


def test_path_error() -> None:
    line_number = this_line(+5)
    with pytest.raises(
        GenerationError,
        match=rf"Failed to generate GX at {THIS_FILE}:{line_number}: expected path on line 2 to be '<path> \[argument\]', '<path>: <arguments>' or '<path>:: <arguments>', but got ':'.",  # noqa: E501 (line too long)
    ):
        execute(
            """
            %load filesystem
            :
            """
        )


def test_source(tmp_path: pathlib.Path) -> None:
    file_code = trim(
        """
        hello {name}
        !for i in range(n):
            line 0
        """
    )
    source_dir = tmp_path / "source_dir"
    source_dir.mkdir()
    source_dir_file = source_dir / "file1"
    source_dir_file.write_text(file_code)
    source_file = tmp_path / "source_file"
    source_file.write_text(file_code)
    source_subdir = source_dir / "subdir"
    source_subdir.mkdir()

    template_path = tmp_path / "template.txt"
    template_code = trim(
        """
        %load filesystem
        dir/ source_dir
            file2 source_file
        """
    )
    template_path.write_text(template_code)

    assert execute(template_path, root=tmp_path, name="alice") == ""

    file_content = trim(
        """
        hello alice
        !for i in range(n):
            line 0
        """
    )
    dir = tmp_path / "dir"
    assert dir.is_dir()
    file1 = dir / "file1"
    assert file1.is_file()
    assert file1.read_text() == file_content
    file2 = dir / "file2"
    assert file2.is_file()
    assert file2.read_text() == file_content
    subdir = dir / "subdir"
    assert subdir.is_dir()


def test_source_generate(tmp_path: pathlib.Path) -> None:
    file_code = trim(
        """
        hello {name}
        !for i in range(n):
            line {i}
        """
    )
    source_dir = tmp_path / "source_dir"
    source_dir.mkdir()
    source_dir_file = source_dir / "file1"
    source_dir_file.write_text(file_code)
    source_file = tmp_path / "source_file"
    source_file.write_text(file_code)

    received = execute(
        """
        %load filesystem
        dir/: source_dir generate=True
            file2:: source_file, generate=True
        """,
        g_source_dir=source_dir,
        g_source_file=source_file,
        root=tmp_path,
        name="alice",
        n=3,
    )
    assert received == ""

    file_content = trim(
        """
        hello alice
        line 0
        line 1
        line 2
    """
    )
    dir = tmp_path / "dir"
    assert dir.is_dir()
    file1 = dir / "file1"
    assert file1.is_file()
    assert file1.read_text() == file_content
    file2 = dir / "file2"
    assert file2.is_file()
    assert file2.read_text() == file_content


def test_source_no_interpolation(tmp_path: pathlib.Path) -> None:
    file_code = trim(
        """
        hello {name}
        """
    )
    source_dir = tmp_path / "source_dir"
    source_dir.mkdir()
    source_dir_file = source_dir / "file1"
    source_dir_file.write_text(file_code)
    source_file = tmp_path / "source_file"
    source_file.write_text(file_code)

    template_path = tmp_path / "template.txt"
    template_code = trim(
        """
        %load filesystem
        dir/: "source_dir" interpolate=False
            file2:: "source_file", interpolate=False
        """
    )
    template_path.write_text(template_code)

    assert execute(template_path, root=tmp_path, name="alice", n=3) == ""

    dir = tmp_path / "dir"
    assert dir.is_dir()
    file1 = dir / "file1"
    assert file1.is_file()
    assert file1.read_text() == file_code
    file2 = dir / "file2"
    assert file2.is_file()
    assert file2.read_text() == file_code


def test_shell(tmp_path: pathlib.Path) -> None:
    template_path = tmp_path / "template.txt"
    template_code = trim(
        """
        %load filesystem
        $ echo {content} > file
        """
    )
    template_path.write_text(template_code)

    assert execute(template_path, root=tmp_path, content="hello world") == ""

    file = tmp_path / "file"
    assert file.is_file()
    assert file.read_text() == "hello world\n"


def test_shell_redirect(tmp_path: pathlib.Path) -> None:
    template_path = tmp_path / "template.txt"
    template_code = trim(
        """
        %load filesystem
        $ echo {stdout} # into="x"
        $ echo {stderr} 1>&2 # stderr_into="y"
        $ bash -c 'exit 3' ## status_into="z"
        file
            {x}{y}{z}
        """
    )
    template_path.write_text(template_code)

    assert execute(template_path, root=tmp_path, stdout="stdout", stderr="stderr") == ""

    file = tmp_path / "file"
    assert file.is_file()
    assert file.read_text() == "stdout\nstderr\n3"


def test_shell_strict(tmp_path: pathlib.Path) -> None:
    template_path = tmp_path / "template.txt"
    template_code = trim(
        """
        %load filesystem
        $ asdf
        file1
            hello world
        """
    )
    template_path.write_text(template_code)

    assert execute(template_path, root=tmp_path) == ""

    file1 = tmp_path / "file1"
    assert file1.is_file()
    assert file1.read_text() == "hello world"

    template_path = tmp_path / "template.txt"
    template_code = trim(
        """
        %load filesystem
        $ asdf # strict=True
        file2
            hello world
        """
    )
    template_path.write_text(template_code)

    with pytest.raises(ExecutionError, match=r"failed to run 'asdf': \[127\] /bin/sh: asdf: command not found"):
        execute(template_path, root=tmp_path)
    file2 = tmp_path / "file2"
    assert not file2.exists()


def test_shell_timeout(tmp_path: pathlib.Path) -> None:
    template_path = tmp_path / "template.txt"
    template_code = trim(
        """
        %load filesystem
        $ sleep 1 # timeout=0.5
        file
            hello world
        """
    )
    template_path.write_text(template_code)

    with pytest.raises(ExecutionError, match="Command 'sleep 1' timed out after 0.5 seconds"):
        execute(template_path, root=tmp_path)
    file = tmp_path / "file"
    assert not file.exists()


def test_shell_error() -> None:
    line_number = this_line(+5)
    with pytest.raises(
        GenerationError,
        match=rf"Failed to generate GX at {THIS_FILE}:{line_number}: expected shell command on line 2 to be '<command>', '<command> # <arguments>' or '<command> ## <arguments>', but got '#'.",  # noqa: E501 (line too long)
    ):
        execute(
            """
            %load filesystem
            $ #
            """
        )
