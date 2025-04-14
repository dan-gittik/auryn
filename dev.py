import contextlib
import functools
import http.server
import pathlib
import shutil
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).parent
PACKAGE = "auryn"
LINE_LENGTH = 120
COVERAGE_PORT = 5000
ARTEFACTS = [
    ".pytest_cache",
    ".coverage",
    "htmlcov",
    ".mypy_cache",
]


def clean() -> None:
    for path in ROOT.rglob("*"):
        if path.name not in ARTEFACTS:
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def test(args: list[str]) -> None:
    tests = []
    for arg in sys.argv[1:]:
        tests.extend(["-k", arg])
    _execute("pytest", "tests", "-x", "-vv", "--ff", *tests)


def cov() -> None:
    _execute("pytest", f"--cov={PACKAGE}", "--cov-report=html", "tests")
    _serve(ROOT / "htmlcov", COVERAGE_PORT)


def lint(args: list[str]) -> None:
    paths = []
    for arg in args:
        path = ROOT / PACKAGE / arg.replace(".", "/")
        if not path.exists():
            path = path.with_suffix(".py")
        if not path.exists():
            raise FileNotFoundError(f"{path} does not exist")
        paths.append(path)
    if not paths:
        paths.extend([ROOT / PACKAGE, ROOT / "tests"])
    for path in paths:
        _execute("black", f"--line-length={LINE_LENGTH}", path)
        _execute("isort", "--profile=black", path)
        _execute("flake8", f"--max-line-length={LINE_LENGTH}", "--extend-ignore=E203", path)


def type(args: list[str]) -> None:
    packages = []
    for arg in args:
        packages.extend(["-p", f"{PACKAGE}.{arg}"])
    if not packages:
        packages.extend(["-p", PACKAGE])
    _execute("mypy", *packages)


def _execute(*args: Any) -> None:
    subprocess.run([str(arg) for arg in args])


def _serve(directory: pathlib.Path, port: int) -> None:
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler,
        directory=str(directory),
    )
    server = http.server.HTTPServer(("localhost", port), handler)
    print(f"http://localhost:{port}")
    with contextlib.suppress(KeyboardInterrupt):
        server.serve_forever()


def main(args: list[str]) -> None:
    match args:
        case ["clean"]:
            clean()
        case ["test", *args]:
            test(args)
        case ["cov"]:
            cov()
        case ["lint", *args]:
            lint(args)
        case ["type", *args]:
            type(args)
        case _:
            print(f"unknown command {args[0]}")
            sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])