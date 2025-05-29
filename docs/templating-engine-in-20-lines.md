# A Templating Engine in 20 Lines

In the book [The Architecutre of Open-Source Applications: 500 Lines or Less](https://aosabook.org/en/), experienced
programmers solve interesting problems from real-life projects — it's an excellent read, full of practical insights into
software design; and in [one of its chapters](https://aosabook.org/en/500L/a-template-engine.html), Ned Batchelder
describes the motivation, challenges and solutions of writing a templating engine.

Here's the gist: most programs contain a lot of code, and only a little text, so programming languages are designed for
code — text is simply enclosed in quotes and managed in strings:

```pycon
>>> def hello():
...     print("Hello, world!")
```

For programs that deal with a lot of text, like a webserver generating custom HTML for every request, this can become an
issue. Even in a language as powerful and elegant as Python, something as simple as generating the HTML for a list of
`n` items turns out to be regrettably clunky:

```pycon
>>> html = ["<ul>"]
>>> for i in range(n): # Suppose n = 3
...     html.append(f"    <li>{i}</li>")
... html.append("</ul>")
... print("\n".join(html))
<ul>
    <li>0</li>
    <li>1</li>
    <li>2</li>
</ul>
```

Imagine how unintelligible a real, complicated webpage would look like. So what do we do?

## Templating Engines

To address such cases, it makes sense to design a "textual" programming language — one where the interpretation is
reversed, and everything is treated as text, except what little code is enclosed in special brackets, like so:

```html
<ul>
    {% for i in range(n) %}
    <li>{{ i }}</li>
    {% endfor %}
</ul>
```

This is much clearer, and much more maintainable; and, when executed with e.g. `n=3`, should result in the desired
output:

```html
<ul>
    <li>0</li>
    <li>1</li>
    <li>2</li>
</ul>
```

This syntax is not imaginary; it's exactly how a templating library like
[Jinja2](https://jinja.palletsprojects.com/en/stable/) works:

```pycon
>>> import jinja2
>>> template = jinja2.Template("""\
... <ul>
...     {%- for i in range(n) %}
...     <li>{{ i }}</li>
...     {%- endfor %}
... </ul>
... """)
>>> result = template.render(n=3)
>>> print(result)
<ul>
    <li>0</li>
    <li>1</li>
    <li>2</li>
</ul>
```

Such "textual" programs are called **templates**. Their code is enclosed in **tags**, both for statements
(`{% like this %}`) and for expressions (`{{ like_this }}`). Given a specific context (e.g. `{"n": 3}`), such templates
can be **rendered** — in which case their statements are evaluated, and their expressions are **interpolated** into
some output.

This is done by a **templating engine**, and there are several ways to implement it.
[Django](https://www.djangoproject.com/) uses *interpretation*: parsing the template into different tags, running their
respective logics, and concatenating the result. Jinja2 and [Mako](https://www.makotemplates.org/) use *compilation*:
analyzing the template, and generating equivalent Python code that, once executed, produces the desired output. This
technique is faster, since it only parses the template once; after the template is translated into code, it can be
invoked on different contexts to generate different outputs quickly and easily (which is exactly what a webserver
needs). However, it's also more difficult, since instead of simply reacting to each tag as it comes, we need to convert
it into valid, analogous code that will only run later, and stitch all the snippets together in a coherent way. Ned
describes how to do exactly that, and covers a lot of clever tricks along the way.

## Generation/Execution

In both approaches, however, a big challenge remains: we end up with a new, domain-specific templating language, which
we have to implement and maintain ourselves. So it's worth asking ourselves whether Python itself can be used for
templating; if only we find a way to do it, we'd be able to delegate all the hard "language handling" stuff to the
runtime. Recall our very first attempt:

```python
print("<ul>")
for i in range(n):
    print(f"    <li>{i}</li>")
print("</ul>")
```

While it's cumbersome, it's mostly because of all the `print`s; and isn't this the whole problem of dealing such
"textual" programs in a nutshell?

What if instead of inventing a whole new grammar for tags, we only introduce a simple way to distinguish between
*code lines* — that is, lines that should be evaluated — and *text lines*, which should be printed? We can use the `!`
character to set them apart, since it's not valid in Python anyway; consider, then, a template like this:

```
<ul>
    !for i in range(n):
        <li>{i}</li>
</ul>
```

Not only is it elegant, but it's pretty easy to implement — and once we do, we get a full-fledged templating language,
pretty much as flexible as Python itself. All we need to do is go over the lines, and:

- For lines starting with `!`, peel it off and leave the rest as is;
- For lines that don't start with `!`, turn them into a `print("<line>")` statement.
- Execute the generated code to produce the desired output.

I don't know of a good theoretical name for such a process: it's not exactly compilation, since the intermediary
representation we're translating our "source" template to is not some bytecode or data structure, but an actual Python
program; and it's not exactly transpilation either, since our "!-templatese" is not per say a programming language, but
a combination of several. For simplicity's sake, then, let's call this two-step process **generation/execution**: first,
we generate code according to some template, and then we execute it.

Two things we need to address, though, are interpolation and indentation.

## Solving Interpolation

Interpolation is about detecting inline expressions in strings and substituting them for their values, like inserting
the actual `i` into each `<li>{i}</li>`. Since we're dealing with a text line, it's bound to become print-statement — so
it's not immediately clear how to parse, execute and replace all its necessary bits. While this basic scenario can be
patched with `replace("{i}", i)`, this obviously wouldn't work for something more elaborate like `{i + 1}`, let alone
`{obj.method(i)}`.

Luckily, Python supports exactly that with f-strings — so let's use those instead of regular strings, and let Python do
the heavy lifting. It may sound like an escaping nightmare, but it's actually pretty straightforward, thanks to the
builtin `repr` function: it gives us a properly escaped representation of a string, and can be applied by appending `!r`
to any formatting clause. Here, see for yourself:

```pycon
>>> s = "<li>{i}</li>"
>>> print(s)
<li>{i}</li>
>>> print(repr(s))
'<li>{i}</li>'
>>> print(f"{s!r}")
'<li>{i}</li>'
>>> print(f"print(f{s!r})")
print(f'<li>{i}</li>')
```

The last bit can be confusing at first, since we print an f-string that results in code that prints an f-string — but
once we wrap our head around it, the nice thing about its result is that we can evaluate it for a specific `i`, which
will interpolate our original line just like we wanted:

```pycon
>>> eval(f"print(f{s!r})", {"i": 0})
<i>0</i>
```

And just to prove a point, let's do it on a string that contains quotes and some non-trivial code that needs to be
executed:

```pycon
>>> s = "<li>{['a', 'b'][i]}</li>"
>>> eval(f"print(f{s!r})", {"i": 0})
<li>a</li>
>>> eval(f"print(f{s!r})", {"i": 1})
<li>b</li>
```

Pretty neat, no? To be fair, f-strings have their limits — if the code contains curly braces (e.g. `{{"x": 1}["x"]}`),
Python won't be able to handle it alone; but we'll figure out ways to bypass it later.

## Solving Indentation

Indentation is a bit more nuanced. On the one hand, we'd like to preserve indentation for text lines, so that:

```
<p>
    Hello, world!
</p>
```

Becomes:

```python
print(f"<p>")
print(f"    Hello, world!") # note the extra whitespace
print(f"</p>")
```

On the other hand, for Python to work properly, code lines need to be indented themselves. For example:

```
!if image:
    <img src="{image}" />
```

Should become:

```python
if image:
    print(f"<img src='{image}' />")
```

And not:

```python
if image:
print(f"    <img src='{image}' />")
```

What's more, we'd like to support arbitrary indentation that makes "intuitive sense", as in:

```
<section>
    <h1>Title</h1>
    !if hello:
        <p>
            Hello, world!
        </p>
</section>
```

Becoming:

```python
print(f"<section>")
print(f"    <h1>Title</h1>")
if hello: # note the extra whitespace for the entire block:
    print(f"    <p>")
    print(f"        Hello, world!")
    print(f"    </p>")
print(f"</section>")
```

Which becomes (if `hello=True`):

```html
<section>
    <h1>Title</h1>
    <p>
        Hello, world!
    </p>
</section>
```

To do that, consider that we actually have two types of indentation: one for text, which can be arbitrary, and one for
code, which should be valid in Python. The code indentation can only increase when we encounter a code line with a
nested block, as in:

```
    !if hello:
        <p>
            Hello, world!
        </p>
```

In this case, let's assume that subsequent lines that are indented more than 4 spaces farther are part of the block; and
that any space after those 4, as well as any space before the code itself, is preserved. If we mark the text indent in
underscores, and the code indent in dots, the difference becomes more visible:

```
____!if hello:
____....<p>
____....____Hello, world!
____....</p>
```

This works well for nested code, too:

```
____!if hello:
____....<p>
____....____!if name:
____....____....Hello, {name}!
____....____!else:
____....____....Hello, world!
____....</p>
```

When this code is evaluated, any code indentation should be removed, so we end up with the text indentation only:

```
____<p>
________Hello, world!
____</p>
```

In other words, we add a small rule: for code lines to have bodies (like if-statements and for-loops do), any nested
line must be indented by *at least* 4 more spaces, which disappear from the final result. Once you get used to it, it's
pretty sensical, and works out in all sorts of edge cases. What's more — it's relatively easy to implement!

To do that, we'll use a stack (or in Python, a list). For every line, we peel off it initial whitespace, and call it the
*full* indentation. Whenever we encounter a code line, we push its full indentation unto the stack (that is, append it
to the list); so in effect, the stack size (list length) represents the level of *code* indentation (in multiples of 4),
while the *text* indentation is simply the difference between the two: that is, the full indentation of the current
line, minus the list length times four — the whitespace reserved to making our Python code valid.

This, however, assumes that every line is nested ever further in previous code lines, so we need to address dedenting as
well. Whenever we encounter a line that is indented 4 spaces less than the indentation at the top of the stack (the last
item of the list), we can infer that it is not nested inside the previous code line; in which case we keep popping the
stack until we arrive at an indentation that does accommodate it, or until we end up with an empty stack, meaning we're
back to the root level of no code indentation at all.

In any case, once we figure out the code indentations, we're golden: for code lines we simply add those indentations (as
in `<code-indent><code>`); for text lines we add them to the print-statement, and text indentations to the printed text
(as in `<code-indent>print(f"<text-indent><text>")`). Honestly, it's easier to read the code than the description:

```pycon
>>> import re

>>> def generate(template):
...     stack = []
...     code = []
...     for line in template.strip().splitlines():
...         whitespace, content = re.match(r"^(\s*)(.*)$", line).groups()
...         full_indent = len(whitespace)
...         while stack and full_indent < stack[-1] + 4:
...             stack.pop()
...         code_indent = len(stack) * 4
...         if content.startswith("!"):
...             code.append(" " * code_indent + content[1:])
...             stack.append(full_indent)
...         else:
...             text_indent = full_indent - code_indent
...             text = " " * text_indent + content
...             code.append(" " * code_indent + f"print(f{text!r})")
...     return "\n".join(code)
```

And it works:

```pycon
>>> print(generate("""
... <ul>
...     !for i in range(n):
...         <li>{i}</li>
... </ul>
... """))
print(f'<ul>')
for i in range(n):
    print(f'    <li>{i}</li>')
print(f'</ul>')

>>> print(generate("""
... <section>
...     <h1>Title</h1>
...     !if hello:
...         <p>
...             Hello, world!
...         </p>
... </section>
... """))
print(f'<section>')
print(f'    <h1>Title</h1>')
if hello:
    print(f'    <p>')
    print(f'        Hello, world!')
    print(f'    </p>')
print(f'</section>')
```

It even gives us many features that aren't supported by most other templating languages, like assignment and while
loops:

```pycon
>>> print(generate("""
... !i = 0
... !while i < n:
...     <p>{i}</p>
...     !i += 1
... """))
i = 0
while i < n:
    print(f'<p>{i}</p>')
    i += 1
```

## Solving Execution

All that's left is to actually execute the code, which is easy enough with Python's builtin `exec` function:

```pycon
>>> exec("""
... for i in range(n):
...     print(f"<li>{i}</li>")
... """, {"n": 3})
<li>0</li>
<li>1</li>
<li>2</li>
```

One tricky thing we're going to do, though, is replace the standard `print` function with one that "steals" the output
into a list, which we can then concatenate and return as a string. Let's write it separately, before combining the two:

```pycon
>>> def execute(code, **context):
...     output = []
...     context["print"] = lambda line: output.append(line)
...     exec(code, context)
...     return "\n".join(output)

>>> output = execute("""
... for i in range(n):
...     print(f"<li>{i}</li>")
... """, n=3)
>>> print(output)
<li>0</li>
<li>1</li>
<li>2</li>
```

This way, we're not bound to the standard output, and end up with a rendered output just like we did in Jinja2. And if
we feed `execute` with `generate`'s output, we get proper templating:

```pycon
>>> execute(generate("""
... <ul>
...     !for i in range(n):
...         <li>{i}</li>
... </ul>
... """), n=3)
<ul>
    <li>0</li>
    <li>1</li>
    <li>2</li>
</ul>
```

Except, of course, it's a bit clumsy to invoke it this way, so let's put the two together:

```pycon
>>> def execute(template, **context):
...     stack = []
...     code = []
...     output = []
...     for line in template.strip().splitlines():
...         whitespace, content = re.match(r"^(\s*)(.*)$", line).groups()
...         full_indent = len(whitespace)
...         while stack and full_indent < stack[-1] + 4:
...             stack.pop()
...         code_indent = len(stack) * 4
...         if content.startswith("!"):
...             code.append(" " * code_indent + content[1:])
...             stack.append(full_indent)
...         else:
...             text = " " * (full_indent - code_indent) + content
...             code.append(" " * code_indent + f"print(f{text!r})")
...     context["print"] = lambda line: output.append(line)
...     exec("\n".join(code), context)
...     return "\n".join(output)
```

Which gives us:

```
>>> output = execute("""
... <section>
...     <h1>Title</h1>
...     !if hello:
...         <p>
...             Hello, world!
...         </p>
... </section>
... """, hello=True)
>>> print(output)
<section>
    <h1>Title</h1>
    <p>
        Hello, world!
    </p>
</section>
```

If you reflect for a moment on what we just did — it's a full-fledged templating engine in less than 20 lines of Python
code. Jinja, while obviously more sophisticated (even though we actually support quite a lot of functionality it
doesn't...) clocks more than 14,000 lines, and Ned's minimalistic example takes 250 — so our little render function is
pretty cool, if I might say so myself.

## 2-Step Code Generation

But I'd argue that it's more than cool — there's an idea here that, once properly articulated, has some pretty
far-reaching ramifications. The reason we managed to pack so much power into such a short function is the following
conceptual leap: converting lines, some code and some text, into intermediary Python code, that we then execute to
generate the actual output. This two-step approach to code generation, whereby we essentially generate code that
generates code, is not only deliciously meta, but surprisingly powerful. Usually, intermediary representations are
compact, abstract and limited instruction sets, since it's effectively another language to implement and maintain (like
we saw with other templating engines). Here, we get it for free, by way of Python itself: and it comes with all sorts of
advanced features, from exceptions and context managers to dynamic evaluation, that let us inject sophisticated
functionality into the code generation process.

Take the following scenario. Given a data model:

```pycon
>>> model = {
...     "n": {
...         "type": "integer",
...         "min": 1,
...         "max": 10,
...     },
...     "p": {
...         "type": "object",
...         "attributes": {
...             "x": {
...                 "type": "integer",
...             },
...             "y": {
...                 "type": "integer",
...             },
...         },
...     },
... }
```

We'd like to generate simple, efficient code that validates its structure:

```pycon
>>> def validate(n, p):
...     if not isinstance(n, int):
...         raise ValueError(f"expected {n=} to be an integer")
...     if n < 1:
...         raise ValueError(f"expected {n=} >= 1")
...     if n > 10:
...         raise ValueError(f"expected {n=} <= 10")
...     if not isinstance(p, object):
...         raise ValueError(f"expected {p=} to be an object")
...     if not isinstance(p.x, int):
...         raise ValueError(f"expected {p.x=} to be an integer")
...     if not isinstance(p.y, int):
...         raise ValueError(f"expected {p.y=} to be an integer")
```

This is all trivial boilerplate, so it really feels like it ought to be auto-generatable; but the potential for
recursion — namely that `p` is an object containing `x` and `y`, and it's easy to imagine deeper nesting, too — makes it
difficult to address.

To gain an intuition, you can think of "regular" code generation as search-and-replace: if we have a macro
`ADD(x, y) -> x + y`, then applying it to `ADD(1, 2)` will result in `1 + 2`. But what if we apply it to
`ADD(ADD(1, 2), 3)`? Easy enough to get `ADD(1, 2) + 3`, but for `1 + 2 + 3` we'll need repeated application.
Implementation aside, the reason for this is that the intermediate representation (in this case, probably a parsed tree
of `ADD`, `1`, `2`) doesn't support recursion. To give another example, take Python's bytecode: we can reduce a function
call into a `CALL` opcode, but there's no concept of calling in the opcode-language, is there? That is, it's meant to
spoon-feed the interpreter, and as such doesn't allow much freedom beyond what's absolutely essential to do so.

Not so in our case: because our intermediate representation is actually Python, we have all of its capabilities for
free — including function definition and invocation. It's confusing to wrap your head around it, at first, since we're
generating Python code that will generate Python code, but that's the 2-step paradigm for you:

```
!def check_integer(name, min=None, max=None):
    if not isinstance({name}, int):
        raise ValueError(f'expected {{{name}=}} to be an integer')
    !if min is not None:
        if {name} < {min}:
            raise ValueError(f'expected {{{name}=}} >= {min}')
    !if max is not None:
        if {name} > {min}:
            raise ValueError(f'expected {{{name}=}} <= {max}')
!check_integer('n', 1, 10)
```

This will generate the following code:

```python
def check_integer(name, min=None, max=None):
    print(f'if not isinstance({name}, int):')
    print(f"    raise ValueError(f'expected {{{name}=}} to be an integer')")
    if min is not None:
        print(f'if {name} < {min}')
        print(f"    raise ValueError(f'expected {{{name}=}} >= {min}')")
    if max is not None:
        print(f'if {name} > {max}:')
        print(f"    raise ValueError(f'expected {{{name}=}} <= {max}')")
check_integer('n', 1, 10)
```

Which, once rendered, will result in:

```python
if not isinstance(n, int):
    raise ValueError(f'expected {n=} to be an integer')
if n < 1:
    raise ValueError(f'expected {n=} >= 1')
if n > 10:
    raise ValueError(f'expected {n=} <= 10')
```

But note that we did it using a function — which means we can both compose and recurse with ease:

```
!def check_types(name, config):
    !if config['type'] == 'integer':
        !check_integer(name, config.get('min'), config.get('max'))
    !if config['type'] == 'object':
        if not isinstance({name}, object):
            raise ValueError(f'expected {{{name}=}} to be an object')
        !for key, value in config['attributes'].items():
            !check_types(f'{name}.{key}', value)
```

This we can then embed into the larger validation template:

```
def validate(
    !for key in model:
        {key},
):
    !for key, value in model.items():
        !check_types(key, value)
```

So if we save all three meta-definition in a template and execute it:

```
>>> template = "..."
>>> print(execute(template, model=model))
def validate(
    n,
    p,
):
if not isinstance(n, int):
    raise ValueError(f'expected {n=} to be an integer')
if n < 1:
    raise ValueError(f'expected {n=} >= 1')
if n > 10:
    raise ValueError(f'expected {n=} <= 10')
if not isinstance(p, object):
    raise ValueError(f'expected {p=} to be an object')
if not isinstance(p.x, int):
    raise ValueError(f'expected {p.x=} to be an integer')
if not isinstance(p.y, int):
    raise ValueError(f'expected {p.y=} to be an integer')
```

We successfully generate exactly what we wanted, recursion and all. Or at least, *almost* exactly what we wanted, since
`validate`'s body indentation is off — we didn't account for function invocation in our initial implementation, so this
bit:

```
    !for key, value in model.items():
        !check_types(key, value)
```

Results in this intermediary code:

```python
for key, value in model.items():
    check_types(key, value)
```

Which doesn't keep track of the extra text indentation that should be appended to its output. No matter, we'll fix it
later; the fact that our 20-line `execute` supports recursive generation out of the box is more than enough for a measly
first attempt.

## Too Meta, Too Early: A Brief History of Code Generation

Before we dive into the details, however, it's worth addressing code generation in general. It's not a new idea: in
fact, it's a pretty inescapable idea, once you start programming. Since the entire point of writing code is to capture
abstract models and flows, and find ways to simulate and automate them, it's only natural to apply the same kind of
thinking to coding itself, and wonder whether it can be abstracted and automated. Still, from my experience, people give
up on it pretty quickly: it's a curious idea, but they don't really trust it. Something about it feels too advanced, or
error-prone, or otherwise scary; interesting in theory, no doubt, but rarely useful in practice.

The same argument can be made against any unfamiliar technology or unpopular opinion — when in fact, if something feels
too advanced or error-prone, it's usually a failure of design or education. Admittedly, programming for code generation
is more complex than plain programming — maybe even an order of conceptual magnitude more so; but then, how did
high-level languages, where a single expression can be translated into dozens of machine instructions, feel to low-level
programmers at first? To paraphrase Arthur C. Clarke: it might look like magic, but when you understand it sufficiently
well, it's just technology. So the important question, really, is how to simplify and accelerate such understanding.
What levels of abstractions will let us reason about it and manage it better? Could we harness its power, also arguably
an order of magnitude higher?

I think we can; and the reason that we haven't yet is mostly historical. Code generation was suggested already in the
1940s and attempted already in the 1960s, even though it doesn't necessarily look this way. You can find it sitting
unabashedly right at the heart of the oldest programming language still in popular use: the C preprocessor. The 
`#include <HEADER>` statement is not like Python's `import`: it quite literally copy-pastes the referenced header in its
place, before the "processed" code is passed on for actual compilation. Similarly, the `#define NAME VALUE` directive
pretty much copy-pastes its value wherever its name appears in the code (supporting some parameterization for macros).
Such raw code manipulation is tremendously useful, but doing so in a language as old and low-level as C might have
contributed to the idea's overall notoriety.

In fact, I would argue that something similar happened with artificial intelligence: it started in the 1960s, way before
hardware was powerful enough, or data plentiful enough, to get any interesting results. Eventually, interest in i
waned, as excitement turned to disappointment; but when the hardware and data finally caught up, it came back with a
vengeance. What if the same is true for code generation, or metaprogramming in general? When it just started,
programming languages, runtime environments and development tools were quite crude; now that software is powerful enough
to accommodate it, maybe it's worth revisiting.

I'd even suggest that such a renaissance is already ongoing, if somewhat slowly and hesitantly. You can see it in
Google's [ProtoBuf](https://protobuf.dev/), where a data schema in a meta-language is used to generate actual
serialization and deserialization code in your favorite language; or in
[Swagger Codegen](https://swagger.io/tools/swagger-codegen/), where an API schema is used to generate boilerplate code
for servers that produce it and clients that consume it. You can even see it in the Angular framework, which has become
so cumbersome and verbose that it comes with a built-in [command-line interface](https://angular.dev/tools/cli) to
generate all the boilerplate it requires.

But there's still some suspicion about the subject. ProtoBuf is a black box: if you were to look at the generated code,
it ain't pretty. Code generation is seen as an implementation detail — a dirty little secret that you shouldn't worry
about, just utilize. With Angular CLI, generated code is admittedly visible; but then, it's restricted to the most
obvious, tedious and repetitive parts (and those don't really matter anyway). Generating anything too substantial feels
taboo — like, how could it possibly be better than handcrafted code without being mindbendingly complex? And even if it
could, how would we maintain and extend it, like reconcile manual changes with auto-generated ones?

I think these questions are not only fascinating, but quiet urgent. More and more AI-driven tools, like GitHub Co-pilot
and ChatGPT, offer to do our code generation for us; and as they get better, they might have a profound effect on
software engineering as a field. I don't think they will replace programmers; the main challenge in making good software
isn't writing code, anyway, but articulating the right problems, coming up with coherent abstractions, designing good
interfaces, etc. — all of which are inherently social.

But I do worry that overreliance on such "AI metaprogramming" would lead to a decline in the craft of code-writing, just
like overreliance on IDEs has. Fluency in code, secondary to making good software though it may be, is still invaluable:
as anyone who did any software design or implementation can attest, one can't be done well without the other. There are
complex and intricate feedback loops between them, and the programmer's skill matters not just for getting the job done,
but for reasoning eloquently about what the job even is.

In this sense, AI metaprogramming may increase productivity, but in the process lead to such dependence, and on such
opaque practices, as to render programmers quite helpless without it, and quite disempowered and unimaginative in
general. A different way to go about it, which I'm exploring in this here codebase, is to develop more convivial tools:
technologies that are more accessible and engaging, so as to foster autonomy and creativity, not just efficiency. In
light of this, the main aim of this project is to discover how such a metaprogramming framework might look like.
