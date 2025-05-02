import pathlib

import pytest

from auryn import EvaluationError, Junk, render

from .conftest import trim, this_line

THIS_FILE = pathlib.Path(__file__)


def test_evaluation_error(tmp_path: pathlib.Path) -> None:
    template_path = tmp_path / "template.txt"
    template_code = trim(
        """
        %error {x}
        """
    )
    template_path.write_text(template_code)

    line_number = this_line(+15)
    pattern = trim(
        rf"""
        Failed to evaluate junk at {THIS_FILE.name}:{line_number}.
        Context:
          n: 3
        Traceback \(most recent call last\):
          Junk, line 2, in <module>
            > emit\(0, 'line ', j\)
            @ File "{THIS_FILE}", line {line_number+3}
                line \{{j\}}
        NameError: name 'j' is not defined
        """
    )
    with pytest.raises(EvaluationError, match=pattern):
        render(
            """
            !for i in range(n):
                line {j}
            """,
            n=3,
        )


def test_evaluation_error_nested(tmp_path: pathlib.Path) -> None:
    meta_path = tmp_path / "meta.py"
    meta_code = trim(
        """
        def error(x):
            raise ValueError(x)
        
        def meta_error(junk, x):
            junk.emit_code(f"error({junk.interpolate(x)})")
        
        def eval_error(junk, x):
            junk.emit(0, error(x))
        """
    )
    meta_path.write_text(meta_code)

    template_path = tmp_path / "template.txt"
    template_code = trim(
        """
        %error {x}
        """
    )
    template_path.write_text(template_code)

    line_number = this_line(+21)
    pattern = trim(
        rf"""
        Failed to evaluate junk at {THIS_FILE.name}:{line_number}.
        Context:
          x: 1
        Traceback \(most recent call last\):
          Junk, line 1, in <module>
            > error\(str\(x\)\)
            @ File ".*?/template.txt", line 1
                %error \{{x\}}
          File ".*?/meta.py", line 8, in eval_error
              def eval_error\(junk, x\):
            >     junk.emit\(0, error\(x\)\)
          File ".*?/meta.py", line 2, in error
              def error\(x\):
            >     raise ValueError\(x\)
        ValueError: 1
        """
    )
    with pytest.raises(EvaluationError, match=pattern):
        render(template_path, load=meta_path, x=1)


def test_evaluation_error_incomplete(tmp_path: pathlib.Path) -> None:
    meta_path = tmp_path / "meta.py"
    meta_code = trim(
        """
        def meta_error(junk, x):
            junk.emit_code(f"error({junk.interpolate(x)})")
        
        def eval_error(junk, x):
            raise ValueError(x)
        """
    )
    meta_path.write_text(meta_code)

    template_path = tmp_path / "template.txt"
    template_code = trim(
        """
        %error {x}
        """
    )
    template_path.write_text(template_code)

    line_number = this_line(+18)
    pattern = trim(
        rf"""
        Failed to evaluate junk at {THIS_FILE.name}:{line_number}.
        Context:
          x: 1
        Traceback \(most recent call last\):
          Junk, line 1, in <module>
            > error\(str\(x\)\)
            @ File ".*?/template.txt", line 1
                %error \{{x\}}
          File ".*?/meta.py", line 5, in eval_error
              def eval_error\(junk, x\):
            >     raise ValueError\(x\)
        ValueError: 1
        """
    )
    with pytest.raises(EvaluationError, match=pattern):
        render(template_path, load=meta_path, x=1)

    line_number = this_line(+1)
    junk = Junk(template_path)
    junk.load(meta_path)
    junk.transpile()

    meta_path.unlink()
    pattern = trim(
        rf"""
        Failed to evaluate junk at {THIS_FILE.name}:{line_number}.
        Context:
          x: 1
        Traceback \(most recent call last\):
          Junk, line 1, in <module>
            > error\(str\(x\)\)
            @ File ".*?/template.txt", line 1
                %error \{{x\}}
          File ".*?/meta.py", line 5, in eval_error
            \? \(file .*?/meta.py does not exist\)
        ValueError: 1
        """
    )
    with pytest.raises(EvaluationError, match=pattern):
        junk.evaluate(x=1)

    meta_path.write_text("")
    pattern = trim(
        rf"""
        Failed to evaluate junk at {THIS_FILE.name}:{line_number}.
        Context:
          x: 1
        Traceback \(most recent call last\):
          Junk, line 1, in <module>
            > error\(str\(x\)\)
            @ File ".*?/template.txt", line 1
                %error \{{x\}}
          File ".*?/meta.py", line 5, in eval_error
            \? \(file .*?/meta.py has only 0 lines, unable to find line 5\)
        ValueError: 1
        """
    )
    with pytest.raises(EvaluationError, match=pattern):
        junk.evaluate(x=1)

    meta_path.write_text(meta_code)
    template_path.unlink()
    pattern = trim(
        rf"""
        Failed to evaluate junk at {THIS_FILE.name}:{line_number}.
        Context:
          x: 1
        Traceback \(most recent call last\):
          Junk, line 1, in <module>
            \? \(template .*?/template.txt does not exist\)
          File ".*?/meta.py", line 5, in eval_error
              def eval_error\(junk, x\):
            >     raise ValueError\(x\)
        ValueError: 1
        """
    )
    with pytest.raises(EvaluationError, match=pattern):
        junk.evaluate(x=1)

    template_path.write_text("")
    pattern = trim(
        rf"""
        Failed to evaluate junk at {THIS_FILE.name}:{line_number}.
        Context:
          x: 1
        Traceback \(most recent call last\):
          Junk, line 1, in <module>
            \? \(template .*?/template.txt has only 0 lines, unable to find line 1\)
          File ".*?/meta.py", line 5, in eval_error
              def eval_error\(junk, x\):
            >     raise ValueError\(x\)
        ValueError: 1
        """
    )
    with pytest.raises(EvaluationError, match=pattern):
        junk.evaluate(x=1)