from . import core, filesystem

plugins = {
    "core": vars(core),
    "filesystem": vars(filesystem),
}

__all__ = ["plugins"]
