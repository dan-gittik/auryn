from __future__ import annotations

import ast
import builtins
import json
import pathlib
import re
from types import CodeType
from typing import ClassVar, TypedDict

from .template import Template
from .utils import refers_to_file

type CodeArgument = str | pathlib.Path | Code

BUILTIN_NAMES = set(vars(builtins))
SOURCE_COMMENT = re.compile(
    r"""
    ^
    (\s*) # whitespace
    (.*?) # content
    \s* \# \s*
    ([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}) # source ID
    :
    (\d+) # template line number
    $
    """,
    flags=re.VERBOSE,
)


class Code:
    """
    The code generated in a generation/execution.

    Attributes:
        lines: The lines of generated code.
    """

    # The prefix of the comment that holds the sources involved in the generation.
    sources_comment_prefix: ClassVar[str] = "# sources: "

    def __init__(self, lines: list[Line] | None = None) -> None:
        if lines is None:
            lines = []
        self.lines = lines

    @classmethod
    def restore(cls, code: CodeArgument, *, stack_level: int = 0) -> tuple[Code, str]:
        """
        Restore standalone generated code from a string, a path, or another code object.

        Arguments:
            code: The standalone generated code to restore.
                If it's a code object, it's returned as is; if it's a path object or a string refering to a
                valid file, its contents are restored; otherwise, *it* is restored.
            stack_level: How many frames to ascend to infer source origins.

        Returns:
            The generated code and the intro that should be executed into its execution namespace before it can run.
        """
        if isinstance(code, Code):
            return code, ""
        if refers_to_file(code):
            text = pathlib.Path(code).read_text()
        else:
            text = str(code)
        gxs: dict[str, GX] = {}
        lines: list[Line] = []
        intro: list[str] = []
        for line in text.splitlines():
            # Restore sources from the sources comment.
            if line.startswith(cls.sources_comment_prefix):
                sources: dict[str, Source] = json.loads(line.removeprefix(cls.sources_comment_prefix))
                # For each source, create a GX with its ID, template path and text, and origin path and line number.
                for source_id, source in sources.items():
                    gx = GX(Origin.infer(stack_level=stack_level + 1), Template(), Code())
                    gx.id = source_id
                    if template_path := source["template_path"]:
                        gx.template.path = pathlib.Path(template_path)
                    gx.template.text = source["template_text"]
                    if origin_path := source["origin_path"]:
                        gx.origin.path = pathlib.Path(origin_path)
                    gx.origin.line_number = source["origin_line_number"]
                    gxs[source_id] = gx
                # Once we have all the sources, link them to their parents.
                for source_id, source in sources.items():
                    if origin_id := source["origin_gx"]:
                        gxs[source_id].origin.gx = gxs[origin_id]
            # Restore code lines that have a source comment, linking them to their source.
            elif match := SOURCE_COMMENT.match(line):
                whitespace, content, source_id, line_number = match.groups()
                lines.append(Line(gxs[source_id], int(line_number), len(whitespace), content))
            # Lines with no source comment are part of the intro.
            else:
                intro.append(line)
        return cls(lines), "\n".join(intro)

    def append(self, gx: GX, template_line_number: int, indent: int, content: str) -> Line:
        """
        Append a line.

        Arguments:
            gx: The generation/execution the code is generated in.
            template_line_number: The template line number the code is generated on.
            indent: The code indentation.
            content: The code content.

        Returns:
            The appended line.
        """
        line = Line(gx, template_line_number, indent, content)
        self.lines.append(line)
        return line

    def to_string(self, gx: GX, *, standalone: bool) -> str:
        """
        Return the generated code as a string.

        Arguments:
            gx: The generation/execution the code is generated in.
            standalone: Whether to append intro code that makes the generated code executable on its own.

        Returns:
            The generated code as a string.
        """
        code = "\n".join(line.to_string(add_source_comment=standalone) for line in self.lines)
        if standalone:
            code = self._add_intro(gx, code)
        return code

    def _add_intro(self, gx: GX, code: str) -> str:
        intro: list[str] = []
        # Add a comment with sources, mapping each GX ID to the configurations necessary to reconstruct it later: its
        # template path and text, its origin path and line number, and its parent GX ID (if it has one).
        sources: dict[str, Source] = {}
        for line in self.lines:
            if line.gx.id in sources:
                continue
            sources.update(self._collect_sources(line.gx))
        if sources:
            intro.append(f"{self.sources_comment_prefix}{json.dumps(sources)}\n")
        # Collect the files of any hooks mentioned in the generated code.
        paths: set[pathlib.Path] = set()
        for name in self._collect_global_references(code):
            if name not in gx.x_globals:
                continue
            hook = gx.x_globals.get(name)
            # If the hook is standard part of GX object (EMIT, INDENT, etc.), it will be available when duration
            # execution anyway, so there's no need to collect it.
            if hook is gx or getattr(gx, name, None) == hook:
                continue
            # If the hook is decorated, unpeel it to find its true location.
            while hasattr(hook, "__wrapped__"):
                hook = hook.__wrapped__  # type: ignore
            if hasattr(hook, "__code__"):
                paths.add(pathlib.Path(hook.__code__.co_filename))  # type: ignore
        # Collect all the imports and definitions needed to make the code standalone.
        defs, imps = self._collect_definitions(code, paths)
        # Add the imports.
        for name, (what, whence) in imps.items():
            if whence is None:
                if name == what:
                    intro.append(f"import {name}")
                else:
                    intro.append(f"import {what} as {name}")
            elif name == what:
                intro.append(f"from {whence} import {name}")
            else:
                intro.append(f"from {whence} import {what} as {name}")
        # If there were any imports, add two empty lines to separate them from the definitions.
        if imps:
            intro.append("\n")
        # Add the definitions.
        for name, def_ in defs.items():
            intro.append(f"{def_}\n")
        # If there were any definitions after the imports, add an empty line to separate them from the generated code.
        if imps and defs:
            intro.append("")
        return "\n".join(intro) + code

    def _collect_sources(self, gx: GX) -> dict[str, Source]:
        sources = {
            gx.id: Source(
                template_path=str(gx.template.path) if gx.template.path else None,
                template_text=gx.template.text,
                origin_path=str(gx.origin.path),
                origin_line_number=gx.origin.line_number,
                origin_gx=gx.origin.gx.id if gx.origin.gx else None,
            )
        }
        if gx.origin.gx:
            sources.update(self._collect_sources(gx.origin.gx))
        return sources

    def _collect_global_references(self, code: str | CodeType) -> set[str]:
        if isinstance(code, str):
            code = compile(code, "", "exec")
        names = set(code.co_names)
        for const in code.co_consts:
            if isinstance(const, CodeType):
                names |= self._collect_global_references(const)
        return names - BUILTIN_NAMES

    def _collect_definitions(
        self,
        code: str,
        paths: set[pathlib.Path],
    ) -> tuple[dict[str, str], dict[str, tuple[str, str | None]]]:
        # Use AST to collect all the hooks, definitions and imports.
        hooks: dict[str, str] = {}
        defs: dict[str, str] = {}
        imps: dict[str, tuple[str, str | None]] = {}
        for path in paths:
            tree = ast.parse(path.read_text())
            dc = DefinitionCollector()
            dc.visit(tree)
            hooks |= dc.hooks
            defs |= dc.defs
            imps |= dc.imps
        # Extract only those definitions used by the code.
        used_defs: dict[str, str] = {}
        used_imps: dict[str, tuple[str, str | None]] = {}
        for name in self._collect_global_references(code):
            if name not in hooks:
                continue
            hook_code = hooks.pop(name)
            used_defs[name] = hook_code
            self._collect_dependencies(hook_code, defs, imps, used_defs, used_imps)
        return used_defs, used_imps

    def _collect_dependencies(
        self,
        code: str,
        defs: dict[str, str],
        imps: dict[str, tuple[str, str | None]],
        used_defs: dict[str, str],
        used_imps: dict[str, tuple[str, str | None]],
    ) -> None:
        for name in self._collect_global_references(code):
            if name in imps:
                used_imps[name] = imps.pop(name)
            elif name in defs:
                def_code = defs.pop(name)
                used_defs[name] = def_code
                self._collect_dependencies(def_code, defs, imps, used_defs, used_imps)


class Line:
    """
    A line of generated code.

    Attributes:
        gx: The generation/execution that generated the code.
        template_line_number: The template line number the code was generated on.
        indent: The code indentation.
        content: The code content.
    """

    def __init__(self, gx: GX, template_line_number: int, indent: int, content: str) -> None:
        self.gx = gx
        self.template_line_number = template_line_number
        self.indent = indent
        self.content = content

    def to_string(self, *, add_source_comment: bool) -> str:
        """
        Return the generated code as a string.

        Arguments:
            add_source_comment: Whether to append a source comment to the generated code.

        Returns:
            The generated code as a string.
        """
        output = [" " * self.indent, self.content]
        if add_source_comment:
            output.append(f" # {self.gx.id}:{self.template_line_number}")
        return "".join(output)


class Source(TypedDict):
    template_path: str | None
    template_text: str
    origin_path: str
    origin_line_number: int
    origin_gx: str | None


class DefinitionCollector(ast.NodeTransformer):

    def __init__(self) -> None:
        # A mapping of hook names to their definitions.
        self.hooks: dict[str, str] = {}
        # A mapping of other names to their definitions.
        self.defs: dict[str, str] = {}
        # A mapping of what name is created (module or alias), what is imported (module or object), and from where from
        # (module or None).
        self.imps: dict[str, tuple[str, str | None]] = {}

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        # Collect definitions of hooks.
        if node.name.startswith(GX.execution_prefix):
            # Remove the execution prefix and the first argument (GX), which is passed implicitly; in standalone code it
            # will be a global variable anyway.
            node.name = node.name.removeprefix(GX.execution_prefix)
            node.args.args = node.args.args[1:]
            self.hooks[node.name] = ast.unparse(node)
        # Collect other definitions, in case they are referenced by the hooks.
        else:
            self.defs[node.name] = ast.unparse(node)
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        self.defs[node.name] = ast.unparse(node)
        return node

    def visit_Import(self, node: ast.Import) -> ast.Import:
        for alias in node.names:
            # import x      -> x: (x, None)
            # import x as y -> y: (x, None)
            self.imps[alias.asname or alias.name] = alias.name, None
        return node

    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.ImportFrom:
        for alias in node.names:
            # from x import y      -> y: (y, x)
            # from x import y as z -> z: (y, x)
            self.imps[alias.asname or alias.name] = alias.name, node.module
        return node


from .gx import GX
from .origin import Origin
