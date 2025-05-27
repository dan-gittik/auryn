from __future__ import annotations

import inspect
import pathlib


class Origin:
    """
    The definition site of a GX object.

    Attributes:
        path: The path the GX is defined in.
        line_number: The line number the GX is defined on.
        gx: The GX this GX is defined in, if it's created as part of an ongoing generation (e.g. with %include).
    """

    def __init__(self, path: pathlib.Path, line_number: int, gx: GX | None) -> None:
        self.path = path
        self.line_number = line_number
        self.gx = gx

    def __str__(self) -> str:
        return f"{self.path}:{self.line_number}"

    def __repr__(self) -> str:
        return f"<{self}>"

    @classmethod
    def infer(cls, stack_level: int) -> Origin:
        """
        Infer the origin from the current stack.

        Arguments:
            stack_level: How many frames to ascend before inferring the origin.
                This is used to skip over wrapper scopes; for example, a user calls execute, which creates a GX, which
                infers the origin. Each wrapper should accept a stack_level keyword-only argument with a default value
                of 0, so it can be wrapped further if necessary, and pass on stack_level + 1, so its frame is skipped.
                In our example, execute (stack_level=0) calls GX.__init__ (stack_level=1), which calls Origin.infer
                (stack_level=2), so a total of 3 frames are skipped: Origin.infer, GX.__init__ and execute, ending up at
                the user's code as the origin.

        Returns:
            The inferred origin.
        """
        frame = inspect.currentframe()
        for _ in range(stack_level + 1):
            frame = frame and frame.f_back
        if not frame:
            raise RuntimeError("unable to infer origin")
        path = pathlib.Path(frame.f_code.co_filename)
        line_number = frame.f_lineno
        return cls(path, line_number, None)

    @classmethod
    def derive(cls, gx: GX) -> Origin:
        """
        Derive the origin from an ongoing generation.

        This happens when one GX is created inside another, e.g. with %include. If the parent GX template is a file, the
        origin path is its path, and the origin line number is the current line number; if it's a string, the origin
        path is the parent's origin path, and the origin line number is the the parent's origin line number offset by
        the current line number (since it is effectively defined later in the same file).

        Arguments:
            gx: The ongoing generation.

        Returns:
            The derived origin.
        """
        if gx.template.path:
            path = gx.template.path
            line_number = gx.line.number
        else:
            path = gx.origin.path
            line_number = gx.origin.line_number + gx.line.number
        return cls(path, line_number, gx)


from .gx import GX
