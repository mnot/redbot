#!/usr/bin/env python3

import argparse
import sys

from babel.messages import Catalog

from .utils import find_po_files, get_lang_from_path, load_catalog, save_catalog


def clear_fuzzy(catalog: Catalog) -> int:
    """
    Reset every fuzzy entry in the catalog to an empty, untranslated one.

    Blanks the translation (every plural form, if there are several) and drops the
    'fuzzy' flag and the previous msgid. This discards the translation text.
    Returns the number of entries cleared.
    """
    count = 0
    for message in catalog:
        if not message.id or "fuzzy" not in message.flags:
            continue
        if isinstance(message.string, (tuple, list)):
            message.string = tuple("" for _ in message.string)
        else:
            message.string = ""
        message.flags.discard("fuzzy")
        message.previous_id = ()
        message.previous_context = None
        # read_po does not parse '#|' previous-msgid lines; it keeps them as
        # user comments that start with '|'.
        message.user_comments = [
            c for c in message.user_comments if not c.startswith("|")
        ]
        count += 1
    return count


def clear_fuzzy_file(po_path: str) -> int:
    """Clear fuzzy entries in one PO file, saving it only if something changed."""
    catalog = load_catalog(po_path)
    count = clear_fuzzy(catalog)
    if count:
        save_catalog(po_path, catalog)
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Blank fuzzy translations, discarding their text"
    )
    parser.add_argument(
        "--locale_dir", default="redbot/translations", help="Path to locale directory"
    )

    args = parser.parse_args()

    po_files = find_po_files(args.locale_dir)
    if not po_files:
        print(f"No PO files found in {args.locale_dir}")
        sys.exit(0)

    for po_file in po_files:
        lang = get_lang_from_path(po_file)
        count = clear_fuzzy_file(po_file)
        noun = "entry" if count == 1 else "entries"
        print(f"{lang}: cleared {count} fuzzy {noun}")


if __name__ == "__main__":
    main()
