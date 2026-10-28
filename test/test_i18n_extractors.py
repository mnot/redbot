import io
import unittest
from itertools import product
from typing import Any, List, Optional, Tuple

from tools.i18n.extractors import extract_notes, keyword_names

SOURCE = b"""
L_("with local keyword")
translate("with other keyword")
_("with default keyword")
ignored("not a keyword")
"""

# The shapes Babel has used for the per-section 'keywords' option in babel.cfg:
# the raw string (< 2.18) and a dict of parsed keywords (>= 2.18); a list is
# what extract_notes used to accept for any other caller.
SHAPES = {
    "str": "L_ translate",
    "dict": {"L_": None, "translate": None},
    "list": ["L_", "translate"],
    "tuple": ("L_", "translate"),
}

# The global keywords Babel passes positionally: 2.17 passes only the defaults,
# 2.18 has already merged in the per-section ones.
POSITIONAL = {
    "babel_2_17": ["_"],
    "babel_2_18": ["_", "L_", "translate"],
}

Result = List[Tuple[int, Optional[str], Any, List[str]]]


def run_extractor(keywords_option: Any, positional: List[str]) -> Result:
    return list(
        extract_notes(
            io.BytesIO(SOURCE),
            positional,
            [],
            {"keywords": keywords_option},
        )
    )


class TestExtractorKeywords(unittest.TestCase):
    def test_keyword_names(self) -> None:
        for name, shape in SHAPES.items():
            with self.subTest(shape=name):
                self.assertEqual(keyword_names(shape), ["L_", "translate"])

    def test_keyword_names_empty(self) -> None:
        for empty in (None, "", {}, []):
            with self.subTest(empty=empty):
                self.assertEqual(keyword_names(empty), [])

    def test_extra_keywords_extracted(self) -> None:
        for (name, shape), (pname, positional) in product(SHAPES.items(), POSITIONAL.items()):
            with self.subTest(shape=name, positional=pname):
                self.assertEqual(
                    [
                        (lineno, funcname, messages)
                        for lineno, funcname, messages, _ in run_extractor(shape, positional)
                    ],
                    [
                        (2, None, "with local keyword"),
                        (3, None, "with other keyword"),
                        (4, "_", "with default keyword"),
                    ],
                )

    def test_shapes_agree(self) -> None:
        expected = run_extractor(SHAPES["str"], POSITIONAL["babel_2_17"])
        for (name, shape), (pname, positional) in product(SHAPES.items(), POSITIONAL.items()):
            with self.subTest(shape=name, positional=pname):
                self.assertEqual(run_extractor(shape, positional), expected)

    def test_no_keywords_option(self) -> None:
        results = list(extract_notes(io.BytesIO(SOURCE), ["_"], [], {}))
        self.assertEqual([r[2] for r in results], ["with default keyword"])


if __name__ == "__main__":
    unittest.main()
