import ast
import os
import re
from typing import Any

SOURCEMAP_REGEX = re.compile(r"(.*?)  # (.*?):(\d+)$")


class StopEvaluation(Exception):
    pass


class EvaluationError(Exception):

    def __init__(self, source: str, code: str, context: dict[str, Any], error: Exception) -> None:
        self.source = source
        self.code = code
        self.context = context
        self.error = error

    def __str__(self) -> str:
        output: list[str] = [f"Failed to evaluate junk at {self.source}."]
        output.append("Context:")
        if self.context:
            for key, value in self.context.items():
                output.append(f"  {key}: {value!r}")
        else:
            output.append("  <none>")
        output.append("Traceback (most recent call last):")
        traceback = self.error.__traceback__ and self.error.__traceback__.tb_next
        while traceback:
            code, template = self._parse_sourcemap(traceback.tb_frame.f_code.co_filename, traceback.tb_lineno)
            if traceback.tb_frame.f_code.co_filename == self.source:
                file = "Junk"
            else:
                file = f'File "{os.path.basename(traceback.tb_frame.f_code.co_filename)}"'
            output.append(
                self._indent(2, f"{file}, line {traceback.tb_lineno}, in {traceback.tb_frame.f_code.co_name}")
            )
            output.append(self._indent(4, code))
            if template:
                template_code, template_path, template_line_number = template
                output.append(self._indent(4, f'@ File "{template_path}", line {template_line_number}'))
                output.append(self._indent(6, template_code))
            traceback = traceback.tb_next
        output.append(f"{type(self.error).__name__}: {self.error}")
        return "\n".join(output)

    def _parse_sourcemap(self, filename: str, line_number: int) -> tuple[str, tuple[str, str, str] | None]:
        if filename == self.source:
            source = self.code
        else:
            with open(filename) as file:
                source = file.read()
        code = source.splitlines()[line_number - 1]
        match = SOURCEMAP_REGEX.match(code)
        if match:
            code, template_path, template_line_number = match.groups()
            with open(template_path) as file:
                template_code = file.read().splitlines()[int(template_line_number) - 1]
            template = template_code.strip(), os.path.basename(template_path), template_line_number
        else:
            template = None
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # end_lineno can be None in older Python versions or for certain AST nodes
                if node.end_lineno is None or not node.lineno <= line_number <= node.end_lineno:
                    continue
                code_block = ast.get_source_segment(source, node)
                if code_block:
                    code_lines: list[str] = []
                    for n, code_line in enumerate(code_block.splitlines()):
                        if n == line_number - node.lineno:
                            code_lines.append(f"> {code_line}")
                        else:
                            code_lines.append(f"  {code_line}")
                    code = "\n".join(code_lines)
                break
        else:
            code = f"> {code.strip()}"
        return code, template

    def _indent(self, indent: int, text: str) -> str:
        return "\n".join(f"{' ' * indent}{line}" for line in text.splitlines())
