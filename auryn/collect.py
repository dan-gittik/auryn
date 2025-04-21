import ast
import builtins
import pathlib
from types import CodeType

BUILTIN_NAMES = set(vars(builtins))


class DefinitionCollector(ast.NodeTransformer):

    def __init__(self) -> None:
        self.evals: dict[str, str] = {}
        self.defs: dict[str, str] = {}
        self.imps: dict[str, tuple[str, str | None]] = {}

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        if node.name.startswith("eval_"):
            node.name = node.name.removeprefix("eval_")
            node.args.args = node.args.args[1:]
            self.evals[node.name] = ast.unparse(node)
        else:
            self.defs[node.name] = ast.unparse(node)
        return node

    def visit_Import(self, node: ast.Import) -> ast.Import:
        for alias in node.names:
            self.imps[alias.asname or alias.name] = alias.name, None
        return node

    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.ImportFrom:
        for alias in node.names:
            self.imps[alias.asname or alias.name] = alias.name, node.module
        return node


def collect_definitions(
    code: str,
    paths: set[pathlib.Path],
) -> tuple[dict[str, str], dict[str, tuple[str, str | None]]]:
    evals: dict[str, str] = {}
    defs: dict[str, str] = {}
    imps: dict[str, tuple[str, str | None]] = {}
    for path in paths:
        dc = DefinitionCollector()
        dc.visit(ast.parse(path.read_text()))
        evals |= dc.evals
        defs |= dc.defs
        imps |= dc.imps
    used_defs: dict[str, str] = {}
    used_imps: dict[str, tuple[str, str | None]] = {}
    for name in collect_global_references(code):
        if name not in evals:
            continue
        code = used_defs[name] = evals.pop(name)
        collect_dependencies(code, defs, imps, used_defs, used_imps)
    return used_defs, used_imps


def collect_dependencies(
    code: str,
    defs: dict[str, str],
    imps: dict[str, tuple[str, str | None]],
    used_defs: dict[str, str],
    used_imps: dict[str, tuple[str, str | None]],
) -> None:
    for name in collect_global_references(code):
        if name in imps:
            used_imps[name] = imps.pop(name)
        elif name in defs:
            code = used_defs[name] = defs.pop(name)
            collect_dependencies(code, defs, imps, used_defs, used_imps)


def collect_global_references(code: str | CodeType) -> set[str]:
    if isinstance(code, str):
        code = compile(code, "", "exec")
    names = set(code.co_names)
    for const in code.co_consts:
        if isinstance(const, CodeType):
            names |= collect_global_references(const)
    return names - BUILTIN_NAMES
