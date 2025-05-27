from typing import Any

from .code import CodeArgument
from .gx import GX, PluginArgument
from .template import TemplateArgument


def generate(
    template: TemplateArgument,
    context: dict[str, Any] | None = None,
    /,
    *,
    load: PluginArgument | None = None,
    load_core: bool | None = None,
    standalone: bool | None = None,
    stack_level: int = 0,
    **context_kwargs: Any,
) -> str:
    """
    Generate code from a template.

        >>> code = generate('''
        ...     !for i in range(n):
        ...         line {i}
        ... ''')
        >>> print(code)
        for i in range(n):
            emit(0, 'line ', i)

    Arguments:
        template: The template used as generation instructions.
            If it's a template object, it's used as is; if it's a path object or a string refering to a valid file, its
            contents are parsed; otherwise, *it* is parsed.
        context: Additional context to add to the generation namespace.
        load: Additional plugins to load into the generation.
            If it's a string or a path object, it's loaded as a module; if it's a dictionary, it's traversed; if it's a
            list, each item is loaded recursively.
            In any case, names starting with g_ are added to the generation namespace, and on_load is called after the
            plugin loads.
        load_core: Whether to load the core plugin, containing the default macros and hooks (e.g. %include and concat;
            default is GX.load_core_by_default).
        standalone: Whether the generated code should be able to run on its own.
        stack_level: How many frames to ascend to infer the origin.
        **context_kwargs: Additional context to add to the generation namespace.

    Returns:
        The generated code.
    """
    gx = GX.parse(template, load_core=load_core, stack_level=stack_level + 1)
    if load:
        gx.load(load)
    gx.generate(context, **context_kwargs)
    return gx.to_string(standalone=standalone)


def execute(
    template: TemplateArgument,
    context: dict[str, Any] | None = None,
    /,
    *,
    load: PluginArgument | None = None,
    load_core: bool | None = None,
    stack_level: int = 0,
    **context_kwargs: Any,
) -> str:
    """
    Generate code from a template and execute it.

        >>> output = execute('''
        ...     !for i in range(n):
        ...         line {i}
        ... ''', n=3)
        >>> print(output)
        line 0
        line 1
        line 2

    Arguments:
        template: The template used as generation instructions.
            If it's a template object, it's used as is; if it's a path object or a string refering to a valid file, its
            contents are parsed; otherwise, *it* is parsed.
        context: Additional context to add to the generation and execution namespaces.
            Names starting with g_ are added to the generation namespace; the rest are added to the execution namespace.
        load_core: Whether to load the core plugin, containing the default macros and hooks (e.g. %include and concat;
            default is GX.load_core_by_default).
        load: Additional plugins to load into the generation and execution.
            If it's a string or a path object, it's loaded as a module; if it's a dictionary, it's traversed; if it's a
            list, each item is loaded recursively.
            In any case, names starting with g_ are added to the generation namespaces, names starting with x_ are added
            to the execution namespace, and on_load is called after the plugin loads.
        stack_level: How many frames to ascend to infer the GX origin.
        **context_kwargs: Additional context to add to the generation and execution namespaces.
            Names starting with g_ are added to the generation namespace; the rest are added to the execution namespace.

    Returns:
        The runtime output.
    """
    g_context: dict[str, Any] = {}
    x_context: dict[str, Any] = {}
    for key, value in {**(context or {}), **context_kwargs}.items():
        if key.startswith("g_"):
            key = key.removeprefix("g_")
            g_context[key] = value
        else:
            x_context[key] = value
    gx = GX.parse(template, load_core=load_core, stack_level=stack_level + 1)
    if load:
        gx.load(load)
    gx.generate(g_context)
    return gx.execute(x_context)


def execute_standalone(
    code: CodeArgument,
    context: dict[str, Any] | None = None,
    /,
    stack_level: int = 0,
    **context_kwargs: Any,
) -> str:
    """
    Execute standalone generated code.

        >>> code = generate('''
        ...     !for i in range(n):
        ...         line {i}
        ... ''', standalone=True)
        >>> output = execute_standalone(code, n=3)
        >>> print(output)
        line 0
        line 1
        line 2

    Arguments:
        code: The standalone generated code.
            If it's an code object, it's used as is; if it's a path object or a string refering to a valid file, its
            contents are restored; otherwise, *it* is restored.
        context: Additional context to add to the execution namespace.
        stack_level: How many frames to ascend to infer the origin.
        **context_kwargs: Additional context to add to the execution namespace.

    Returns:
        The execution output.
    """
    gx = GX.restore(code, stack_level=stack_level + 1)
    return gx.execute(context, **context_kwargs)
