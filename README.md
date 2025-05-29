# Auryn

A metaprogramming engine for extensible templating and code generation.

- [Installation](#installation)
- [Quickstart](#quickstart)
    - [Simple Templating](#simple-templating)
    - [Template Composition](#template-composition)
    - [Recursive Code Generation](#recursive-code-generation)
    - [Directory Structure Generation](#directory-structure-generation)
- [Overview](#overview)
    - [Generation/Execution](#generationexecution)
    - [Standalone Code](#standalone-code)
    - [Templates](#templates)
    - [Macros](#macros)
        - [Template Inclusion](#template-inclusion)
        - [Template Extension](#template-extension)
        - [Evaluation and Interpolation Control](#evaluation-and-interpolation-control)
        - [Parameter Definition, Inlining and Backtracking](#parameter-definition-inlining-and-backtracking)
        - [Filesystem Macros](#filesystem-macros)
    - [Advanced Syntax](#advanced-syntax)
- [Plugin Development](#plugin-development)
    - [Understanding Errors](#understanding-errors)
- [CLI](#cli)
- [Local Development](#local-development)
- [License](#license)

![Auryn Logo](auryn.png)

## Installation

**Requires Python ≥ 3.10.**

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

### Simple Templating

```pycon
>>> import auryn

>>> output = auryn.execute(
...     """
...     !for i in range(n):
...         line {i}
...     """,
...     n=3,
... )
>>> print(output)
line 0
line 1
line 2
```

### Template Composition

Given `base.aur`:

```
<!DOCTYPE html>
<html>
    <head>
        %insert head
    </head>
    <body>
        %insert body
    </body>
<html>
```

And `meta.aur`:

```
<meta charset="utf8" />
<meta name="author" content="{author}" />
<meta name="description" content="{description}" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
```

We can use the `%extend`, `%define`, `%insert` and `%include` macros to compose them:

```pycon
>>> output = auryn.execute(
...     """
...     %extend base.aur
...     %define head
...         <title>{title}</title>
...         %include meta.aur
...     %define body
...         <p>{message}</p>
...     """,
...     title="Auryn",
...     author="Dan Gittik",
...     description="The Auryn metaprogramming engine",
...     message="Metaprogramming is cool!",
... )
>>> print(output)
<!DOCTYPE html>
<html>
    <head>
        <title>Auryn</title>
        <meta charset="utf8" />
        <meta name="author" content="Dan Gittik" />
        <meta name="description" content="The Auryn metaprogramming engine" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    </head>
    <body>
        <p>Metaprogramming is cool!</p>
    </body>
</html>
```

### Recursive Code Generation

Given `typechecking.aur`, which defines code generation *functions* (and uses custom `<% %>` interpolation to set it
apart from Python's native f-strings):

```
%interpolate <% %>

!def check_integer(name, min=None, max=None):
    if not isinstance(<% name %>, int):
        raise ValueError(f"expected {<% name %>=} to be an integer")
    !if min is not None:
        if <% name %> < <% min% >:
            raise ValueError(f"expected {<% name %>=} >= <% min %>")
    !if max is not None:
        if <% name %> > <% min% >:
            raise ValueError(f"expected {<% name %>=} <= <% max %>")

!def check_types(name, config):
    !if config["type"] == "integer":
        !check_integer(name, config.get("min"), config.get("max"))
    !if config["type"] == "object":
        if not isinstance(<% name %>, object):
            raise ValueError(f"expected {<% name %>=} to be an object")
        !for key, value in config["attributes"].items():
            !check_types(f"{name}.{key}", value)
```

And a data model in `model.json`:

```json
{
    "n": {
        "type": "integer",
        "min": 1,
        "max": 10
    },
    "p": {
        "type": "object",
        "attributes": {
            "x": {
                "type": "integer"
            },
            "y": {
                "type": "integer"
            }
        }
    }
}
```

We can generate validation code *recursively*:

```pycon
>>> import json
>>> output = auryn.execute(
...     """
...     %incldue typechecking.aur
...     def validate(
...         !for key in model:
...             {key},
...     ):
...         !for key, value in model.items():
...             !check_types(key, value)
...     """,
...     model=json.load(open("model.json")),
... )
... print(output)
def validate(
    n,
    p,
):
    if not isinstance(n, int):
        raise ValueError(f"expected {n=} to be an integer")
    if n < 1:
        raise ValueError(f"expected {n=} >= 1")
    if n > 1:
        raise ValueError(f"expected {n=} <= 10")
    if not isinstance(p, object):
        raise ValueError(f"expected {p=} to be an object")
    if not isinstance(p.x, int):
        raise ValueError(f"expected {p.x=} to be an integer")
    if not isinstance(p.y, int):
        raise ValueError(f"expected {p.y=} to be an integer")
```

### Directory Structure Generation

Using the `filesystem` plugin, we can augment our syntax to generate files and directories and run shell commands:

```pycon
>>> auryn.execute(
...     """
...     %load filesystem
...     dir/
...         !for i in range(n):
...             script{i}.sh
...                 echo hello {i}!
...             $chmod +x script{i}.sh
...     """,
...     n=3,
... )
```

To wit:

```sh
$ dir/script0.sh
hello 0!
$ dir/script1.sh
hello 1!
$ dir/script2.sh
hello 2!
```

## Overview

### Generation/Execution

Auryn works in two **phases**:

1. **Generation**: generate code according to a **template**;
2. **Execution**: run the **generated code** to produce an **output**.

This is a bit mind-bending; to appreciate the motivation and get a gentler introduction to the subject, check out 
[A Templating Engine in 20 Lines](docs/templating-engine-in-20-lines.md).

Templates are parsed line by lines, where each line can be:

1. A **text line**: emitted as output (after **interpolation**);
2. A **code line** (starting with `!`): runs during execution;
3. A **macro line** (starting with `%`): runs during generation.

For example:

```pycon
>>> output = auryn.execute(
...     """
...     !for i in range(n):
...         line {i}
...     """,
...     n=3)
line 0
line 1
line 2
```

`!for i in range(n):` is a code line; it becomes part of the generated code, to be run during execution (with `n=3`).
`line {i}` is a text line; it's emitted as output – that is, generates code that emits `'line ', i`. To see this code
for ourselves we can call `generate`, which performs the generation phase only:

```pycon
>>> code = auryn.generate(
...     """
...     !for i in range(n):
...         line {i}
...     """
... )
>>> print(code)
for i in range(n):
    emit(0, 'line ', i)
```

### Standalone Code

We can thus split the two phases: generate code at one time, and execute it later (e.g. to improve performance). To do
that, we need to generate the code with `standalone=True`, then pass it to `execute_standalone`:

```pycon
>>> code = auryn.generate(
...     """
...     !for i in range(n):
...         line {i}
...     """,
...     standalone=True,
... )
>>> # Later...
>>> output = auryn.execute_standalone(code, n=3)
>>> print(output)
line 0
line 1
line 2
```

### Templates

The templates in the examples so far were all strings, but they can also be stored in files:

```
# loop.aur
!for i in range(n):
    line {i}
```

```pycon
>>> output = execute("loop.aur", n=3)
```

To tell the two cases apart, string templates *must* be multiline. To be fair, one-line templates aren't particularly
interesting to begin with, but even in cases when we have them we should do:

```pycon
>>> output = auryn.execute(
...     """
...     hello world
...     """
... )
```

Rather than `auryn.execute("hello world")`, since the latter will be interpreted as a path. As for multiline strings,
they get intelligently cropped, removing the indent of their first non-empty line from all subsequent lines, so that
they can accommodate the code's indentation without the extra whitespace getting in the way; hence, in our previous
examples:

```pycon
>>> output = auryn.execute(
...     """
...     !for i in range(n):
...         line {i}
...     """
... )
```

We effectively end up with a template identical to `loop.aur`.

### Macros

Auryn's strength is its extensibility: we can write Python **plugins** that extend its generation through **macros**,
and its execution through **hooks**. Before we talk about it, however, common patterns are already implemented as part
of the **core plugin**, which is loaded by default (unless we pass `load_core=False`), so we have quite a few macros
available out of the box.

#### Template Inclusion

For example, given `loop.aur`:

```
!for i in range(n):
    line {i}
```

We can do:

```pycon
>>> output = execute(
...     """
...     %include loop.aur
...     """,
...     n=3,
... )
>>> print(output)
line 0
line 1
line 2
```

The `%include` macro takes a template and generates it in its place. There are actually three ways to invoke it, or any
other macro:

1. `%macro <argument>`: the argument is passed as a string to the first parameter of the macro;
2. `%macro: <arguments>`: the arguments are split by space (respecting quoted strings);
3. `%macro:: <arguments>`: the arguments are passed as-is.

So for instance, if we'd want `%include` to embed some text as-is, without treating it as generation instructions, we
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
`generate=<bool>`, it also accepts `interpolate=<bool>` (whether the text should be interpolated), `load=<plugins>`
(which additional plugins to apply in this generation), `load_core=<bool>`, and `continue_generation=<bool>` (to carry
over the current generation's configuration, i.e. generate the nested template in the same way as the nesting one).

#### Template Extension

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
what blocks it defines, and then replaced with the *extending* template, in which these blocks are inserted. If we have
`base.aur`:

```
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

And then `page.aur`:

```
%extends base.aur
%define head
    <title>title</title>
%define body
    <p>hello world</p>
```

We get:

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

Lines nested in `%insert` are used as default content if the block it attempts to insert is missing; so if we'd omit the
`head` block from `page.aur`, we'd get:

```html
<html>
    <head>
        <meta charset="utf8" />
    </head>
    <body>
        <p>hello world</p>
    </body>
</html>
```

If `required=True`, the block must be defined; so if we'd omit `body`, we'd get an error. To insert blocks conditionally
we can use `%ifdef` and `%ifndef`:

```
%ifdef body
    <div class="container">
        %insert body
    </div>
```

#### Evaluation and Interpolation Control

Beside template composition patterns, we have macros for other use cases, too. `%interpolate` can be used to change the
tokens used for interpolation from the default `{ }` to something else, either for the entire file or for a nested block
of lines:

```
%interpolate <% %> # Affects the entire file.
{not_interpolated}
<% interpolated %>

%interpolate {{ }} # Affects nested children only.
    <% not_interpolated %>
    {not_interpolated_either}
    {{ interpolated }}
{{ not_interpolated_anymore }}
<% interpolated_again %>
```

Similarly, `%raw` can be used to mark an entire file, or a nested block of lines, to be emitted as-is:

```
%raw
!not_executed
{nor_interpolated}
```

```
!executed
{interpolated}
%raw
    !not_executed
    {nor_interpolated}
!executed_again
{interpolated_again}
```

`%stop` can be use to end the execution where it's encountered:

```
!for i in range(n):
    line {i}
    !if i % 2 == 0:
        %stop
```

#### Parameter Definition, Inlining and Backtracking

So far, we wrote templates that expected `n` to be available during execution, i.e. passed to `execute` along with the
template; if it wasn't, we'd get an `ExecutionError` around the `NameError` that is raised when attempting to run the
code. We can define such requirements more explicitly and in advance with `%param`:

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

Since generation and execution are two separate phases, and this lets us define in the first what we're going to need in
the second, it can also be inspected inbetween. Currently there's no convenience method for it, but we can do so with
more low-level constructs (which we'll cover later):

```python
>>> gx = auryn.GX.parse("""
...     %param x
...     %param: "y" default=2
... """) 
>>> gx.generate()
>>> gx.state["parameters"]
{'x': '<required>',
 'y': 2}
```

Another interesting use-case is **inlining**: given a data model like this:

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

However, since templates are line-based, we will be hard pressed to add `primary_key=True` or `nullable=True` (if the
corresponding keys are defined in the data model) *on the same line*. That is, unless we use the `%inline` macro to mark
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
```

Another interesting use-case is **backtracking**: realizing somewhere down the template that we actually want to add
something to its beginning – like processing an HTML document's body and realizing we have to add something to its head.
This can be done with the `%bookmark` macro, which effectively creates a placeholder, and the `%append` macro, which
adds content to a given bookmark later on:

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

#### Filesystem Macros

Another builtin plugin lets us generate directory structures. For example:

``` pycon
>>> execute(
...     """
...     %load filesystem
...     {name}/
...         file.txt
...             !for line in range(n):
...                 line {i}
...     """,
...     name='dir',
...     n=3,
... )
```

Will generate a `dir` directory with a `file.txt` inside it, and our usual `line 0...line 2` content inside *it*. Since
it hijacks the line transformation mechanism – text lines are treated as **path directives** – it's not included by
default: that's why we need to use the `%load` macro, or pass it to `execute` via `load=<plugins>`:

```pycon
>>> execute(template, load="filesystem")
```

And since it's a builtin plugin that comes as part of Auryn, it's enough to specify its name (for custom plugins, we'd
have to specify their path). Once loaded, it treats lines ending with `/` as instructions to create a directory, and the
rest of the lines as instructions to create files – except lines nested inside a file definition, which are generated
using the standard line transformations to generate that file's content. Code lines, macro lines and interpolation works
as usual:

```
%load filesystem
%include project-structure.aur
!for n, filename in enumerate(filenames):
    {filename}.txt
        File #{n}.
```

And just like with macros, if we want to pass additional arguments (other than the path), we can put a string one right
after a path directive, or multiple/keyword arguments with `:` or `::`. That first argument would be a source to copy
the file or directory from:

```
dir/ src_dir          # Copies src_dir to dir/
    file.txt src_file # And adds file.txt to it, copied from src_file
```

Normally, file sources are copied as data; that is, they're not generated as templates, although their contents are
still interpolated. These two options can be toggled with `generate=True` or `interpolate=False`, respectively; and note
that here we do need to use `:`-notation:

```
file1.txt: "template.aur" generate=True
file2.txt: "raw_content.txt" interpolate=False
```

For directories, these arguments are passed to its entries during traversal:

```
dir/: "templates" generate=True # Recursively generates an entire directory of templates.
```

Certain aspects of creating a directory strucutre are normally done with shell commands (e.g. making a script
executable), so we support those as well, via lines that start with `$`:

```
script.sh
    echo hello world
$chmod +x script.sh
```

Since `:` can be a valid part of a shell command, the way to pass additional arguments to them is a bit different: `#`
for space-delimited arguments and `##` for an invocation as-is. Those arguments can capture the standard output
(`into=<string>`), standard error (`stderr_into=<string>`) and status (`status_into=<string>`) into variables:

```sh
$ curl {url} # into="content" status_into="status"
!if status > 0:
    {normalize(url)}.txt
        {content}
```

As well as raise an error if the command fails (`strict=True`) or exceeds a time limit (`timeout=<float>`).

### Advanced Syntax

To add multiline code, instead of prefixing each line with `!`:

```
!def f():
!    return 1
```

We indent a whole block after an empty code line:

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

By default, empty lines are omitted from the output; to add one explicitly, we use an empty macro line:

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

Or even to define macros dynamically (more on this later):

```
%!
    def hello(gx, name):
        gx.emit_text(0, f'hello {name}')

%hello world
```

Note that in the previous example, passing `templates=[...]` to `execute` is not going to work, since such context is
available during *execution*, while the `%!for` loop is happening during *generation*. To pass context to *it*, we have
to either manage the phases separately (in which case each function accepts its respective context):

```pycon
>>> code = generate(template, generation_context)
>>> output = execute_standalone(code, execution_context)
# Note: context can be passed as via keyword arguments or a positional dictionary (or both).
```

Alternative, we can prefix any generation-time names with `g_` when passing them to `execute`:

```pycon
>>> output = execute(
...     """
...     %!for template in templates:
...         %include: template
...     """,
...     g_templates=[...], # Aavailable as `templates` during generation.
... )
```

Most of the time, we'll use standard code lines (so the standard execution context will suffice); programming in both
phases at once is pretty advanced and somewhat confusing. When we have to, though, a few details to bear in mind:

1. Interpolation (with potentially custom delimiters) is an execution-time feature; in generation time, we're limited to
   Python's f-strings, and have to use them explicitly:

    ```
    %!for template_name in template_names:
        %include: f'{template_name}.aur'
    ```

2. If we want to "pass down" a value available during generation and make it available during execution, we can use the
    `%eval` macro:

    ```
    %!for n, chapter in enumerate(chapters):
        %include: chapter
        %eval chapter_num = {n} # chapter_num in now available in regular code lines
        !if chapter_num > 0:
            ... # e.g. add chapter to table of contents.
    ```

3. If we want to *emit* a value available during generation, we can pass it down to execution and use interpolation, but
    also do so directly with the `%emit` macro:

    ```
    %!for n, chapter in enumreate(chapters):
        %emit <h1>Chapter #{n}</h1>
        %include: chapter
    ```

## Plugin Development

All the sophisticated macros listed above are implemented as standard plugins; the only thing that sets them apart is
that they are located in the `auryn/plugins` directory, and as such are considered *builtin* and are loadable by *name*,
whereas custom plugins need to be loaded by *path*. Interestingly, most of these plugins are implemented in 2-20 lines;
the whole purpose of two-phase generation, and the core design principle behind Auryn, is to make it easy (or rather, as
easy as possible) to extend the syntax of its meta-language.

Think about it: the generation/execution process is somewhat similar to compilation, converting "high-level" template
instructions into "low-level" bytecode that can run on a particular VM or hardware (in our case, Python); however,
because our "bytecode" is effectively Python, we gain an incredible degree of control in manipulation it: introspection
of values, dynamic code injection, and so on.

With that in mind, let's see how plugins are implemented. To define a macro, we create a function starting with `g_`; to
to define a hook (more on those later), we create a function starting with `x_`. These functions are placed in a regular
Python module, which can be loaded by path:

```python
# plugins/hello.py
def g_hello(gx, name):
    gx.add_text(0, f"hello, {name}")
```

```pycon
>>> output = execute(
...     """
...     %hello world
...     """,
...     load="plugins/hello.py",
)
>>> print(output)
hello world
```

We've seen that builtin modules (namely, `filesystem`) can be loaded by name; we can achieve the same for custom plugins
by adding their directories to `GX.plugin_directories`:

```pycon
>>> auryn.GX.add_plugins_directory("plugins")
>>> output = execute(
...     """
...     %hello world
...     """,
...     load="hello",
... )
>>> print(output)
hello world
```

the third way to load additional macros and hooks is by providing them in a dictionary:

```pycon
>>> def g_hello(gx, name):
...     gx.add_text(0, f"hello, {name}")
>>> output = execute(
...     """
...     %hello world
...     """,
...     load={"g_hello": g_hello},
... )
>>> print(output)
hello world
```

And finally, to load multiple plugins, we can pass a list of any of the above. In any case, those `g_` and `x_`
functions are special in that they always receive a `GX` object as their first argument, much like methods receive their
instance in `self`; and this object is what provides them with all the necessary utilities to influence the
generation/execution process. The most important of those are:

1. `gx.line`: the current line being transformed; it has a `number`, an `indent`, its `content` and the `children`
    nested inside it, encapsulated in a `Lines` object that behaves like a list, but provides a couple nifty utilities
    of its own.
2. `gx.add_code(code)`: a way to add raw Python to the generated code.
3. `gx.add_text(indent, text)`: a way to emit text (that is, add code that emits text) to the generated code.
4. `gx.transform([lines])`: recursively continue the transformation of the specified lines (if no lines are specified,
    it applies to the children of the current line).
5. `gx.increase_code_indent()`, `gx.decrease_code_indent()` and the `gx.increased_code_indent()` context manager: three
    ways of controlling the current indentation of the generated code.

At this point, I find it useful to implement some macros as an exercise, starting with `%text` and `%code` with which we
can emulate how text lines and code lines are are transformed (albiet with terser syntax):

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
back. Since we're managing the code indent explicitly, we also use `snap()` to align the children to the current line's
indent, thus cancelling the additional indentation necessary to nest them under the current line. In other words:

```
%code if x > 1:
    %text x is greater than 1
```

Becomes:

```python
if x > 1:
    emit(0, 'x is greater than 1') # Rather than emit(4, 'x is greater than 1')
#       ^^^                                          ^^^
```

Because `%text` is "pulled back" to `%code`'s level of indentation before being recursively transformed, and the 4
spaces that made it `%code`'s child are not counted towards its own indentation. If we'd want to support code blocks:

```python
def g_code(gx):
    if gx.line.content == "!" and gx.line.children: # Empty code line with a nested block:
        code = gx.line.children.snap(0).to_string()
        gx.add_code(code)
    ... # Same as before.
```

That is, we use `snap(0)` to remove *any* indentation from the children, seeing as the next thing we do is to convert
them to a string and inject all of it at once.

Now, let's implement `%define` and `%insert` ourselves:

```python
def g_define(gx, name):
    definitions = gx.state.setdefault("blocks", {})
    definitions[name] = gx.line.children

def g_insert(gx, name, required=False):
    definitions = gx.state.get("blocks", {})
    if name in definitions:
        gx.transform(definitions[name].snap(gx.line.indent))
    else:
        if required:
            raise ValueError(f"missing required definition {name!r} on line {gx.line}")
        gx.transform(gx.line.children.snap())
```

For `%define`, we simply store the current line's children in a dedicated slot of `gx.state`, available for this purpose
of sharing data between macros. For `%insert`, we fetch those children, snap them to the the current line's indent, and
transform them recursively as if this is where they were nested to begin with. If the block is missing, we raise an
error for required ones, or use its own children as the default, aligning them to `%insert`'s indentation.

It takes a while to get the hang of `snap`, so let's review the last scenario again. Suppose we have:

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

And not:

```html
<body>
        <p>hello world</p>
</body>
```

That is, transform `%insert`'s children, but without the extra spaces that were necessary only to delineate them as
such. Calling `snap()` before passing them into `transform` does exactly that: it shifts them 4 spaces back, aligning
them to their parent, and continues from there – a pattern that repeats itself often. For another example, take `%raw`:

```
def g_raw(gx):
    content = gx.children.snap().to_string()
    gx.add_text(gx.line.indent, content, crop=True, interpolate=False)
```

If we have:

```
<p>
    %raw
        {not_interpolated}
</p>
```

We'd like to end up with:

```html
<p>
    {not_interpolated}
</p>
```

So we snap the children to `%raw`'s indentation level before converting them into a string and passing them to
`add_text`. Normally, this function expects a single line; since our content might span multiple, we add `crop=True`,
as well as `interpolate=False` to make sure it remains, well, raw.

That's how the majority of macros work: inject some code or other, adjusting indentation if necessary, and recurse on
children after snapping them into place. But let's say we want to emulate the `%filesystem` plugin: how would we go
about a `%directory` macro? The obvious solution might look like:

```python
def g_directory(gx, name):
    gx.add_code("import os")
    gx.add_code(f"os.mkdir({name!r}, parents=True)")
    gx.add_code(f"os.chdir({name!r})")
    gx.transform(gx.line.children.snap())
    gx.add_code(f"os.chdir('..')")
```

That is, make sure `os` is available, create the directory, enter it, transform its children, and finally step out. Such
execution-time complexity, however, is best encapsulated in a hook: since we're dealing with Python, we can extend the
functions available to its runtime just as easily, making our code much cleaner:

```python
def g_directory(gx, name):
    gx.add_code("with directory({name!r}):")
    with gx.increased_code_indent():
        gx.transform(gx.line.children.snap())
```

And to have such a `directory` context manager during execution:

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
        os.chdir("..")
```

In other words, hooks (functions starting with `x_`) are available to the generated code, so macros (functions starting
with `g_`) can assume as much and generate code accordingly, delegating any runtime work to their corresponding hook.

There's much more to say about all the cool things we can do with this paradigm, but until I have time to write such a
guide, the best thing to do is look at the implementations of `auryn/plugins/core.py` and `auryn/plugins/filesystem.py`
and learn from there. We can add post-processing with `on_complete` (what `%extend` does), temporarily patch `output`
to replace it with our own list (how files capture and then write their content), replace line transformations when our
plugin loads (with `on_load` and `line_transform`), and so on. So, do let me know what fun ideas you come up with :)

### Understanding Errors

When working with so many layers of abstractions, bugs can be difficult to trace. For that reason, Auryn raises either
a `GenerationError` or an `ExecutionError`, depending on what phase the error occured in, and those come with a detailed
detailed, color-highlighted report. Suppose we have `template1.aur`:

```
%load plugin.py
%include template2.aur
```

And `template2.aur`:

```
%load plugin.py
%error
```

Which use `plugin.py`:

```
def g_error(gx):
    gx.add_code('error()')

def x_error(gx):
    raise ValueError('wat')
```

Executing the first template will include the second, which will call the `%error` macro, which will generate code that
will call a hook that raises an error at execution time. Following such a flow when all this code is executed
dynamically behind the scenes is no easy feat; so if something goes wrong, we can orient ourselves by catching the
exception (both inherit from `auryn.Error`) and printing its report:

```
>>> try:
...     execute("template1.aur")
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

This includes a dump of the context, the template traceback (including nested templates derived via e.g. %include) and
the code traceback with function-breadth views, where internal Auryn methods are dimmed out and problematic lines are
highlighted. You can't really see the colors in this README, but trust me, it's beautiful.

## CLI

Auryn comes with a command-line interface, available via the `auryn` command. Suppose we have `loop.aur`:

```
!for i in range(n):
    line {i}
```

Then:

```sh
$ auryn generate template.aur
for i in range(n):
    emit(0, 'line ', i)

$ auryn execute template.aur n=3
line 0
line 1
line 2
```

We can provide context either via key-value pairs (e.g. `n=3`), where values are parsed as JSON or used as strings if it
fails, or via an actual JSON with the `-c|--context FILE` option (or both).

To generate standalone code, we can use `generate` with the `-s|--standalone` flag; to later execute it, we have
`execute-standalone`:

```sh
$ auryn generate -s template.aur > code.py
$ auryn execute-standalone code.py n=3
line 0
line 1
line 2
```

To load additional hooks and macros, we add the `-l|--load PLUGIN` option followed by a plugin path or name; to load
multiple plugins, we add it multiple times. Given `hello.aur`:

```
%hello world
```

And the `hello.py` plugin:

```python
def g_hello(gx, name):
    gx.add_text(gx.line.indent, f"hello {name}")
```

We can do:

```sh
$ auryn execute -l hello.py hello.aur
hello world
```

## Local Development

Install the project with development dependencies:

```sh
$ poetry install --with dev
...
```

The `dev.py` script contains all the development-related tasks, mapped to Poe the Poet commands:

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