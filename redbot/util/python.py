from typing import Dict, Optional

from importlib_resources import files as resource_files
from importlib_resources.abc import Traversable


def module_files(module: str) -> Dict[str, bytes]:
    """
    Given a module name, return a dictionary containing the contents of that
    directory in the Python package.
    """
    out: Dict[str, bytes] = {}

    def walk(obj: Traversable, prefix: Optional[str] = None, top: bool = False) -> None:
        if top:
            name = None
        elif prefix:
            name = "/".join([prefix, obj.name])
        else:
            name = obj.name
        if obj.is_dir():
            for subobj in obj.iterdir():
                walk(subobj, name)
        if obj.is_file() and name:
            out[name] = obj.read_bytes()

    walk(resource_files(module), top=True)
    return out
