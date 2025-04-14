import re

LINE_REGEX = re.compile(r"^(\s*)(.*)$")


def trim(string: str) -> list[str]:
    indent = None
    output = []
    for number, line in enumerate(string.rstrip().expandtabs().splitlines(), 1):
        if not line.strip():
            continue
        if indent is None:
            if not (match := LINE_REGEX.match(line)):
                continue
            whitespace, content = match.groups()
            indent = len(whitespace)
            output.append(content)
            continue
        prefix = line[:indent]
        if prefix and not prefix.isspace():
            raise ValueError(f"expected line {number} to start with {indent!r} spaces, " f"but got {prefix!r}")
        output.append(line[indent:])
    return output
