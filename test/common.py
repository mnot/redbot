
import os
import sys

_loaded = False

def loadAllModules(dir):
    """
    Load all modules in a directory.
    """
    global _loaded
    if not _loaded:
        sys.path.insert(0, dir)
        for root, dirs, files in os.walk(dir):
            root = os.path.relpath(root, dir)
            if root in ['test', 'bin']:
                continue
            for name in files:
                base, ext = os.path.splitext(name)
                if ext != '.py':
                    continue
                if base == 'setup':
                    continue
                if base == "__init__":
                    base = ""
                else:
                    base = ".%s" % base
                module_name = "%s%s" % ('.'.join(root.split("/")), base)
                __import__(module_name)
        _loaded = True

def checkSubClasses(cls, check):
    """
    Run a check(subclass) function on all subclasses of cls.
    """
    loadAllModules('./')
    for subcls in cls.__subclasses__():
        check(subcls)
