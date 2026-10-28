import os
import tempfile
import unittest

from babel.messages import Catalog, pofile

from tools.i18n.clear_fuzzy import clear_fuzzy, clear_fuzzy_file


def build_catalog() -> Catalog:
    catalog = Catalog(locale="fr", fuzzy=False)
    catalog.add("new text", "ancien texte", flags=["fuzzy"], previous_id="old text")
    catalog.add("kept", "gardé", user_comments=["note on kept"])
    catalog.add("empty")
    catalog.add(
        ("one thing", "many things"),
        ("une chose", "des choses"),
        flags=["fuzzy"],
        previous_id=("one item", "many items"),
    )
    return catalog


class TestClearFuzzy(unittest.TestCase):
    def test_clears_only_fuzzy_entries(self) -> None:
        catalog = build_catalog()
        self.assertEqual(clear_fuzzy(catalog), 2)

        fuzzy = catalog.get("new text")
        assert fuzzy is not None
        self.assertEqual(fuzzy.string, "")
        self.assertNotIn("fuzzy", fuzzy.flags)
        self.assertFalse(fuzzy.previous_id)

        plural = catalog.get(("one thing", "many things"))
        assert plural is not None
        self.assertEqual(plural.string, ("", ""))
        self.assertNotIn("fuzzy", plural.flags)
        self.assertFalse(plural.previous_id)

        kept = catalog.get("kept")
        assert kept is not None
        self.assertEqual(kept.string, "gardé")
        empty = catalog.get("empty")
        assert empty is not None
        self.assertFalse(empty.string)

    def test_no_fuzzy_is_a_no_op(self) -> None:
        catalog = build_catalog()
        clear_fuzzy(catalog)
        self.assertEqual(clear_fuzzy(catalog), 0)

    def test_file_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            po_path = os.path.join(tmp, "messages.po")
            with open(po_path, "wb") as f:
                pofile.write_po(f, build_catalog(), include_previous=True)
            with open(po_path, encoding="utf-8") as f:
                self.assertIn("#| msgid", f.read())
            self.assertEqual(clear_fuzzy_file(po_path), 2)
            with open(po_path, encoding="utf-8") as f:
                text = f.read()
            self.assertNotIn("fuzzy", text)
            # read_po keeps '#|' lines as user comments, and write_po emits '# |'.
            self.assertNotIn("# | msgid", text)
            self.assertNotIn("#|", text)
            self.assertIn("gardé", text)
            self.assertIn("# note on kept", text)

            # Nothing left to clear: the file is not rewritten.
            before = os.stat(po_path).st_mtime_ns
            self.assertEqual(clear_fuzzy_file(po_path), 0)
            self.assertEqual(os.stat(po_path).st_mtime_ns, before)


if __name__ == "__main__":
    unittest.main()
