import pathlib

import pytest

from auryn import EvaluationError, evaluate, render, transpile

from .conftest import trim


def test_filesystem(tmp_path: pathlib.Path) -> None:
    output = render(
        """
        %load filesystem
        %d dir
            %f file
                hello world
            %d subdir
                %f subfile
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
    code = transpile(
        """
        %load filesystem
        %d dir
            %f file
                hello world
            %d subdir
                %f subfile
                    hello {name}
        """,
        standalone=True,
    )
    assert evaluate(code, root=tmp_path, name="alice") == ""

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


def test_filesystem_name_interpolation(tmp_path: pathlib.Path) -> None:
    received = render(
        """
        %load filesystem
        %d {dirname}
            %f {filename}
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


def test_filesystem_empty(tmp_path: pathlib.Path) -> None:
    file = tmp_path / "file"
    file.write_text("")

    received = render(
        """
        %load filesystem
        %d dir
        %f file
        """,
        root=tmp_path,
    )
    assert received == ""
    dir = tmp_path / "dir"
    assert dir.is_dir()
    file = tmp_path / "file"
    assert file.is_file()
    assert file.read_text() == ""


def test_filesystem_source(tmp_path: pathlib.Path) -> None:
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

    template_path = tmp_path / "template.txt"
    template_code = trim(
        """
        %load filesystem
        %d: "dir" source="source_dir"
            %f: "file2" source="source_file"
        """
    )
    template_path.write_text(template_code)

    assert render(template_path, root=tmp_path, name="alice") == ""

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


def test_filesystem_render(tmp_path: pathlib.Path) -> None:
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

    received = render(
        """
        %load filesystem
        %d: "dir" source=source_dir render=True
            %f: "file2" source=source_file render=True
        """,
        meta_context={
            "source_dir": source_dir,
            "source_file": source_file,
        },
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


def test_filesystem_no_interpolation(tmp_path: pathlib.Path) -> None:
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
        %d: "dir" source="source_dir" interpolate=False
            %f: "file2" source="source_file" interpolate=False
        """
    )
    template_path.write_text(template_code)

    assert render(template_path, root=tmp_path, name="alice", n=3) == ""

    dir = tmp_path / "dir"
    assert dir.is_dir()
    file1 = dir / "file1"
    assert file1.is_file()
    assert file1.read_text() == file_code
    file2 = dir / "file2"
    assert file2.is_file()
    assert file2.read_text() == file_code


def test_filesystem_shell(tmp_path: pathlib.Path) -> None:
    template_path = tmp_path / "template.txt"
    template_code = trim(
        """
        %load filesystem
        %x echo {content} > file
        """
    )
    template_path.write_text(template_code)

    assert render(template_path, root=tmp_path, content="hello world") == ""

    file = tmp_path / "file"
    assert file.is_file()
    assert file.read_text() == "hello world\n"


def test_filesystem_redirect(tmp_path: pathlib.Path) -> None:
    template_path = tmp_path / "template.txt"
    template_code = trim(
        """
        %load filesystem
        %x: "echo {stdout}" into="x"
        %x: "echo {stderr} 1>&2" stderr_into="y"
        %x: "bash -c 'exit 3'" status_into="z"
        %f file
            {x}{y}{z}
        """
    )
    template_path.write_text(template_code)

    assert render(template_path, root=tmp_path, stdout="stdout", stderr="stderr") == ""

    file = tmp_path / "file"
    assert file.is_file()
    assert file.read_text() == "stdout\nstderr\n3"


def test_filesystem_strict(tmp_path: pathlib.Path) -> None:
    template_path = tmp_path / "template.txt"
    template_code = trim(
        """
        %load filesystem
        %x asdf
        %f file1
            hello world
        """
    )
    template_path.write_text(template_code)

    assert render(template_path, root=tmp_path) == ""

    file1 = tmp_path / "file1"
    assert file1.is_file()
    assert file1.read_text() == "hello world"

    template_path = tmp_path / "template.txt"
    template_code = trim(
        """
        %load filesystem
        %x: "asdf" strict=True
        %f file2
            hello world
        """
    )
    template_path.write_text(template_code)

    with pytest.raises(EvaluationError, match=r"failed to run 'asdf': \[127\] /bin/sh: asdf: command not found"):
        render(template_path, root=tmp_path)
    file2 = tmp_path / "file2"
    assert not file2.exists()


def test_filesystem_timeout(tmp_path: pathlib.Path) -> None:
    template_path = tmp_path / "template.txt"
    template_code = trim(
        """
        %load filesystem
        %x: "sleep 1" timeout=0.5
        %f file
            hello world
        """
    )
    template_path.write_text(template_code)

    with pytest.raises(EvaluationError, match="TimeoutExpired: Command 'sleep 1' timed out after 0.5 seconds"):
        render(template_path, root=tmp_path)
    file = tmp_path / "file"
    assert not file.exists()
