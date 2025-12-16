#!/usr/bin/env python3

import argparse
import sys
import re
from .utils import load_catalog, find_po_files, get_lang_from_path

def find_variables(text):
    """
    Find all python format variables in the text.
    Handles %(name)s and {name} formats.
    """
    if not text:
        return set()
    # Find %(name)s style
    percent_vars = set(re.findall(r'%\(([^)]+)\)[diouxXeEfFgGcrs]', text))
    # Find {name} style
    brace_vars = set(re.findall(r'\{([^}]+)\}', text))
    return percent_vars | brace_vars

def check_file(po_path, pot_catalog):
    lang = get_lang_from_path(po_path)
    print(f"Checking {lang} ({po_path})...")

    catalog = load_catalog(po_path)

    missing = 0
    fuzzy = 0
    bad_vars = 0

    for message in catalog:
        if not message.id:
            continue

        # Check for fuzzy
        if 'fuzzy' in message.flags:
            fuzzy += 1
            print(f"  FUZZY: {message.id[:40]}...")

        # Check for missing
        if not message.string:
            # Only count as missing if it's not fuzzy (fuzzy usually means it needs review/update)
            # But technically fuzzy strings HAVE a string, just potentially wrong.
            # Empty string means untranslated.
            missing += 1
            print(f"  MISSING: {message.id[:40]}...")

        # Check variables if translated
        if message.string:
             orig_vars = find_variables(message.id)
             trans_vars = find_variables(message.string)

             # Check if all original variables are present in translation
             missing_vars = orig_vars - trans_vars
             # Check if any unknown variables are in translation
             extra_vars = trans_vars - orig_vars

             if missing_vars:
                 print(f"  ERROR: Missing variables {missing_vars} in translation of '{message.id[:40]}...' (line {message.lineno})")
                 bad_vars += 1

             if extra_vars:
                 print(f"  ERROR: Extra variables {extra_vars} in translation of '{message.id[:40]}...' (line {message.lineno})")
                 bad_vars += 1

    print(f"  Found {missing} missing, {fuzzy} fuzzy, {bad_vars} bad variable errors.")
    return missing, fuzzy, bad_vars

def main():
    parser = argparse.ArgumentParser(description="Check translation health")
    parser.add_argument("--pot_file", default="redbot/translations/messages.pot", help="Path to POT file")
    parser.add_argument("--locale_dir", default="redbot/translations", help="Path to locale directory")

    args = parser.parse_args()

    try:
        pot_catalog = load_catalog(args.pot_file)
    except FileNotFoundError:
        print(f"Error: POT file not found at {args.pot_file}")
        sys.exit(1)

    po_files = find_po_files(args.locale_dir)
    if not po_files:
        print(f"No PO files found in {args.locale_dir}")
        sys.exit(0)

    total_errors = 0

    for po_file in po_files:
        _, _, bad_vars = check_file(po_file, pot_catalog)
        total_errors += bad_vars

    if total_errors > 0:
        print(f"\nFAILED: Found {total_errors} errors.")
        sys.exit(1)

    print("\nSUCCESS: No critical errors found.")

if __name__ == "__main__":
    main()
