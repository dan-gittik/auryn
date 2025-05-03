from __future__ import annotations

import ast
import pathlib
import re

SOURCEMAP_REGEX = re.compile(r"(.*?)  # (.*?):(\d+)$")


class StopEvaluation(Exception):
    pass


class EvaluationError(Exception):

    def __init__(self, junk: Junk, error: Exception) -> None:
        self.junk = junk
        self.error = error

    def __str__(self) -> str:
        output: list[str] = [f"Failed to evaluate junk at {self.junk.source}."]
        output.append("Context:")
        if self.junk.eval_context:
            for key, value in self.junk.eval_context.items():
                output.append(f"  {key}: {value!r}")
        else:
            output.append("  <none>")
        output.append("Traceback (most recent call last):")
        traceback = self.error.__traceback__ and self.error.__traceback__.tb_next
        while traceback:
            try:
                line, template = self._parse_source(traceback.tb_frame.f_code.co_filename, traceback.tb_lineno)
            except Exception as error:
                line, template = f'? ({error})', None
            if traceback.tb_frame.f_code.co_filename == self.junk.source:
                file = "Junk"
            else:
                file = f'File "{traceback.tb_frame.f_code.co_filename}"'
            output.append(
                self._indent(2, f"{file}, line {traceback.tb_lineno}, in {traceback.tb_frame.f_code.co_name}")
            )
            output.append(self._indent(4, line))
            if template:
                template_line, template_path, template_line_number = template
                output.append(self._indent(4, f'@ File "{template_path}", line {template_line_number}'))
                output.append(self._indent(8, template_line))
            traceback = traceback.tb_next
        output.append(f"{type(self.error).__name__}: {self.error}")
        return "\n".join(output)

    def _parse_source(self, filename: str, line_number: int) -> tuple[str, tuple[str, pathlib.Path, int] | None]:
        if filename == self.junk.source:
            source = self.junk.to_string()
        else:
            path = pathlib.Path(filename)
            if not path.exists():
                raise ValueError(f"file {path} does not exist")
            source = path.read_text()
        lines = source.splitlines()
        if line_number > len(lines):
            raise ValueError(f"file {path} has only {len(lines)} lines, unable to find line {line_number}")
        line = lines[line_number - 1].strip()
        match = SOURCEMAP_REGEX.match(line)
        if match:
            line, template_path, template_line_number = match.groups()
            template_path = pathlib.Path(template_path)
            template_line_number = int(template_line_number)
            if not template_path.exists():
                raise ValueError(f"template {template_path} does not exist")
            template_lines = template_path.read_text().splitlines()
            if template_line_number > len(template_lines):
                raise ValueError(f"template {template_path} has only {len(template_lines)} lines, unable to find line {template_line_number}")
            template_line = template_lines[template_line_number - 1].strip()
            template = template_line, template_path, template_line_number
        else:
            template = None
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # end_lineno can be None in older Python versions or for certain AST nodes
                if node.end_lineno is None or not node.lineno <= line_number <= node.end_lineno:
                    continue
                block = ast.get_source_segment(source, node)
                if block:
                    block_lines: list[str] = []
                    for n, block_line in enumerate(block.splitlines()):
                        if n == line_number - node.lineno:
                            block_lines.append(f"> {block_line}")
                        else:
                            block_lines.append(f"  {block_line}")
                    line = "\n".join(block_lines)
                break
        else:
            line = f"> {line.strip()}"
        return line, template

    def _indent(self, indent: int, text: str) -> str:
        return "\n".join(f"{' ' * indent}{line}" for line in text.splitlines())


from .junk import Junk