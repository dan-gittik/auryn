from __future__ import annotations

import contextlib
import os
import pathlib
import re
import sys
import tempfile
import uuid
from typing import Any, Callable, ClassVar, Iterable, Iterator, Self

from .interpolate import interpolate as interpolate_
from .interpolate import split
from .utils import concat, crop_lines, refers_to_file

type LineTransform = Callable[[GX, str], None]
type PostProcessor = Callable[[GX], None]
type PluginArgument = str | pathlib.Path | dict[str, Any] | Iterable[PluginArgument]

MACRO_INVOCATION = re.compile(
    r"""
    ^
    ([a-zA-Z_][a-zA-Z0-9_]*)
    (?:
        (:{0,2})
        \s+
        (.*)
    )?
    $
    """,
    flags=re.VERBOSE,
)


class GX:
    """
    A generation/execution (GX) process.

        >>> gx = GX.parse('''
        ...     !for i in range(n):
        ...         line {i}
        ... ''')
        >>> gx.generate()
        >>> code = gx.to_string()
        >>> print(code)
        for i in range(n):
            emit(0, 'line ', i)
        >>> output = gx.execute(n=3)
        >>> print(output)
        line 0
        line 1
        line 2

    Attributes:
        origin: The GX definition site.
        template: The template used as generation instructions.
        code: The generated code.
        line_transforms: A map of prefixes to transformations applied to lines starting with that prefix.
        g_globals: The namespace used during generation.
        g_locals: The local namespace used during generation.
        x_globals: The namespace used during execution (since the generated code is a module, its globals and locals
            coincide).
        state: An out-of-scope stash for values that don't belong in an explicit namespace (e.g. blocks shared between
            %define and %insert or bookmarks extended with %append).
        postprocessors: Functions called after the generation to post-process it (e.g. in %extend).
        interpolation: The delimiters used for interpolation.
        inline: Whether to inline generated code or not.
        output: The execution output.
        output_indent: The current indentation of the execution output.
    """

    # Conventions:
    code_prefix: ClassVar[str] = "!"
    macro_prefix: ClassVar[str] = "%"
    comment_prefix: ClassVar[str] = "#"
    plugin_directories: ClassVar[list[pathlib.Path]] = [pathlib.Path(__file__).parent / "builtins"]
    core_plugin_name: ClassVar[str] = "core"
    generation_prefix: ClassVar[str] = "g_"
    execution_prefix: ClassVar[str] = "x_"
    on_load_name: ClassVar[str] = "on_load"
    generation_file_suffix: ClassVar[str] = ".g.py"
    execution_file_suffix: ClassVar[str] = ".x.py"

    # Defaults:
    load_core_by_default: ClassVar[bool] = True
    generate_standalone_by_default: ClassVar[bool] = False
    default_interpolation: ClassVar[str] = "{ }"
    crop_text_by_default: ClassVar[bool] = False
    interpolate_by_default: ClassVar[bool] = True

    # Runtime:
    EMIT: ClassVar[str] = "emit"
    INDENT: ClassVar[str] = "indent"
    STOP_EXECUTION: ClassVar[str] = "StopExecution"

    def __init__(
        self,
        origin: Origin,
        template: Template,
        code: Code,
    ) -> None:
        self.origin = origin
        self.template = template
        self.code = code
        self.line_transforms: dict[str, LineTransform] = {
            self.code_prefix: self.transform_code,
            self.macro_prefix: self.transform_macro,
            "": self.transform_text,  # Default line transform.
        }
        self.g_globals: dict[str, Any] = {
            "gx": self,
            "load": self._load,
        }
        self.g_locals: dict[str, Any] = {}
        self.x_globals: dict[str, Any] = {
            "gx": self,
            self.EMIT: self.emit,
            self.INDENT: self._indent,
            self.STOP_EXECUTION: StopExecution,
        }
        self.state: dict[str, Any] = {}
        self.postprocessors: list[tuple[Line, PostProcessor]] = []
        self.interpolation: str = self.default_interpolation
        self.inline: bool = False
        self.code_indent: int = 0
        self.text_indent: int = 0
        self.output: list[Any] = []
        self.output_indent = 0
        # A unique ID, used to reconstruct the GX as a source in standalone generated code.
        self.id = str(uuid.uuid4())
        # The lines currently in use by the generation.
        self._lines: list[Line] = []
        # Temporary files for dynamically executed code (so it's included in the traceback).
        self._temp_files: list[pathlib.Path] = []

    def __str__(self) -> str:
        output = ["GX"]
        if self.template.path:
            output.append(f" of {self.template.path}")
        output.append(f" at {self.origin}")
        return "".join(output)

    def __repr__(self) -> str:
        return f"<{self}>"

    def __del__(self) -> None:
        # If the GX is being deleted, then it's not part of any traceback, and we can remove its temporary files.
        for file in self._temp_files:
            file.unlink()

    @classmethod
    def add_plugins_directory(cls, directory: str | pathlib.Path) -> None:
        """
        Add a directory to the list of directories to search for plugins.

        Arguments:
            directory: The directory to add.
        """
        cls.plugin_directories.append(pathlib.Path(directory))

    @classmethod
    def parse(cls, template: TemplateArgument, *, load_core: bool | None = None, stack_level: int = 0) -> Self:
        """
        Create a generation/execution from a template.

        Arguments:
            template: The template to parse.
                If it's a template object, it's returned as is; if it's a path object or a string refering to a valid
                file, its contents are parsed; otherwise, *it* is parsed.
            load_core: Whether to load the core plugin, containing the default macros and hooks (e.g. %include and
                concat; default is GX.load_core_by_default).
            stack_level: How many frames to ascend to infer the origin.

        Returns:
            The created generation/execution.
        """
        if load_core is None:
            load_core = cls.load_core_by_default
        origin = Origin.infer(stack_level + 1)
        template = Template.parse(template)
        code = Code()
        gx = cls(origin, template, code)
        if load_core:
            gx.load(cls.core_plugin_name)
        return gx

    @classmethod
    def restore(cls, code: CodeArgument, *, stack_level: int = 0) -> Self:
        """
        Create a generation/execution from standalone generated code.

        Arguments:
            code: The standalone generated code to restore.
                If it's a code object, it's used as is; if it's a path object or a string refering to a valid
                file, its contents are restored; otherwise, *it* is restored.
            stack_level: How many frames to ascend to infer the origin.

        Returns:
            The created generation/execution.
        """
        origin = Origin.infer(stack_level + 1)
        template = Template()
        code, intro = Code.restore(code)
        gx = cls(origin, template, code)
        gx.x_exec(intro)
        return gx

    @property
    def root(self) -> pathlib.Path:
        """
        The generation/execution root directory.

        If the template is a file, it's the template's directory; otherwise, it's the origin directory.
        """
        if self.template.path:
            return self.template.path.parent
        return self.origin.path.parent

    @property
    def line(self) -> Line:
        """
        The line currently being transformed.
        """
        if not self._lines:
            raise RuntimeError(f"{self} is not in generation")
        return self._lines[-1]

    def load(self, plugin: PluginArgument) -> None:
        """
        Load additional macros and hooks into the GX.

        Arguments:
            plugin: The additional macros and hooks to load.
                If it's a string or a path object, it is imported as a module; if it's a dictionary, it is traversed; if
                it's a list, each of its items is loaded recursively.
                In any case, names starting with g_ are added to the generation namespaces, names starting with x_ are
                added to the execution namespace, and on_load is called after the plugin loads.
        """
        # If the plugin is a dictionary, use it as a namespace.
        if isinstance(plugin, dict):
            namespace = plugin
        # If the plugin is a name of a builtin, use its namespace.
        elif isinstance(plugin, str) and plugin in plugins:
            namespace = plugins[plugin]
        # If the plugin is a string or path object, import it as a module.
        elif isinstance(plugin, str | pathlib.Path):
            path = self.root / plugin
            if not path.is_file():
                # If the plugin is not a valid file, look in the plugin directories for a module of this name.
                for directory in self.plugin_directories:
                    path_ = directory / f"{plugin}.py"
                    if path_.exists():
                        path = path_
                        break
                else:
                    available_plugins = set(plugins)
                    for directory in self.plugin_directories:
                        for module in directory.glob("*.py"):
                            available_plugins.add(module.stem)
                    raise ValueError(
                        f"unable to load {plugin!r} ({path} does not exist and available plugins are "
                        f"{concat(sorted(available_plugins))})"
                    )
            # Add the directory containing the module to sys.path to allow for relative imports.
            sys_path = sys.path.copy()
            sys.path.append(str(path.parent))
            try:
                text = path.read_text()
                code = compile(text, str(path), "exec")
                namespace = {}
                exec(code, namespace)
            finally:
                sys.path = sys_path
        # If the plugin is an iterable, load each of its items recursively.
        else:
            for item in plugin:
                self.load(item)
            return
        # Finally, extract any macros and hooks from the namespace.
        for key, value in namespace.items():
            if key.startswith(self.generation_prefix):
                name = key.removeprefix(self.generation_prefix)
                self.g_globals[name] = value
            if key.startswith(self.execution_prefix):
                name = key.removeprefix(self.execution_prefix)
                self.x_globals[name] = value.__get__(self, type(self))
        # If there is an on_load function, call it.
        if self.on_load_name in namespace:
            namespace[self.on_load_name](self)

    def generate(self, context: dict[str, Any] | None = None, /, **context_kwargs: Any) -> None:
        """
        Generate code from the template.

        Arguments:
            context: Additional context to add to the generation namespace.
            **context_kwargs: Additional context to add to the generation namespace.
        """
        self.g_locals.update(**(context or {}), **context_kwargs)
        try:
            self.transform(self.template.lines)
            for line, postprocessor in self.postprocessors:
                with self._line(line):
                    postprocessor(self)
        except GenerationError:
            raise
        except Exception as error:
            raise GenerationError(self, error)

    def to_string(self, standalone: bool | None = None) -> str:
        """
        Return the generated code.

        Arguments:
            standalone: Whether the generated code should be able to run on its own (default is
                GX.generate_standalone_by_default).

        Returns:
            The generated code.
        """
        if standalone is None:
            standalone = self.generate_standalone_by_default
        return self.code.to_string(self, standalone=standalone)

    def execute(self, context: dict[str, Any] | None = None, /, **context_kwargs: Any) -> str:
        """
        Execute the generated code.

        Arguments:
            context: Additional context to add to the execution namespace.
            **context_kwargs: Additional context to add to the execution namespace.

        Returns:
            The execution output.
        """
        self.x_globals.update(**(context or {}), **context_kwargs)
        code = self.to_string()
        try:
            self.x_exec(code)
        except StopExecution:
            pass
        except ExecutionError:
            raise
        except Exception as error:
            raise ExecutionError(self, error)
        return "".join(map(str, self.output)).rstrip()

    def transform(self, lines: Lines | None = None) -> None:
        """
        Transform template lines into generated code.

        This is used in macros to continue the generation recursively:

            >>> def g_macro(gx):
            ...     # Do something...
            ...     gx.transform()
            ...     # Or, to continue with the same indentation:
            ...     gx.transform(gx.line.children.snap())

        Arguments:
            lines: The lines to transform.
                If not provided, the children of the current line are used.
        """
        if lines is None:
            lines = self.line.children
        for line in lines:
            with self._line(line):
                for prefix, transform in sorted(
                    self.line_transforms.items(),
                    key=lambda x: len(x[0]),
                    reverse=True,
                ):
                    if line.content.startswith(prefix):
                        content = line.content.removeprefix(prefix).lstrip()
                        transform(self, content)
                        break
                else:
                    transforms = [f"{func.__name__} ({prefix})" for prefix, func in self.line_transforms.items()]
                    raise ValueError(f"unable to transform {line} (considered {concat(sorted(transforms))})")

    def line_transform(self, transform: LineTransform, prefix: str = "") -> None:
        """
        Add a line transform.

        Arguments:
            transform: The line transform to add.
            prefix: The prefix the line transform will run on (no prefix makes it the default transform).
        """
        self.line_transforms[prefix] = transform

    def on_complete(self, postprocessor: PostProcessor) -> None:
        """
        Register a callback to post-process the generation after it's complete.

            >>> def g_extend(gx):
            ...     def replace_code(gx):
            ...         # Replace the code after the generation is complete
            ...     gx.on_complete(replace_code)

        Arguments:
            postprocessor: The post-processor to call.
        """
        self.postprocessors.append((self.line, postprocessor))

    def add_code(self, code: str) -> None:
        """
        Add raw generated code.

            >>> def g_macro(gx):
            ...     gx.add_code('print("hello")')

            >>> def g_macro(gx):
            ...     gx.add_code('''
            ...         try:
            ...             # Do something.
            ...         except Exception as error:
            ...             # Handle the error.
            ...     ''')

        Arguments:
            code: The raw code to add.
                Multi-line code blocks are cropped.
        """
        for _, line in crop_lines(code):
            self.code.append(self, self.line.number, self.code_indent, line)

    def increase_code_indent(self) -> None:
        """
        Increase the generated code indentation.
        """
        self.code_indent += 4

    def decrease_code_indent(self) -> None:
        """
        Decrease the generated code indentation.
        """
        self.code_indent -= 4

    @contextlib.contextmanager
    def increased_code_indent(self) -> Iterator[None]:
        """
        Temporarily increase the generated code indentation.

        This is used in macros to add code that requires indentation when generation continues recursively:

            >>> def g_macro(gx):
            ...     gx.code('with context():')
            ...     # Subsequent code should be indented to fit inside the with-statement.
            ...     with gx.increased_code_indent():
            ...         gx.transform()
        """
        self.increase_code_indent()
        try:
            yield
        finally:
            self.decrease_code_indent()

    def add_text(
        self,
        indent: int | None,
        text: str,
        crop: bool | None = None,
        interpolate: bool | None = None,
        newline: bool = True,
    ) -> None:
        """
        Generate code that emits text.

            >>> def g_macro(gx):
            ...     gx.add_text(0, 'hello')

        Arguments:
            indent: The text indentation.
            text: The text to emit.
            crop: Whether to crop the text (default is GX.crop_text_by_default).
            interpolate: Whether to interpolate the text (default is GX.interpolate_by_default).
            newline: Whether to add a newline after the text (default is True).
        """
        if crop is None:
            crop = self.crop_text_by_default
        if interpolate is None:
            interpolate = self.interpolate_by_default
        if indent is not None:
            indent += self.text_indent
        # If we need to crop the text, add each line separately.
        if crop:
            for _, line in crop_lines(text):
                self.add_text(indent, line, crop=False, interpolate=interpolate, newline=newline)
            return
        # Otherwise, interpolate if necessary and add code that calls the EMIT hook during execution, passing directives
        # on newlines and inlining via keyword arguments.
        if not interpolate:
            args = [repr(text)]
        else:
            args = []
            for snippet, is_code in interpolate_(text, self.interpolation):
                if is_code:
                    args.append(f"{snippet}")
                else:
                    args.append(repr(snippet))
        if not newline:
            args.append("newline=False")
        if self.inline:
            args.append("inline=True")
        self.add_code(f'{self.EMIT}({indent}, {", ".join(args)})')

    def interpolated(self, string: str) -> str:
        """
        Return an expression that accounts for interpolation during execution.

        This is used in macros to add text that respects interpolation:

            >>> def g_macro(gx):
            ...     # Suppose we call execute with name='world':
            ...     gx.code('print("hello {name}")')
            ...     # Will be printed as-is: hello {name}
            ...     # To make sure interpolation takes effect, we need to pass it through interpolated first:
            ...     gx.code(f'print({gx.interpolated("hello, {name}")})'
            ...     # This produces print(concat('hello, ', name)), which results in: hello world

        Arguments:
            string: The string to be interpolated.

        Returns:
            An expression that accounts for interpolation during execution.
        """
        args = []
        for snippet, is_code in interpolate_(string, self.interpolation):
            if is_code:
                args.append(snippet)
            else:
                args.append(repr(snippet))
        if len(args) == 1:
            return f"s({args[0]})"
        return f"s({', '.join(args)})"

    def resolve_template(self, template: TemplateArgument) -> Template:
        """
        Resolve a template relative to the root directory.

        This is used in macros to interpolate template paths and position them relative to the root directory (if
        they're files), or pass them as-is (if they're strings).

            >>> def g_render(gx, template):
            ...     template = gx.resolve_template(template)
            ...     output = execute(template)
            ...     gx.add_text(0, output, crop=True)

        Arguments:
            template: The template to resolve.

        Returns:
            The resolved template.
        """
        if isinstance(template, Template):
            return template
        if refers_to_file(template):
            template = self.root / self.g_interpolate(str(template))
        return Template.parse(template)

    def derive(self, template: TemplateArgument, continue_generation: bool = False) -> GX:
        """
        Create a new generation/execution based on this one.

            >>> def g_include(gx, template):
            ...     new_gx = gx.derive(template)
            ...     new_gx.generate()
            ...     gx.extend(new_gx)

        Arguments:
            template: The template of the new generation/execution.
                If it's a template object, it's used as is; if it's a path object or a string refering to a valid file,
                its contents are parsed; otherwise, *it* is parsed.
            continue_generation: Whether to carry over the current line transforms and generation namespace (default is
                False); note that the generation state is always shared.

        Returns:
            The new generation/execution.
        """
        origin = Origin.derive(self)
        template = self.resolve_template(template)
        code = Code()
        gx = type(self)(origin, template, code)
        gx.state = self.state
        if continue_generation:
            gx.line_transforms = self.line_transforms
            gx.g_globals = self.g_globals.copy()
            gx.g_globals["gx"] = gx
            gx.g_locals = self.g_locals.copy()
        return gx

    def extend(self, gx: GX) -> None:
        """
        Extend the generated code with generated code from another generation/execution.

            >>> def g_include(gx, template):
            ...     new_gx = gx.derive(template)
            ...     new_gx.generate()
            ...     gx.extend(new_gx)

        Arguments:
            gx: The generation/execution to extend the generated code with.
        """
        for line in gx.code.lines:
            self.code.append(line.gx, line.template_line_number, self.code_indent + line.indent, line.content)

    @contextlib.contextmanager
    def patch(self, **attributes: Any) -> Iterator[None]:
        """
        Temporarily patch arbitrary GX attributes.

        This is used in macros and hooks to change, capture or suspend GX configurations:

            >>> def g_interpolate(gx, delimiters):
            ...     # Continue the generation with a different interpolation delimiters:
            ...     with gx.patch(interpolation=delimiters):
            ...         gx.transform()

            >>> @contextlib.contextmanager
            ... def x_assign(gx):
            ...     # Capture the execution output into a different list:
            ...     output = []
            ...     with gx.patch(output=output):
            ...         yield output

        Arguments:
            **attributes: The attributes to patch.
        """
        prev_attributes: dict[str, Any] = {}
        for key, value in attributes.items():
            prev_attributes[key] = getattr(self, key)
            setattr(self, key, value)
        try:
            yield
        finally:
            for key, value in prev_attributes.items():
                setattr(self, key, value)

    def g_interpolate(self, text: str) -> str:
        """
        Interpolate a string in the generation namespace.

        Arguments:
            text: The text to interpolate.

        Returns:
            The interpolated text.
        """
        # Evaluate the text as an f-string in the generation namespace.
        return self.g_eval(f"f{text!r}")

    def g_eval(self, code: str) -> Any:
        """
        Evaluate code during generation.

        Arguments:
            code: The code to evaluate.

        Returns:
            The result of the evaluation.
        """
        return self._execute(self.generation_file_suffix, code, self.g_globals, self.g_locals, expression=True)

    def g_exec(self, code: str) -> None:
        """
        Execute code during generation.

        Arguments:
            code: The code to execute.
        """
        self._execute(self.generation_file_suffix, code, self.g_globals, self.g_locals)

    def x_interpolate(self, text: str) -> str:
        """
        Interpolate a string in the execution namespace.

        Arguments:
            text: The text to interpolate.

        Returns:
            The interpolated text.
        """
        # Evaluate the text as an f-string in the execution namespace.
        return self.x_eval(f"f{text!r}")

    def x_eval(self, code: str) -> Any:
        """
        Evaluate code during execution.

        Arguments:
            code: The code to evaluate.

        Returns:
            The result of the evaluation.
        """
        return self._execute(self.execution_file_suffix, code, self.x_globals, expression=True)

    def x_exec(self, code: str) -> None:
        """
        Execute code during execution.

        Arguments:
            code: The code to execute.
        """
        self._execute(self.execution_file_suffix, code, self.x_globals)

    def emit(
        self,
        indent: int | None,
        *args: Any,
        inline: bool = False,
        newline: bool = True,
    ) -> None:
        """
        Emit output during execution.

        This is called when generated code invokes the EMIT hook; on its own, it can be used in hooks to emit additional
        output:

            >>> def x_hook(gx):
            ...     gx.emit(0, "hello")

        Arguments:
            indent: The indentation of the output.
            *args: The values to emit.
            inline: Whether to emit the output inline (default is False).
            newline: Whether to emit a newline after the output (default is True).
        """
        text = "".join(map(str, args))
        if inline:
            self.output.append(text)
        else:
            end = "\n" if newline else ""
            # indent=None signifies no indentation (used when inlining).
            if indent is None:
                indent = 0
            # Otherwise (even if indent=0), add the current output indentation.
            else:
                indent += self.output_indent
            self.output.append(f'{" " * indent}{text}{end}')

    def _execute(
        self,
        suffix: str,
        text: str,
        globals: dict[str, Any],
        locals: dict[str, Any] | None = None,
        *,
        expression: bool = False,
    ) -> Any:
        # Before executing code, write it to a temporary file to make sure it's available in tracebacks.
        if self.template.path:
            name = self.template.path.stem
        else:
            name = f"{self.origin.path.stem}-{self.origin.line_number}"
        fd, name = tempfile.mkstemp(suffix=f".{name}{suffix}")
        os.close(fd)
        path = pathlib.Path(name)
        path.write_text(text)
        # Collect any temporary files, to be removed when the GX is deleted.
        self._temp_files.append(path)
        code = compile(text, str(path), "eval" if expression else "exec")
        if expression:
            return eval(code, globals, locals)
        else:
            exec(code, globals, locals)

    @contextlib.contextmanager
    def _indent(self, indent: int) -> Iterator[None]:
        self.output_indent += indent
        try:
            yield
        finally:
            self.output_indent -= indent

    @contextlib.contextmanager
    def _line(self, line: Line) -> Iterator[None]:
        self._lines.append(line)
        try:
            yield
        # In case of an error, keep the current line available for the traceback.
        except Exception:
            raise
        else:
            self._lines.pop()

    # Since line transforms and macros can be defined separately in plugins, they are invoked with the GX object as the
    # first argument; as such, they shouldn't be implicitly bound, and are defined as static methods instead.

    @staticmethod
    def transform_text(gx: GX, content: str) -> None:
        """
        Generate a text line.

            >>> execute('''
            ...     hello world
            ... ''')

        Arguments:
            gx: The generation/execution.
            content: The line content.
        """
        if content:
            gx.add_text(gx.line.indent, content)
        gx.transform()

    @staticmethod
    def transform_code(gx: GX, content: str) -> None:
        """
        Generate a code line.

            >>> execute('''
            ...     !x = 1
            ... ''')

            >>> # Code block:
            >>> execute('''
            ...     !
            ...         def f():
            ...             return 1
            ... ''')

            >>> # Comments:
            >>> execute('''
            ...     !# This is a comment
            ...     !#
            ...         This is a comment
            ...         with multiple lines
            ... ''')

        Arguments:
            gx: The generation/execution.
            content: The line content.
        """
        # Ignore comment lines or blocks.
        if content.startswith(gx.comment_prefix):
            return
        # If the content is empty, this is a code block: add its contents as-is.
        if not content:
            code = gx.line.children.to_string()
            gx.add_code(code)
            return
        # Otherwise, this is a code line. Previous code lines should have discarded any indentation significant to the
        # code itself, so any remaining indentation is to be applied during execution.
        indent = gx.line.indent
        if indent:
            gx.add_code(f"with {gx.INDENT}({indent}):")
            gx.increase_code_indent()
        gx.add_code(content)
        # Indentation significant to the code is managed explicitly, so children indentation is discarded entirely.
        with gx.increased_code_indent():
            gx.transform(gx.line.children.snap(0))
        if indent:
            gx.decrease_code_indent()

    @staticmethod
    def transform_macro(gx: GX, content: str) -> None:
        """
        Generate a macro line.

            >>> # 0-1 arguments are passed as text by default; multiple arguments can be passed with : (space-delimited)
            ... # or :: (as-is).
            >>> execute('''
            ...     %macro                             # macro(gx)
            ...     %macro text                        # macro(gx, 'text')
            ...     %macro: 'text' x=1                 # macro(gx, 'text', x=1)
            ...     %macro:: 'text', x=1, xs=[1, 2, 3] # macro(gx, 'text', x=1, xs=[1, 2, 3])
            ... ''')

            >>> # Macro code (evaluated in the generation namespace):
            >>> execute('''
            ...     %!for x in xs:      # code line with children
            ...         %!y = x         # code line without children
            ...         %!              # code block
            ...             def f():
            ...                 return x
            ... ''', g_xs=[1, 2, 3])

            >>> # Explicit empty line (empty lines do not appear in the output by default):
            >>> output = execute('''
            ...     line 1
            ...             # omitted
            ...     line 2
            ...     %       # emitted
            ...     line 3
            ... ''')
            >>> print(output)
            line 1
            line 2

            line 3

        Arguments:
            gx: The generation/execution.
            content: The line content.
        """
        # If the content is empty, it means there should be an empty line of output, so we emit empty text.
        if not content:
            gx.add_text(0, "")
            return
        # If the content starts with the code prefix, this is code to execute during generation.
        if content.startswith(gx.code_prefix):
            code = content.removeprefix(gx.code_prefix).lstrip()
            # If the code is empty, this is a code block: execute its contents as-is.
            if not code:
                code = gx.line.children.snap(0).to_string()
                gx.g_exec(code)
                return
            # Otherwise, this is a code line. If it has no children, execute it as-is.
            if not gx.line.children:
                gx.g_exec(code)
                return
            # Otherwise, execute it with a nested transform invocation, so generation continues recursively.
            code += "\n    gx.transform(gx.line.children.snap())"
            gx.g_exec(code)
            return
        # Otherwise, this is a macro invocation.
        match = MACRO_INVOCATION.match(content)
        if not match:
            raise ValueError(
                f"expected macro on {gx.line} to be '<macro> [argument]', '<macro>: <arguments>' or "
                f"'<macro>:: <arguments>', but got {content!r}"
            )
        name, invocation_type, arg = match.groups()
        # Collect all the macros available in this scope.
        macros = {name for name, value in gx.g_globals.items() if callable(value)}
        macros |= {name for name, value in gx.g_locals.items() if callable(value)}
        if name not in macros:
            raise ValueError(f"unknown macro {name!r} on {gx.line} (available macros are {concat(sorted(macros))})")
        # There are three ways to call macros:
        # 1. <macro> [argument] - called with 0-1 arguments, passed in as a string;
        # 2. <macro>: <arguments> - called with arguments split by whitespace, respecting quoted strings;
        # 3. <macro>:: <arguments> - called with arguments as-is.
        if not arg:
            code = f"{name}(gx)"
        elif not invocation_type:
            code = f"{name}(gx, {arg!r})"
        elif invocation_type == ":":
            code = f"{name}(gx, {', '.join(split(arg))})"
        else:  # invocation_type == "::"
            code = f"{name}(gx, {arg})"
        gx.g_exec(code)

    @staticmethod
    def _load(gx: GX, plugin: PluginArgument) -> None:
        gx.load(plugin)


from .code import Code, CodeArgument
from .errors import ExecutionError, GenerationError, StopExecution
from .origin import Origin
from .plugins import plugins
from .template import Line, Lines, Template, TemplateArgument
