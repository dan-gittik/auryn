import argparse
import json
import pathlib
import sys
from typing import Any

from .api import execute, execute_standalone, generate
from .errors import Error


def cli(argv: list[str] | None = None) -> None:
    """
    The command-line interface for the Auryn metaprogramming engine.

    Args:
        argv: The command line arguments (default is sys.argv).
    """
    parser = argparse.ArgumentParser(description="Auryn metaprogramming engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate", help="generate code from a template")
    generate_parser.add_argument("template", help="template path")
    generate_parser.add_argument("-c", "--context", default=None, help="context path")
    generate_parser.add_argument("-l", "--load", action="append", help="additional plugin paths or names")
    generate_parser.add_argument(
        "-n",
        "--no-core",
        action="store_true",
        default=False,
        help="do not load core plugin",
    )
    generate_parser.add_argument(
        "-s",
        "--standalone",
        action="store_true",
        default=False,
        help="generate standalone code",
    )
    generate_parser.add_argument(
        "context_kwargs",
        nargs="*",
        default=[],
        help="additional context as key=value pairs",
    )

    run_parser = subparsers.add_parser("execute", help="generate code from a template and execute it")
    run_parser.add_argument("template", help="template path")
    run_parser.add_argument("-c", "--context", default=None, help="context path")
    run_parser.add_argument("-l", "--load", action="append", help="additional plugin paths or names")
    run_parser.add_argument(
        "-n",
        "--no-core",
        action="store_true",
        default=False,
        help="do not load core plugin",
    )
    run_parser.add_argument(
        "context_kwargs",
        nargs="*",
        default=[],
        help="additional context as key=value pairs",
    )

    run_standalone_parser = subparsers.add_parser("execute-standalone", help="execute standalone generated code")
    run_standalone_parser.add_argument("code", help="standalone code path")
    run_standalone_parser.add_argument("-c", "--context", default=None, help="context path")
    run_standalone_parser.add_argument(
        "context_kwargs",
        nargs="*",
        default=[],
        help="additional context as key=value pairs",
    )

    args = parser.parse_args(argv)

    try:
        match args.command:
            case "generate":
                context = _parse_context(args.context, args.context_kwargs)
                code = generate(
                    pathlib.Path(args.template).absolute(),
                    context,
                    load=args.load,
                    load_core=not args.no_core,
                    standalone=args.standalone,
                )
                print(code)

            case "execute":
                context = _parse_context(args.context, args.context_kwargs)
                output = execute(
                    pathlib.Path(args.template).absolute(),
                    context,
                    load=args.load,
                    load_core=not args.no_core,
                )
                print(output)

            case "execute-standalone":
                context = _parse_context(args.context, args.context_kwargs)
                output = execute_standalone(
                    pathlib.Path(args.code).absolute(),
                    context,
                )
                print(output)

    except Error as error:
        print(error.report(), file=sys.stderr)
        exit(1)


def _parse_context(path: str | pathlib.Path | None, args: list[str]) -> dict[str, Any]:
    context: dict[str, Any] = {}
    if path:
        path = pathlib.Path(path)
        context.update(json.loads(path.read_text()))
    for arg in args:
        if "=" not in arg:
            raise ValueError(f"invalid argument: {arg} (expected <key>=<value>)")
        key, value = arg.split("=", 1)
        try:
            context[key] = json.loads(value)
        except json.JSONDecodeError:
            context[key] = value
    return context
