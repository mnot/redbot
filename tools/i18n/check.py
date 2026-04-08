#!/usr/bin/env python3

import argparse
import sys
import re
from typing import List, Set, Tuple, Dict
from dataclasses import dataclass
from enum import Enum, auto

from .utils import load_catalog, find_po_files, get_lang_from_path

class IssueType(Enum):
    MISSING = auto()
    FUZZY = auto()
    BAD_VARIABLE = auto()
    SYNTAX_ERROR = auto()

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
        catalog = load_catalog(po_path)
        issues = []

        for message in catalog:
            if not message.id:
                continue

            # 1. Check for fuzzy
            if "fuzzy" in message.flags:
                issues.append(
                    TranslationIssue(IssueType.FUZZY, message.id, message.lineno)
                )

            # 2. Check for missing
            if not message.string:
                issues.append(
                    TranslationIssue(IssueType.MISSING, message.id, message.lineno)
                )
                continue

            # 3. Check variables
            orig_vars = self.find_variables(message.id)
            trans_vars = self.find_variables(message.string)

            missing_vars = orig_vars - trans_vars
            extra_vars = trans_vars - orig_vars

            if missing_vars:
                issues.append(
                    TranslationIssue(
                        IssueType.BAD_VARIABLE,
                        message.id,
                        message.lineno,
                        f"Missing: {', '.join(sorted(missing_vars))}",
                    )
                )

            if extra_vars:
                issues.append(
                    TranslationIssue(
                        IssueType.BAD_VARIABLE,
                        message.id,
                        message.lineno,
                        f"Extra: {', '.join(sorted(extra_vars))}",
                    )
                )

            # 4. Check syntax (stray %)
            valid, error_msg = self.validate_format_string(message.string)
            if not valid:
                issues.append(
                    TranslationIssue(
                        IssueType.SYNTAX_ERROR, message.id, message.lineno, error_msg
                    )
                )

        return issues

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
            print(f"  {label:<12} {preview}... (line {issue.lineno}){detail}")

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
        issues = checker.check_file(po_file)
        reporter.report_file(lang, po_file, issues)

        # Count critical errors (anything that's not just fuzzy or missing)
        # Actually, missing might be critical too depending on requirements,
        # but the original script only exited 1 for bad variables/syntax.
        critical = [
            i
            for i in issues
            if i.issue_type in [IssueType.BAD_VARIABLE, IssueType.SYNTAX_ERROR]
        ]
        total_critical_errors += len(critical)

    if total_critical_errors > 0:
        print(f"\nFAILED: Found {total_critical_errors} critical errors.")
        sys.exit(1)

    print("\nSUCCESS: No critical errors found.")

if __name__ == "__main__":
    main()
