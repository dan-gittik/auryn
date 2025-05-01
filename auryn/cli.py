import argparse
import json
import pathlib
import sys
from typing import Any

from .api import evaluate, render, transpile
from .errors import EvaluationError

def parse_context(path: str | pathlib.Path | None, args: list[str]) -> dict[str, Any]:
    context = {}
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


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Auryn metaprogramming engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    transpile_parser = subparsers.add_parser("transpile", help="transpile a template")
    transpile_parser.add_argument("path", help="template path")
    transpile_parser.add_argument("-S", "--sourcemap", action="store_true", help="add source comments")
    transpile_parser.add_argument("-l", "--load", action="append", help="additional meta-module path or name")
    transpile_parser.add_argument(
        "-n",
        "--no-common",
        action="store_true",
        default=False,
        help="do not load common meta-module",
    )
    transpile_parser.add_argument(
        "-s",
        "--standalone",
        action="store_true",
        default=False,
        help="generate standalone code",
    )

    render_parser = subparsers.add_parser("render", help="render a template")
    render_parser.add_argument("path", help="template path")
    render_parser.add_argument("-c", "--context", default=None, help="context path")
    render_parser.add_argument("-l", "--load", action="append", help="additional meta-module path or name")
    render_parser.add_argument(
        "-n",
        "--no-common",
        action="store_true",
        default=False,
        help="do not load common meta-module",
    )
    render_parser.add_argument(
        "context_kwargs",
        nargs="*",
        default=[],
        help="additional context as key=value pairs",
    )

    evaluate_parser = subparsers.add_parser("evaluate", help="evaluate junk code")
    evaluate_parser.add_argument("path", help="junk code path")
    evaluate_parser.add_argument("-c", "--context", default=None, help="context path")
    evaluate_parser.add_argument(
        "context_kwargs",
        nargs="*",
        default=[],
        help="additional context as key=value pairs",
    )

    args = parser.parse_args(argv)

    try:
        match args.command:
            case "transpile":
                code = transpile(
                    pathlib.Path(args.path).absolute(),
                    sourcemap=args.sourcemap,
                    load=args.load,
                    load_common=not args.no_common,
                    standalone=args.standalone,
                )
                print(code)

            case "render":
                context = parse_context(args.context, args.context_kwargs)
                output = render(
                    pathlib.Path(args.path).absolute(),
                    context,
                    load=args.load,
                    load_common=not args.no_common,
                )
                print(output)

            case "evaluate":
                context = parse_context(args.context, args.context_kwargs)
                output = evaluate(
                    pathlib.Path(args.path).absolute(),
                    context,
                )
                print(output)
    except EvaluationError as error:
        print(error, file=sys.stderr)
        exit(1)