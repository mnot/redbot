#!/usr/bin/env python3

import argparse
import sys
import re
from typing import List, Optional, Set, Tuple, Dict
from dataclasses import dataclass
from enum import Enum, auto

from . import heuristics, rules
from .utils import load_catalog, find_po_files, get_lang_from_path, save_catalog

class IssueType(Enum):
    MISSING = auto()
    FUZZY = auto()
    BAD_VARIABLE = auto()
    SYNTAX_ERROR = auto()
    # Report-only heuristics (see heuristics.py); they never fail the build.
    LINK_MISMATCH = auto()
    TOKEN_CHANGED = auto()
    DUPLICATED_TEXT = auto()
    SUSPICIOUS_LENGTH = auto()
    PREAMBLE = auto()
    # Language rules (see rules.py and glossary.py); also used by autotranslate.
    FIELD_NAME_CHANGED = auto()
    GLOSSARY = auto()
    GLOSSARY_LOW = auto()  # low-confidence terms: reported, but not marked fuzzy
    STRENGTH = auto()
    LEFTOVER_ENGLISH = auto()
    PUNCTUATION = auto()
    BACKTICKS_ADDED = auto()
    STRUCTURE = auto()

# Reported, but they don't get an entry marked fuzzy.
NOT_MARKED = (IssueType.MISSING, IssueType.FUZZY, IssueType.GLOSSARY_LOW)

# Only these make `main()` exit non-zero.
CRITICAL_ISSUES = (IssueType.BAD_VARIABLE, IssueType.SYNTAX_ERROR)

@dataclass
class TranslationIssue:
    issue_type: IssueType
    message_id: str
    lineno: int
    details: str = ""

class CatalogChecker:
    # Regex for %(name)s style variables
    NAMED_VAR_RE = re.compile(r"%\([^)]+\)[-#0 +]*[\d\.]*[diouxXeEfFgGcrsa]")
    # Regex for positional style variables like %s, %d (including width/precision)
    POSITIONAL_VAR_RE = re.compile(r"%[-#0 +]*[\d\.]*[diouxXeEfFgGcrsa]")
    # Regex for {name} style variables
    BRACE_VAR_RE = re.compile(r"\{([^}]+)\}")

    def find_variables(self, text: str) -> Set[str]:
        """Find all python format variables in the text."""
        if not text:
            return set()
        # Replace escaped percents first to avoid false positives
        safe_text = text.replace("%%", "ESCAPE")
        named = set(self.NAMED_VAR_RE.findall(safe_text))
        positional = set(self.POSITIONAL_VAR_RE.findall(safe_text))
        brace = set(self.BRACE_VAR_RE.findall(safe_text))
        return named | positional | brace

    def validate_format_string(self, text: str) -> Tuple[bool, str]:
        """Validate that the string is a valid Python format string."""
        if not text:
            return True, ""

        # 1. Replace all escaped percents first
        temp = text.replace("%%", "SAFE")

        # 2. Replace all valid segments
        temp = self.NAMED_VAR_RE.sub("SAFE", temp)
        temp = self.POSITIONAL_VAR_RE.sub("SAFE", temp)

        # 3. Check for any remaining % signs
        if "%" in temp:
            return False, "Stray '%' found (missing '%%' or invalid format)"

        return True, ""

    def check_file(self, po_path: str) -> List[TranslationIssue]:
        """Check a single PO file for various issues."""
        return self.check_catalog(load_catalog(po_path), get_lang_from_path(po_path))

    def check_catalog(
        self, catalog, lang: Optional[str] = None
    ) -> List[TranslationIssue]:
        """Check a loaded catalog for various issues."""
        issues = []

        for message in catalog:
            if not message.id:
                continue

            # A plural message has a tuple of ids and of strings; report it by its singular.
            msgid = message.id[0] if message.pluralizable else message.id

            # 1. Check for fuzzy
            if "fuzzy" in message.flags:
                issues.append(
                    TranslationIssue(IssueType.FUZZY, msgid, message.lineno)
                )

            # 2. Check for missing
            incomplete = not message.string or (
                message.pluralizable and not all(message.string)
            )
            if incomplete:
                issues.append(
                    TranslationIssue(IssueType.MISSING, msgid, message.lineno)
                )

            if message.pluralizable:
                # the forms that are filled in are still checked
                issues.extend(self.check_plural(message))
                continue
            if incomplete:
                continue

            issues.extend(
                self.check_pair(message.id, message.string, lang, message.lineno)
            )

        return issues

    def check_plural(self, message) -> List[TranslationIssue]:
        """
        Check a plural message's variables and syntax. A form may leave out a variable
        the other form has ("one item" and "%(n)s items"), so only variables the English
        doesn't have are errors in every form; the last form, which serves the larger
        numbers (and every number, in a language with one form), must keep all of the
        English plural's. Empty forms are skipped (they are reported as MISSING). The
        heuristics are not run on plurals.
        """
        singular, plural = message.id[0], message.id[1]
        forms = list(message.string)
        issues = []
        allowed = self.find_variables(singular) | self.find_variables(plural)
        for form in forms:
            if not form:
                continue
            extra = self.find_variables(form) - allowed
            if extra:
                issues.append(
                    TranslationIssue(
                        IssueType.BAD_VARIABLE,
                        singular,
                        message.lineno,
                        f"Extra: {', '.join(sorted(extra))}",
                    )
                )
            valid, error_msg = self.validate_format_string(form)
            if not valid:
                issues.append(
                    TranslationIssue(
                        IssueType.SYNTAX_ERROR, singular, message.lineno, error_msg
                    )
                )
        missing = self.find_variables(plural) - self.find_variables(forms[-1])
        if forms[-1] and missing:
            issues.append(
                TranslationIssue(
                    IssueType.BAD_VARIABLE,
                    singular,
                    message.lineno,
                    f"Missing: {', '.join(sorted(missing))}",
                )
            )
        return issues

    def check_pair(
        self, msgid: str, msgstr: str, lang: Optional[str] = None, lineno: int = 0
    ) -> List[TranslationIssue]:
        """Check one translated (msgid, msgstr) pair: variables, syntax, heuristics."""
        issues = []

        # 3. Check variables
        orig_vars = self.find_variables(msgid)
        trans_vars = self.find_variables(msgstr)

        missing_vars = orig_vars - trans_vars
        extra_vars = trans_vars - orig_vars

        if missing_vars:
            issues.append(
                TranslationIssue(
                    IssueType.BAD_VARIABLE,
                    msgid,
                    lineno,
                    f"Missing: {', '.join(sorted(missing_vars))}",
                )
            )

        if extra_vars:
            issues.append(
                TranslationIssue(
                    IssueType.BAD_VARIABLE,
                    msgid,
                    lineno,
                    f"Extra: {', '.join(sorted(extra_vars))}",
                )
            )

        # 4. Check syntax (stray %)
        valid, error_msg = self.validate_format_string(msgstr)
        if not valid:
            issues.append(
                TranslationIssue(IssueType.SYNTAX_ERROR, msgid, lineno, error_msg)
            )

        issues.extend(self.check_heuristics(msgid, msgstr, lang, lineno))
        return issues

    def check_heuristics(
        self, msgid, msgstr, lang: Optional[str], lineno: int = 0
    ) -> List[TranslationIssue]:
        """Run the report-only heuristics on one translated message."""
        if not isinstance(msgid, str) or not isinstance(msgstr, str):
            return []  # plural forms are not handled anywhere in this tool yet
        found = [
            (IssueType.LINK_MISMATCH, heuristics.link_mismatch(msgid, msgstr)),
            (IssueType.TOKEN_CHANGED, heuristics.token_changed(msgid, msgstr)),
            (IssueType.DUPLICATED_TEXT, heuristics.duplicated_text(msgid, msgstr)),
            (
                IssueType.SUSPICIOUS_LENGTH,
                heuristics.suspicious_length(msgid, msgstr, lang),
            ),
            (IssueType.PREAMBLE, heuristics.preamble(msgid, msgstr)),
            (IssueType.FIELD_NAME_CHANGED, rules.field_name_changed(msgid, msgstr)),
            (IssueType.GLOSSARY, rules.glossary(msgid, msgstr, lang)),
            (IssueType.GLOSSARY_LOW, rules.glossary_low(msgid, msgstr, lang)),
            (IssueType.STRENGTH, rules.strength(msgid, msgstr, lang)),
            (IssueType.LEFTOVER_ENGLISH, rules.leftover_english(msgid, msgstr, lang)),
            (IssueType.PUNCTUATION, rules.punctuation(msgid, msgstr, lang)),
            (IssueType.BACKTICKS_ADDED, rules.backticks_added(msgid, msgstr)),
            (IssueType.STRUCTURE, rules.structure(msgid, msgstr, lang)),
        ]
        return [
            TranslationIssue(issue_type, msgid, lineno, details)
            for issue_type, details in found
            if details
        ]

def mark_fuzzy(catalog, issues: List[TranslationIssue]) -> int:
    """
    Set the fuzzy flag on translated entries that have any issue other than MISSING,
    FUZZY or GLOSSARY_LOW, so 'make i18n-clear-fuzzy' can blank them. Returns the number
    marked.
    """
    flagged = {
        i.message_id
        for i in issues
        if i.issue_type not in NOT_MARKED
    }
    count = 0
    for message in catalog:
        if message.id in flagged and message.string and "fuzzy" not in message.flags:
            message.flags.add("fuzzy")
            count += 1
    return count

class Reporter:
    """Handles formatted output for translation issues."""

    def report_file(self, lang: str, po_path: str, issues: List[TranslationIssue]):
        print(f"Checking {lang} ({po_path})...")
        if not issues:
            print("  SUCCESS: No issues found.")
            return

        counts: Dict[IssueType, int] = {}
        for issue in issues:
            counts[issue.issue_type] = counts.get(issue.issue_type, 0) + 1
            label = issue.issue_type.name
            preview = issue.message_id[:40].replace("\n", " ")
            detail = f" - {issue.details}" if issue.details else ""
            print(f"  {label:<18} {preview}... (line {issue.lineno}){detail}")

        summary_parts = []
        for it in IssueType:
            if counts.get(it, 0) > 0:
                summary_parts.append(f"{counts[it]} {it.name.lower()}")
        print(f"  Found {', '.join(summary_parts)} issues.")

def main():
    parser = argparse.ArgumentParser(description="Check translation health")
    parser.add_argument(
        "--pot_file",
        default="redbot/translations/messages.pot",
        help="Path to POT file",
    )
    parser.add_argument(
        "--locale_dir", default="redbot/translations", help="Path to locale directory"
    )

    parser.add_argument(
        "--mark-fuzzy",
        action="store_true",
        help="Set the fuzzy flag on entries with issues, and save the catalogs",
    )

    args = parser.parse_args()

    checker = CatalogChecker()
    reporter = Reporter()

    po_files = find_po_files(args.locale_dir)
    if not po_files:
        print(f"No PO files found in {args.locale_dir}")
        sys.exit(0)

    total_critical_errors = 0

    for po_file in po_files:
        lang = get_lang_from_path(po_file)
        catalog = load_catalog(po_file)
        issues = checker.check_catalog(catalog, lang)
        if args.mark_fuzzy:
            marked = mark_fuzzy(catalog, issues)
            if marked:
                save_catalog(po_file, catalog)
            noun = "entry" if marked == 1 else "entries"
            print(f"{lang}: marked {marked} {noun} fuzzy")
        reporter.report_file(lang, po_file, issues)

        # Missing, fuzzy and the heuristic reports are advisory; the original script
        # only exited 1 for bad variables/syntax.
        critical = [i for i in issues if i.issue_type in CRITICAL_ISSUES]
        total_critical_errors += len(critical)

    if total_critical_errors > 0:
        print(f"\nFAILED: Found {total_critical_errors} critical errors.")
        sys.exit(1)

    print("\nSUCCESS: No critical errors found.")

if __name__ == "__main__":
    main()
