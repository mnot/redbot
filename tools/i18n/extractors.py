import ast
from typing import Any, Iterator, Tuple, List
from babel.messages.extract import extract_python


def keyword_names(value: Any) -> List[str]:
    """
    Normalise a Babel 'keywords' option to a list of function names.

    Babel < 2.18 hands the per-section option from babel.cfg over as the raw
    string ("L_ translate"); 2.18 and later pass a dict of parsed keywords.
    """
    if not value:
        return []
    if isinstance(value, str):
        return value.split()
    return list(value)  # dict keys, list or tuple


def extract_notes(
    fileobj, keywords, comment_tags, options
) -> Iterator[Tuple[int, str, List[str], List[str]]]:
    """
    Extract messages from Note subclasses in Python source code.

    This looks for classes that inherit from 'Note' (or 'RedbotNote') and extracts the strings
    assigned to '_summary' and '_text'.

    It also delegates to the standard Python extractor to find other messages.
    """
    # Read content for AST parsing
    content = fileobj.read()
    tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Check if class inherits from Note (simple check)
            is_target = False
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id in ["Note", "RedbotNote"]:
                    is_target = True
                    break
                # Handle module.Note
                if isinstance(base, ast.Attribute) and base.attr in ["Note", "RedbotNote"]:
                    is_target = True
                    break

            if is_target:
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name) and target.id in [
                                "_summary",
                                "_text",
                            ]:
                                if isinstance(item.value, ast.Constant) and isinstance(
                                    item.value.value, str
                                ):
                                    yield (item.lineno, "_", [item.value.value], [])
                                # Handle multiline strings (which might be parsed differently depending on python version, but usually Constant)

    # Delegate to standard python extractor
    fileobj.seek(0)

    # Merge keywords from options
    extra_keywords = keyword_names(options.get("keywords"))

    all_keywords = list(keywords) + extra_keywords

    # We need to pass a container that supports 'in' to extract_python.
    # A list is fine.

    for lineno, funcname, messages, comments in extract_python(
        fileobj, all_keywords, comment_tags, options
    ):
        if funcname in extra_keywords:
            # Names listed in babel.cfg lose any argument-position spec that
            # Babel 2.18 carries in the dict values. L_ and translate take the
            # default (1,), so that is harmless today; a cfg entry such as
            # 'ngettext:1,2' must be registered through Babel's own keyword
            # mechanism instead.
            funcname = None
        yield (lineno, funcname, messages, comments)
