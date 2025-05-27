# Auryn

A metaprogramming engine for extensible templating and code generation.

- [Installation](#installation)
- [Quickstart](#quickstart)
- [Macros](#macros)
- [Filesystem Macros](#filesystem-macros)
- [Advanced Syntax](#advanced-syntax)
- [Plugin Development](#plugin-development)
- [Understanding Errors](#understanding-errors)
- [CLI](#cli)
- [Local Development](#local-development)
- [License](#license)

![Auryn Logo](auryn.png)

## Installation

**Requires Python > 3.12.**

From PyPI:

```sh
$ pip install auryn
...
```

From source:

```sh
$ git clone git@github.com:dan-gittik/auryn.git
$ cd auryn/
$ poetry install
...
```

The project is pure Python and has no dependencies.

## Quickstart

Auryn works in two phases:

1. **Generation**: generate code according to given a **template**;
2. **Execution**: run the **generated code** to produce an **output**.

Templates are parsed by lines, where each line can be:

1. **text**: emitted as output after **interpolation**;
2. **code** (`!` prefix): runs during execution;
3. **macro** (`%` prefix): runs during generation.

For example:

```pycon
>>> from auryn import execute

>>> output = execute('''
...     !for i in range(n):
...         line {i}
... ''', n=3)
line 0
line 1
line 2
```

`!for i in range(n):` is a code line; it becomes part of the generated code, and will run during execution (with `n=3`).
`line {i}` is a text line; it is emitted as output, so the code it generates is one that emits `'line ', i`. To see that
code for ourselves, we can call `generate` to perform the generation phase only:

```pycon
>>> from auryn import generate

>>> code = generate('''
...     !for i in range(n):
...         line {i}
... ''')
>>> print(code)
for i in range(n):
    emit(0, 'line ', i)
```

We can thus split the two phases: generate code at one time, and execute it later (e.g. to improve
performance). To do that, we generate the code with `standalone=True`, then use `execute_standalone`:

```pycon
>>> from auryn import execute_standalone
>>> code = generate('''
...     !for i in range(n):
...         line {i}
... ''', standalone=True)
>>> # Later...
>>> output = execute_standalone(code, n=3)
>>> print(output)
line 0
line 1
line 2
```

Templates can be stored in files:

```
# loop.aur
!for i in range(n):
    line {i}
```

```pycon
>>> output = execute('loop.aur', n=3)
```

Or, as we've seen, in strings – in which case they *must* be multiline, to tell them apart from paths. To accommodate
code indentation naturally, these multiline strings are cropped, removing the indent of their first non-empty line; so
the `loop.aur` template above is equivalent to our previous examples:

```pycon
>>> output = execute('''
...     !for i in range(n):
...         line {i}
... ''', n=3)
```

## Macros

Auryn's strength is its extensibility: we can write Python **plugins** that extend its generation through **macros**,
and its execution through **hooks**. Before we talk about it, however, common patterns are already implemented as part
of the **core plugin**, which is loaded by default (unless we pass `load_core=False`), so we have quite a few macros
available out of the box. For example:

```
# loop.aur
!for i in range(n):
    line {i}
```

```
>>> output = execute('''
...     %include loop.aur
... ''', n=3)
>>> print(output)
line 0
line 1
line 2
```

The `%include` macro takes a template and generates it in its place. There are actually three ways to invoke it, or any other macro:

1. `%macro <argument>`: the argument is passed as a string to the first parameter of the macro;
2. `%macro: <arguments>`: the arguments are split by space (respecting quoted strings);
3. `%macro:: <arguments>`: the arguments are passed as-is.

So for example, if we'd want `%include` to embed some text as-is, without treating it as generation instructions, we
could do:

```
%include: "file.txt" generate=False
```

If we'd want to do this conditionally, based on something like `is_template`, we'd have a problem negating it, since
this would introduce a space (`generate=not is_template`) and split the arguments incorrectly. In this case, we'd have
to write the full invocation with commas, like we would in Python:

```
%include:: "file.txt", generate=not is_template
```

`%include` resolves paths relative to the directory of the template it appears in, or if the template is a string,
relative to the directory of its **origin** – the module in which the generation/execution is invoked. Besides
`generate=`, it also accepts `interpolate=` (whether the text should be interpolated), `load=` (which additional plugins
to apply to this generation), `load_core=`, and `continue_generation=` (to carry over the current generation's
configuration, i.e. generate the template the same way).

Besides `%include`, we also have `%define` to create named blocks on the fly and `%insert` to embed them:

```
%block content
    hello world

# Later...
<p>
    %insert content
</p>
```

This is particularly useful with `%extend`, which is like a reverse-inclusion: the template is parsed primarily to see
what blocks it defines, and then replaced with the *extending* template, in which these blocks are inserted:

```
% base.aur
<html>
    <head>
        %insert head
            <meta charset="utf8" />
    </head>
    <body>
        %insert: "body" required=True
    </body>
</html>
```

```
% page.aur
%extends base.aur
%define head
    <title>title</title>
%define body
    <p>hello world</p>
```

The result:

```html
<html>
    <head>
        <title>title</title>
    </head>
    <body>
        <p>hello world</p>
    </body>
</html>
```

Lines nested in `%insert` are used as default content if the block it attempts to insert is missing; if `required=True`
is provided, that block must be defined or an error is raised. To insert blocks conditionally, we can use `%ifdef` and
`%ifndef`.

Beside template composition patterns, we have macros for other use cases, too. `%interpolate` can be used to change the
tokens used for interpolation from the default `{ }` to something else, either for the entire file or for a nested block
of lines:

```
%interpolate <% %> # Affects the entire file.
{not_interpolated}
<% interpolated %>

%interpolate {{ }} # Affects nested children only.
    <% not interpolated %>
    {not_interpolated_either}
    {{ interpolated }}
{{ not_interpolated_anymore }}
<% interpolated_again %>
```

Similarly, `%raw` can be used to mark an entire file, or a nested block of lines, to be emitted as-is:

```
%raw
    !for i in range(n):
        line {i}
```

And `%stop` can be use to end the execution where it's encountered:

```
!for i in range(n):
    line {i}
    !if i % 2 == 0:
        %stop
```

So far, we wrote templates that expected `n` to be available during execution, i.e. passed to `execute` along with the
template; if it wasn't, we'd get an `ExecutionError` around the `NameError` that raised when attempting to run the code.
We can define such requirements more explicitly and in advance with `%param`:

```
%param n
!for i in range(n):
    line {i}
```

And even provide it with a default, in case `n` is missing:

```
%param: "n" default=3
!for i in range(n):
    line {i}
```

Another interesting use-case is **inlining**: given a data model like:

```json
{
    "model_name": "user_profile",
    "fields": {
        "id": {
            "type": "number",
            "primary_key": true,
        },
        "username": {
            "type": "string",
        },
        "password": {
            "type": "string",
            "nullable": true,
        }
    }
}
```

We might want to generate code like this:

```python
class UserProfile(Model):
    id = Field("number", primary_key=True)
    username = Field("string")
    password = Field("string", nullable=True)
```

However, since templates are line-based, we will be hard pressed to add `primary_key=True` or `nullable=True` if the
corresponding keys are defined in the data model *on the same line*. That is, unless we use the `%inline` macro to mark
a nested block as emitted *inline*:

```
class {camel_case(data["model_name"])}(Model):
    !for field_name, field in data["fields"].items():
        %inline
            {field_name} = Field(
                {repr(field["type"])},
                !if field["primary_key"]:
                    primary_key=True,
                !if field["nullable"]:
                    nullable=True,
            )
```

This will work, but leave us with inelegant trailing commas; so we can also use the `%strip` macro to remove undesirable
characters from the previous line of generated output:

```
            # Same as before...
                !if field["nullable"]:
                    nullable=True,
                %strip ,
            )
```

Another interesting use-case is **backtracking**: realizing somewhere down the template that we'd want to add something
to its beginning – like processing an HTML document's body and realizing we have to add something to its head. This can
be done with the `%bookmark` macro, which effectively creates a placeholder, and the `%append` macro, which adds content
to it later on:

```
<html>
    <head>
        %bookmark styles
    </head>
    <body>
        !for text, style in content.items():
            <p>{text}</p>
            !if style:
                %append styles
                    <styles rel="stylesheet" href="{style}" />
    </body>
</html>
```

## Filesystem Macros

Another builtin plugin exists to generate entire directory structures. This, for example:

``` pycon
>>> execute('''
...     %load filesystem
...     {name}/
...         file.txt
...             !for line in range(n):
...                 line {i}
... ''', name='dir', n=3)
```

Will generate a `dir` directory with a `file.txt` inside it, and our usual `line 0...line 2` example inside *it*. Since
it hijacks the line transformation mechanism (text lines are treated as path directives), it's not included by default:
that's why we need to use the `%load` macro. We could also pass it via `load=`:

```pycon
>>> execute(template, load='filesystem')
```

And since it's a builtin plugin that comes as part of Auryn, it's enough to specify its name (for custom plugins, we'd
have to specify their path). Once loaded, it treats lines ending with `/` as instructions to create a directory, and the
rest of the lines as instructions to create files, with the exception of lines nested inside a file definition, which
are generated using the standard transforms as that file's content. Code and macro lines still work:

```
%load filesystem
%include dir.aur
!for n, filename in enumerate(filenames):
    {file}.txt
        File #{n}.
```

And just like with macros, if we want to pass additional arguments (other than the path), we can put a string one right
after it, or multiple/keyword arguments with `:` or `::`. That first argument would be the source, i.e. a directory or
file to base the entry upon, copying its contents:

```
dir/ base_dir          # Copies base_dir to dir/
    file.txt base_file # And adds file.txt to it, copied from base_file
```

File sources are copied as data by default; that is, they're not generated as templates, although their contents are
interpolated. These two options can be toggled with `generate=True` or `interpolate=False`, respectively; and note that
here we need to use `:`-notation:

```
file1.txt: "template.aur" generate=True
file2.txt: "raw_content.txt" interpolate=False
```

For directories, these arguments are passed to its entries during traversal:

```
dir/: "templates" generate=True # Generates an entire directory of templates.
```

Certain aspects of creating a directory strucutre are normally done with the shell (e.g. making a script executable);
for that purpose, shell commands are also supported via lines that start with `$`:

```
script.sh
    echo hello world
$ chmod +x script.sh
```

Since `:` can be a valid part of a shell command, the way to pass additional arguments to them is a bit different: `#`
for space-delimited arguments and `##` for an invocation as-is. Those arguments help us capture the standard output
(`into=`), standard error (`stderr_into=`) and status (`status_into=`) into variables of our choice:

```sh
$ curl {url} # into="content" status_into="status"
!if status > 0:
    {url}.txt
        {content}
```

As well as raise an error if the command fails (`strict=True`) or exceeds a time limit (`timeout=`).

## Advanced Syntax

To add multiline code, instead of prefixing each line with `!`:

```
!def f():
!    return 1
```

We can indent a whole block after an empty code line:

```
!
    def f():
        return 1
```

To add comments, we use code lines starting with `#`:

```
!# A comment.
!#
    A comment with
    multiple lines.
```

By default, empty lines are omitted from the output; to add one, we use an empty macro line:

```
line 1
        # This line is omitted.
line 2
%       # This line is emitted.
line 3
```

To run code *during generation*, we use macro lines starting with `!`:

```
%!x = 1
%!
    def f():
        return 1
```

This can be useful when we want to call macros conditionally or in a loop:

```
%!for template in templates:
    %include: template
```

Note that since this is happening during *generation*, passing `templates=[...]` to `execute` is not going to cut it:
such context is available during *execution*. To pass in generation context, we can either call the two phases
separately, passing each context to its respective function:

```pycon
>>> # Note: context can be passed as keyword arguments or a positional dictionary (or both)
>>> code = generate(template, generation_context)
>>> output = execute_standalone(code, execution_context)
```

Or prefix any generation-time names with `g_` when passing them to `execute`:

```pycon
>>> output = execute(template, g_templates=[...]) # Will be available as templates in macro code lines (%!).
```

Most of the time, we'll use standard code lines (so the standard execution context will suffice); programming in both
phases at once is pretty difficult and confusing. When we have to, though, there are a few tricks to bear in mind:

1. Interpolation (with potentially custom delimiters) is an execution-time feature; in generation time, we're limited to
   Python's f-strings, and have to use them explicitly:

    ```
    %!for template_name in template_names:
        %include: f'{template_name}.aur'
    ```

2. If we want to "pass down" a value available during generation and make it available during execution, we can use the
    `%eval` macro:

    ```
    %!for chapter_num, chapter in enumerate(chapters):
        %include: chapter
        %eval chapter_num = {chapter_num}
        !# Now we can use chapter_num in regular code lines, like:
        !if chapter_num > 0:
            # Add to table of contents.
    ```

3. If we want to emit a value available during generation, we can pass it down to execution and use interpolation, but
    also emit it more directly with the `%emit` macro:

    ```
    %!for chapter_num, chapter in enumreate(chapters):
        %emit "Chapter #{chapter_num}"
        %include: chapter
    ```

## Plugin Development

All the sophisticated macros listed above are generated as standard plugins; the only thing that sets them apart as 
*builtin* plugins is that they're located in the `auryn/plugins` directory, so we can load them by name. What's more,
most of them are implemented in 2-20 lines; the whole purpose of this two-phase generation, and the core principle
guiding Auryn's design, is to make it easy (or rather, as easy as possible) to add new syntax to this meta-language.

Think about it: the generation/execution process is somewhat similar to compilation, converting "high-level" template
instructions into "low-level" bytecode that can run on a particular VM or hardware (and in our case, Python); however,
because our "bytecode" is effectively as high-level a language as Python, we gain incredible abilities to manipulate it:
introspect its values, inject dynamic code into it, and so on.

With that in mind, here's how we write plugins: to define a macro, we create a function starting with `g_`, and to 
define a hook (more on those later), we add a function starting with `x_`. We can place these functions in a standard
module, in which case we can load it by path:

```python
# hello.py
def g_hello(gx, name):
    gx.add_text(0, f"hello, {name}")
```

```pycon
>>> output = execute('''
...     %hello world
... ''', load=['hello.py'])
>>> print(output)
hello world
```

We've seen that builtin modules (namely, `filesystem`) can also be loaded by name; the third way to load additional
macros and hooks is by providing them in a dictionary:

```pycon
>>> def g_hello(gx, name):
...     gx.add_text(0, f"hello, {name}")
>>> output = execute('''
...     %hello world
... ''', load={'g_hello': g_hello})
>>> print(output)
hello world
```

To load multiple plugins, we can also pass a list thereof. Anyway, those `g_` and `x_` functions are special in that
they always receive `gx: GX` as their first argument, much like methods do `self`: this is the generation/execution
object, which provides them with a set of utilities to influence its result. The most important of those are:

1. `gx.line`: the current line being transformed; it has a `number`, an `indent`, its `content` and the `children`
    nested inside it, encapsulated in a `Lines` object that behaves like a list, but has a few nifty utilities of its
    own.
2. `gx.add_code(code)`: a way to add raw Python to the generated code.
3. `gx.add_text(indent, text)`: a way to emit text (that is, add code that emits text) to the generated code.
4. `gx.transform([lines])`: recursively continue transforming the specified lines (default is the children of the
    current line).
5. `gx.increase_code_indent()`, `gx.decrease_code_indent()` and the `gx.increased_code_indent()` context manager: three
    ways of controlling the current indentation of the generated code.

At this point, I find it useful to implement a few macros as an exercise: let's start with `%text` and `%code` that
emulate text and code lines, to see how such logic might look:

```python
def g_text(gx):
    gx.add_text(gx.line.indent, gx.line.content)
    gx.transform()
```

Text is the simplest: we emit the current line's content at the current line's indent, and go on to transform any
children it might have. Code is a bit trickier:

```python
def g_code(gx):
    gx.add_code(gx.line.content.removeprefix("!"))
    with gx.increased_code_indent():
        gx.transform(gx.line.children.snap())
```

That is, we add the code (without the `!` prefix), increase the indent, transform any children and then decrease it
back. Since we're managing the code indent explicitly, we also use `snap()` to align them to their parent's indent, thus
discarding any additional indentation they might have had. And if we'd like to add support for code blocks:

```python
def g_code(gx):
    if gx.line.content == "!" and gx.line.children: # Empty code line with a nested block:
        code = gx.line.children.snap(0).to_string()
        gx.add_code(code)
    # Same as before
```

That is, we use `snap(0)` to remove *any* indent from the children, since the next thing we do is to convert them to a
string and inject all of it at once.

Let's also implement `%define` and `%insert`:

```python
def g_define(gx, name):
    definitions = gx.state.setdefault('blocks', {})
    definitions[name] = gx.line.children

def g_insert(gx, name, required=False):
    definitions = gx.state.get('blocks', {})
    if name in definitions:
        gx.transform(definitions[name].snap(gx.line.indent))
    else:
        if required:
            raise ValueError(f"missing required definition {name!r} on line {gx.line}")
        gx.transform(gx.line.children.snap())
```

For `%define`, we simply store the current line's children in a dedicated slot of `gx.state`, available for this purpose
of sharing data between macros. For `%insert`, we fetch those children, snap them to the the current line's indent, and
transform them recursively as if this is where they appeared to begin with. If the block is missing, we raise an error
if it's required, and otherwise use our own children as the default, removing the unnecessary indentation.

It takes a while to get the hang of `snap`, so consider that last scenario again. Suppose we have:

```
<body>
    %insert content
        <p>hello world</p>
</body>
```

The indentation of `%insert` is 4; the indentation of its children (`<p>hello world</p>`) is 8. If the `content` block
is missing, we want to end up with:

```html
<body>
    <p>hello world</p>
</body>
```

That is, transform `%insert`'s children, but without the extra spaces that were necessary only to delineate them as
such. Calling `snap()` before passing them into `transform` does exactly that: it shifts them 4 spaces back, aligning
them to `%insert`'s indentation, and continues from there – a pretty common pattern with children. For another example,
take `%raw`:

```
def g_raw(gx):
    content = gx.children.snap().to_string()
    gx.add_text(gx.line.indent, content, crop=True, interpolate=False)
```

If we have:

```
<p>
    %raw
        {this should not be interpolated}
</p>
```

We'd like to end up with:

```html
<p>
    {this should not be interpolated}
</p>
```

So we snap the children to `%raw`'s indentation level before converting them into a string and passing them to
`add_text`. Normally, this function expects a single line; since `%raw`'s content might span multiple lines, we add
`crop=True`, as well as `interpolate=False` to make sure it remains, well, raw.

That's how the majority of macros work: inject some code or other, adjusting the code indentation if necessary, and
recurse on their children after snapping them into place. But let's say we want to emulate the `%filesystem` plugin:
how would we go about a `%directory` macro? The obvious solution might look like:

```python
def g_directory(gx, name):
    gx.add_code("import os")
    gx.add_code(f"os.mkdir({name!r}, parents=True)")
    gx.add_code(f"os.chdir({name!r})")
    gx.transform(gx.line.children.snap())
    gx.add_code(f"os.chdir('..')")
```

That is, make sure `os` is available, create the directory, enter it, transform its children inside it, and finally step
out. However, any such execution-time complexity is best encapsulated in a hook: since we're dealing with Python, we can
add functions that will be available during runtime just as easily, and it makes our code much cleaner:

```python
def g_directory(gx, name):
    gx.add_code('with directory({name!r}):')
    with gx.increased_code_indent():
        gx.transform(gx.line.children.snap())
```

What's this `directory` context manager? Well:

```python
import contextlib
import os

@contextlib.contextmanager
def x_directory(gx, name):
    os.mkdir(name, parents=True)
    os.chdir(name)
    try:
        yield
    finally:
        os.chdir('..')
```

This function, `x_directory`, will be available during execution as `directory`; and the `g_directory` macro assumes as
much, generating code accordingly, and delegating any runtime consideration to its corresponding hook.

There's much more to say about all the cool things we can do with this paradigm, but until I have time to write such a
guide, the best thing to do is look at the implementations of `auryn/plugins/core.py` and `auryn/plugins/filesystem.py`
and learn from there. We can add post-processing with `on_complete` (which `%extend` does), temporarily patch `output`
to replace it with our own list (which is how files capture and then write their content), replace the line transforms
at load time with `on_load` and `line_transform` and so on – do let me know what fun ideas you come up with :)

## Understanding Errors

When working with so many layers of abstractions, bugs can be difficult to reason about. For that reason, Auryn raises
either a `GenerationError` or an `ExecutionError`, depending on what phase the issue occured in, that can print a
detailed, color-highlighted report. Suppose we have these template:

```
# template1.aur
%include template2.aur
```

```
# template2.aur
%load plugin.py
%error
```

And this plugin:

```
# plugin.py

def g_error(gx):
    gx.add_code('error()')

def x_error(gx):
    raise ValueError('wat')
```

Executing the first template will include the second, which will call the `%error` macro, which will inject code that
will call a hook that raises an error at execution time. Following a similar flow when it's unplanned can be tricky, so
the way to orient ourselves is catch any such exceptions (both inheriting from `auryn.Error`) and print their report:

```
>>> try:
...     execute('template1.aur')
... except auryn.Error as error:
...     print(error.report())
```

Lo and behold:

```
Failed to execute GX of template1.aur at <stdin>:2:4: wat.

CONTEXT
gx: GX of template1.aur at <stdin>:2
emit: emit at auryn/gx.py:697
indent: _indent at auryn/gx.py:758
StopExecution: auryn.errors.StopExecution
s: x_s at auryn/plugins/core.py:60
strip: x_strip at auryn/plugins/core.py:519
assign: x_assign at auryn/plugins/core.py:560
bookmark: x_bookmark at auryn/plugins/core.py:608
append: x_append at auryn/plugins/core.py:641
camel_case: x_camel_case at auryn/plugins/core.py:659
error: x_error at plugin.py:4 <--

TEMPLATE
in template2.aur:2:
    %load plugin.py
    %error <-- highlighted
derived from template1.aur:2:
    %load plugin.py
    %include template2.aur <-- highlighted

TRACEBACK
in <stdin>:2:
    ???
in auryn/api.py:110:
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
        # ... cropped ...
in auryn/gx.py:335:
    def execute(self, context: dict[str, Any] | None = None, /, **context_kwargs: Any) -> str:
        # ... cropped ...
in auryn/gx.py:329:
    def execute(self, context: dict[str, Any] | None = None, /, **context_kwargs: Any) -> str:
        # ... cropped ...
in auryn/gx.py:695:
    def x_exec(self, code: str) -> None:
        # ... cropped ...
in auryn/gx.py:756:
    def _execute(
        self,
        suffix: str,
        text: str,
        globals: dict[str, Any],
        locals: dict[str, Any] | None = None,
        *,
        expression: bool = False,
    ) -> Any:
        # ... cropped ...
in execution of GX of template1:
    error() <-- highlighted
in plugin.py:5:
    def x_error(gx):
        raise ValueError() <-- highlighted
ValueError: wat
```

This includes a dump of the context, the template traceback (including nested ones, derived via e.g. %include) and the
code traceback, with builtins and internal definitions dimmed out, and the problematic lines highlighted. You can't
really see it in the README, but trust me, it's beautiful.

## CLI

The `auryn` command is provided for convenience, to generate and execute templates via the command-line:

```
# template.aur
!for i in range(n):
    line {i}
```

```sh
$ auryn generate template.aur
for i in range(n):
    emit(0, 'line ', i)

$ auryn execute template.aur n=3
line 0
line 1
line 2
```

Context is provided either as key-value pairs (e.g. `n=3`), where the values are parsed as JSON and used as strings if
it fails, or as a JSON file with the `-c|--context` option (or both).

To generate standalone code, use `generate` with the `-s|--standalone` flag; to execute it, use `execute-standalone`:

```sh
$ auryn generate -s template.aur > code.py
$ auryn execute-standalone code.py n=3
line 0
line 1
line 2
```

To load additional plugins, use the `-l|--load` option followed by the plugin path or name (if it's builtin); using it
multiple times is supported.

```
# template.aur
%hello world
```

```python
def g_hello(gx, name):
    gx.add_text(gx.line.indent, f"hello {name}")
```

```sh
$ auryn execute -l hello.py template.aur
hello world
```

To avoid loading the core plugin, use the `-n|--no-core` flag.

## Local Development

Install the project with development dependencies:

```sh
$ poetry install --with dev
...
```

The `dev.py` script contains development-related tasks, mapped to Poe the Poet commands:

- Linting (with `black`, `isort` and `flake8`):

    ```sh
    $ poe lint [module]*
    ...
    ```

- Type-checking (with `mypy`):

    ```sh
    $ poe type [module]*
    ...
    ```

- Testing (with `pytest`):

    ```sh
    $ poe test [name]*
    ...
    ```

- Coverage (with `pytest-cov`):

    ```sh
    $ poe cov
    ... # browse localhost:8888
    ```

- Clean artefacts generated by these commands:

    ```sh
    $ poe clean
    ```

## License

[MIT](https://opensource.org/license/mit).