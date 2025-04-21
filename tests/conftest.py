import inspect

from auryn.utils import split_line


def trim(text: str) -> str:
    text = text.lstrip("\n").rstrip()
    indent: int | None = None
    output: list[str] = []
    for line in text.splitlines():
        if indent is None:
            indent, content = split_line(line)
            output.append(content)
        else:
            output.append(line[indent:])
    return "\n".join(output)


def this_line(offset: int = 0) -> int:
    frame = inspect.currentframe()
    frame = frame and frame.f_back
    if not frame:
        raise RuntimeError("unable to infer source")
    return frame.f_lineno + offset