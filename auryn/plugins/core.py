import contextlib
import pathlib
from typing import Any, Iterator

from ..code import Code
from ..gx import GX
from ..template import Lines, TemplateArgument
from ..utils import concat

UNDEFINED = object()
DEFINITIONS = "definitions"
PARAMETERS = "parameters"
BOOKMARKS = "bookmarks"


def g_eval(gx: GX, code: str) -> None:
    """
    Generate code evaluated from the generation namespace.

        >>> code = generate('''
        ...     %!for i in range(n):
        ...         %eval x = {i}
        ... ''', n=3)
        >>> print(code)
        x = 0
        x = 1
        x = 2

    Arguments:
        code: The code to generate.
    """
    code = gx.g_interpolate(code)
    gx.add_code(code)
    # If the code has any children, they should be indented inside it.
    with gx.increased_code_indent():
        gx.transform(gx.line.children.snap())


def g_emit(gx: GX, text: str) -> None:
    """
    Emit text evaluated from the generation namespace.

        >>> output = execute('''
        ...     %!for i in range(n):
        ...         %emit line {i}
        ... ''', g_n=3)
        >>> print(output)
        line 0
        line 1
        line 2

    Arguments:
        text: The text to emit.
    """
    text = gx.g_interpolate(text)
    gx.add_text(gx.line.indent, text)
    gx.transform()


def x_s(gx: GX, *args: Any) -> str:
    """
    Convert multiple values into a string (used by GX.interpolated).
    """
    return "".join(map(str, args))


def g_include(
    gx: GX,
    template: TemplateArgument,
    *,
    load: str | pathlib.Path | dict[str, Any] | None = None,
    load_core: bool | None = None,
    generate: bool = True,
    interpolate: bool = True,
    continue_generation: bool = False,
) -> None:
    """
    Emit the text or generated code of another template.

        >>> open("template", "w").write("!n = 3")
        >>> output = execute('''
        ...     %include template
        ...     !for i in range(n):
        ...         line {i}
        ... ''')
        >>> print(output)
        line 0
        line 1
        line 2

    %include macros must not have children.

    Arguments:
        template: The template to include.
            If it's a template object, it's returned as is; if it's a path object or a string refering to a valid file,
            its contents are parsed; otherwise, *it* is parsed.
        load: Additional plugins to load into the generation and execution.
            If it's a string or a path object, it is imported as a module; if it's a dictionary, it is traversed; if
            it's a list, each of its items is loaded recursively.
            In any case, names starting with g_ are added to the generation namespaces, names starting with x_ are added
            to the execution namespace, and on_load is called after the plugin loads.
        load_core: Whether to load the core plugin, containing the default macros and hooks (e.g. %include and concat;
            default is GX.load_core_by_default).
        generate: Whether to include generated code, or just the template text (default is True).
        interpolate: Whether to interpolate the template text (default is True); if generate=True, this is ignored.
        continue_generation: Whether to carry over the current line transforms and generation namespace (default is
            False); note that the generation state is always shared.
    """
    if load_core is None:
        load_core = gx.load_core_by_default
    if gx.line.children:
        raise RuntimeError("%include macro must not have children")
    if not generate:
        template = gx.resolve_template(template)
        gx.add_text(gx.line.indent, template.text, crop=True, interpolate=interpolate)
        return
    included_gx = gx.derive(template, continue_generation=continue_generation)
    if load_core:
        included_gx.load(gx.core_plugin_name)
    if load:
        included_gx.load(load)
    included_gx.template.lines.snap(gx.line.indent)
    included_gx.generate(gx.g_locals)
    gx.extend(included_gx)


def g_define(gx: GX, name: str) -> None:
    """
    Define a new block, to be inserted later with %insert.

        >>> output = execute('''
        ...     %define block
        ...         inside
        ...     before
        ...     %insert block
        ...     after
        ... ''')
        >>> print(output)
        before
        inside
        after

    This is particularly useful with %extend:

        >>> open("base", "w").write('''
        ... <html>
        ...     <head>
        ...         %insert head
        ...     <body>
        ...         %insert body
        ...     </body>
        ... </html>
        ... '''.strip())
        >>> output = execute('''
        ...     %extend base
        ...     %define head
        ...         <title>title</title>
        ...     %define body
        ...         <p>content</p>
        ... ''')
        >>> print(output)
        <html>
            <head>
                <title>title</title>
            </head>
            <body>
                <p>content</p>
            </body>
        </html>

    Arguments:
        name: The block name.
    """
    definitions: dict[str, Lines] = gx.state.setdefault(DEFINITIONS, {})
    definitions[name] = gx.line.children


def g_ifdef(gx: GX, name: str) -> None:
    """
    Transform children only if the block is defined.

        >>> output = execute('''
        ...     %define content
        ...         content
        ...     %ifdef title
        ...         <h1>
        ...             %insert title
        ...         </h1>
        ...     %ifdef content
        ...         <p>
        ...             %insert content
        ...         </p>
        ... ''')
        >>> print(output)
        <p>
            content
        </p>

    %ifdef macros must have children.

    Arguments:
        name: The block name.
    """
    if not gx.line.children:
        raise RuntimeError("%ifdef macro must have children")
    if name in gx.state.get(DEFINITIONS, {}):
        gx.transform(gx.line.children.snap())


def g_ifndef(gx: GX, name: str) -> None:
    """
    Transform children only if the block is not defined.

    See g_ifdef for an example. %ifndef macros must have children.

    Arguments:
        name: The block name.
    """
    if not gx.line.children:
        raise RuntimeError("%ifndef macro must have children")
    if name not in gx.state.get(DEFINITIONS, {}):
        gx.transform(gx.line.children.snap())


def g_insert(gx: GX, name: str, required: bool = False) -> None:
    """
    Insert a block previously defined with %define.

    See g_define for an example. If an %insert macro has children, they are transformed as its default content if the
    specified block is missing; if required=True, an error is raised, and the %insert macro must not have children.

        >>> output = execute('''
        ...     %insert block
        ...         default
        ... ''')
        >>> print(output)
        default

    Arguments:
        name: The name of the block to insert.
        required: Whether the block is required (default is False).
    """
    if required and gx.line.children:
        raise RuntimeError("%insert macro must not have children when required=True")
    definitions: dict[str, Lines] = gx.state.get(DEFINITIONS, {})
    if name in definitions:
        gx.transform(definitions[name].snap(gx.line.indent))
    else:
        if required:
            raise ValueError(
                f"missing required definition {name!r} on {gx.line} "
                f"(available definitions are {concat(sorted(definitions))})"
            )
        gx.transform(gx.line.children.snap())


def g_extend(gx: GX, template: TemplateArgument) -> None:
    """
    Use the blocks defined in this template to extend another template.

    See g_define for an example. If %extend has children, they are transformed for block definitions and replaced with
    the extending template, rather than the entire original template being replaced.

        >>> open("head", "w").write('''
        ... <head>
        ...     <meta charset="utf-8">
        ...     %insert head
        ... </head>
        ... '''.strip())
        >>> output = execute('''
        ...     <html>
        ...         %extend head
        ...             %define head
        ...                 <title>title</title>
        ...     </html>
        ... ''')
        >>> print(output)
        <html>
            <head>
                <meta charset="utf-8">
                <title>title</title>
            </head>
        </html>

    Arguments:
        template: The extending template.
    """
    if gx.line.children:
        # The children are only transformed for block definitions, so we don't want them as part of the generated code.
        with gx.patch(code=Code()):
            gx.transform(gx.line.children.snap())
        # This way, there's nothing to replace; it's enough to include the extending template, as blocks are defined
        # in a shared state and will be available for it to insert. We only need to remove the children, since include
        # macros shouldn't have any.
        gx.line.children = Lines()
        g_include(gx, template)
        return

    def replace_code(gx: GX) -> None:
        # The IR so far was only transformed for block definitions, so we can discard it and include the extending
        # template instead; blocks are defined in a shared state and will be available for it to insert.
        gx.code = Code()
        gx.code_indent = 0
        g_include(gx, template)

    # Wait until the generation is complete so all the blocks are defined.
    gx.on_complete(replace_code)


def g_interpolate(gx: GX, delimiters: str) -> None:
    """
    Set the interpolation delimiters.

    If %interpolate has children, the new delimiters only apply to them; otherwise, they apply for the rest of the
    template:

        >>> output = execute('''
        ...     {x}
        ...     <x>
        ...     %interpolate < >
        ...     {x}
        ...     <x>
        ... ''', x=1
        >>> print(output)
        1
        <x>
        {x}
        1

        >>> output = execute('''
        ...     %interpolate < >
        ...         {x}
        ...         <x>
        ...     {x}
        ...     <x>
        ... ''', x=1)
        >>> print(output)
        {x}
        1
        1
        <x>

    Arguments:
        delimiters: The interpolation delimiters.
    """
    if gx.line.children:
        with gx.patch(interpolation=delimiters):
            gx.transform(gx.line.children.snap())
    else:
        gx.interpolation = delimiters


def g_raw(gx: GX) -> None:
    """
    Emit text without transforming or interpolating it.

    If %raw has children, only they are emitted; otherwise, the rest of the template is emitted:

        >>> output = execute('''
        ...     %raw
        ...         !for i in range(n):
        ...             line {i}
        ... ''')
        >>> print(output)
        !for i in range(n):
            line {i}
    """
    if gx.line.children:
        # Emit the children only.
        text = gx.line.children.snap().to_string()
        gx.add_text(gx.line.indent, text, crop=True, interpolate=False)
    else:
        # Remove all the line transforms, and set the default to a pass-through.
        gx.line_transforms.clear()
        gx.line_transform(no_transform)


def no_transform(gx: GX, content: str) -> None:
    gx.add_code(f"{gx.EMIT}({gx.line.indent}, {content!r})")
    gx.transform()


def g_stop(gx: GX) -> None:
    """
    Stop the execution.

        >>> output = execute('''
        ...     happens
        ...     %stop
        ...     doesn't happen
        ... ''')
        >>> print(output)
        happens

    %stop macros must not have children.
    """
    gx.add_code(f"raise {gx.STOP_EXECUTION}()")


def g_param(gx: GX, name: str, default: Any = UNDEFINED) -> None:
    """
    Request a parameter to be passed to the execution.

    This raises a more informative error if the parameter is missing, or allows setting a default value for it.

        >>> output = execute('''
        ...     %param n
        ...     !for i in range(n):
        ...         line {i}
        ... ''')
        Failed to execute GX at <module>:1: missing parameter 'n'

        >>> output = execute('''
        ...     %param n 3
        ...     !for i in range(n):
        ...         line {i}
        ... ''')
        >>> print(output)
        line 0
        line 1
        line 2

    It also allows to inspect the expected parameters before execution:

        >>> gx = GX.from_template('''
        ...     %param x
        ...     %param y 1
        ... ''')
        >>> gx.generate()
        >>> print(gx.parameters)
        {'x': '<required>', 'y': 1}

    %param macros must not have children.

    Arguments:
        name: The parameter name.
        default: The default value.
    """
    if gx.line.children:
        raise RuntimeError("%param macro must not have children")
    parameters: dict[str, Any] = gx.state.setdefault(PARAMETERS, {})
    parameters[name] = default if default is not UNDEFINED else "<required>"
    if default is UNDEFINED:
        # To detect a missing required parameter, look in globals().
        message = f"missing required parameter {name!r}"
        gx.add_code(
            f"""
            if {name!r} not in globals():
                raise ValueError({message!r})
            """
        )
    else:
        # To assign a default value to a missing optional parameter, try to resolve it and set it on NameError.
        gx.add_code(
            f"""
            try:
                {name}
            except NameError:
                {name} = {default!r}
            """
        )


def g_inline(gx: GX) -> None:
    """
    Emit text inline (without newlines).

    If %inline has children, only they are transformed like this; otherwise, the rest of the template is.

        >>> output = execute('''
        ...     %inline
        ...         {name}(
        ...             !for arg in args.items():
        ...                 {arg},
        ...             )
        ... ''', name="f", args=[1, 2, 3])
        >>> print(output.strip())
        f(1, 2, 3,)

    See %strip on how to remove the trailing comma.
    """
    if gx.line.children:
        # First, emit the indent of the current line (with no newline).
        gx.add_text(gx.line.indent, "", newline=False)
        # Then, transform the children inline.
        with gx.patch(inline=True):
            gx.transform()
        # Finally, emit a newline.
        with gx.patch(inline=False):
            gx.add_text(None, "")
    else:
        gx.inline = True


def g_strip(gx: GX, suffix: str) -> None:
    """
    Remove a suffix from the last execution line.

    This can be used to e.g. remove trailing commas from inlined code:

        >>> output = execute('''
        ...     %inline
        ...         {name}(
        ...             !for arg in args.items():
        ...                 {arg},
        ...             %strip ,
        ...             )
        ... ''', name="f", args=[1, 2, 3])
        >>> print(output.strip())
        f(1, 2, 3)

    Arguments:
        suffix: The suffix to remove.
    """
    # Since we don't know what the execution output will be until it's running, we have to do this in a hook.
    gx.add_code(f"strip({suffix!r})")


def x_strip(gx: GX, suffix: str) -> None:
    """
    The corresponding hook to the %strip macro.
    """
    if not gx.output:
        return
    gx.output[-1] = gx.output[-1].rstrip().rstrip(suffix)


def g_assign(gx: GX, name: str) -> None:
    """
    Assign the execution output to a variable.

        >>> output = execute('''
        ...     %assign x
        ...         !for i in range(n):
        ...             line {i}
        ...     open("output.txt", "w").write(x)
        ... ''')
        >>> print(output)
        ''
        >>> print(open("output.txt").read())
        line 0
        line 1
        line 2

    %assign macros must have children.

    Arguments:
        name: The variable name.
    """
    if not gx.line.children:
        raise RuntimeError("%assign macro must have children")
    # Add a hook to temporary redirect the execution output into _.
    gx.add_code("with assign() as _:")
    with gx.increased_code_indent():
        gx.transform(gx.line.children.snap())
    # Assign the concatenated results to the variable.
    gx.add_code(f"{name} = ''.join(_).strip()")


@contextlib.contextmanager
def x_assign(gx: GX) -> Iterator[list[str]]:
    """
    The corresponding hook to the %assign macro.
    """
    output: list[str] = []
    with gx.patch(output=output):
        yield output


class Bookmark:

    def __init__(self, indent: int) -> None:
        self.indent = indent
        self.lines: list[Any] = []

    def __str__(self) -> str:
        return "".join(map(str, self.lines))


def g_bookmark(gx: GX, name: str) -> None:
    """
    Insert a bookmark into which additional code can be generated later on with %append.

        >>> output = execute('''
        ...     %bookmark b
        ...     after
        ...     !for i in range(n):
        ...         %append b
        ...             line {i}
        ... ''', n=3)
        >>> print(output)
        line 0
        line 1
        line 2
        after

    Bookmark children are transformed as its initial content.

    Arguments:
        name: The bookmark name.
    """
    if gx.line.children:
        gx.transform(gx.line.children.snap())
    # Add a hook to define a bookmark into which the %append hook will inject output.
    gx.add_code(f"bookmark({gx.interpolated(name)}, {gx.line.indent})")


def x_bookmark(gx: GX, name: str, indent: int) -> None:
    """
    The corresponding hook to the %bookmark macro.

    Arguments:
        name: The bookmark name.
        indent: The indent at which the bookmark is created.
    """
    bookmark = Bookmark(indent)
    bookmarks: dict[str, Bookmark] = gx.state.setdefault(BOOKMARKS, {})
    bookmarks[name] = bookmark
    # Add the bookmark object to the output; when concatenated, it will be converted to a string containing all the
    # content that was appended to it.
    gx.output.append(bookmark)


def g_append(gx: GX, name: str) -> None:
    """
    Append children to a bookmark.

    See g_bookmark for an example. %append macros must have children.

    Arguments:
        name: The name of the bookmark to append to.
    """
    if not gx.line.children:
        raise RuntimeError("%append macro must have children")
    # Add a hook to temporarily redirect the execution output into the bookmark.
    gx.add_code(f"with append({gx.interpolated(name)}, {str(gx.line)!r}):")
    with gx.increased_code_indent():
        gx.transform(gx.line.children.snap(0))


@contextlib.contextmanager
def x_append(gx: GX, name: str, line: str) -> Iterator[None]:
    """
    The corresponding hook to the %append macro.

    Arguments:
        name: The name of the bookmark to append to.
    """
    bookmarks: dict[str, Bookmark] = gx.state.get(BOOKMARKS, {})
    if name not in bookmarks:
        raise ValueError(
            f"missing bookmark {name!r} referenced on {line} (available bookmarks are {concat(sorted(bookmarks))})"
        )
    bookmark = bookmarks[name]
    with gx.patch(output=bookmark.lines, output_indent=bookmark.indent):
        yield


def x_camel_case(gx: GX, name: str) -> str:
    """
    Convert a name from snake_case to CamelCase.

        >>> output = execute('''
        ...     class {camel_case(name)}:
        ...         pass
        ... ''', name="class_name")
        >>> print(output)
        class ClassName:
            pass

    Arguments:
        name: The name to convert.
    """
    return "".join(word.capitalize() for word in name.split("_"))
