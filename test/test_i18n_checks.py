"""Tests for the report-only heuristics in tools/i18n/check.py."""

import contextlib
import io
import os
import tempfile
import unittest
from unittest import mock

from babel.messages.catalog import Catalog

from tools.i18n import heuristics
from tools.i18n import check
from tools.i18n.check import CRITICAL_ISSUES, CatalogChecker, IssueType
from tools.i18n.utils import load_catalog, save_catalog


class LinkMismatchTest(unittest.TestCase):
    def test_same_links(self) -> None:
        msgid = "See [RFC 9110](https://example.com/rfc9110) and https://example.org/x."
        msgstr = "Voir [RFC 9110](https://example.com/rfc9110) et https://example.org/x."
        self.assertIsNone(heuristics.link_mismatch(msgid, msgstr))

    def test_dropped_link(self) -> None:
        msgid = "A [Structured Field](https://example.com/sf) is bad."
        msgstr = "Un champ structuré est mauvais."
        self.assertIn("https://example.com/sf", heuristics.link_mismatch(msgid, msgstr) or "")

    def test_changed_link(self) -> None:
        msgid = "See [x](https://example.com/a)."
        msgstr = "Voir [x](https://example.com/b)."
        details = heuristics.link_mismatch(msgid, msgstr)
        self.assertIn("missing", details or "")
        self.assertIn("extra", details or "")

    def test_placeholder_target(self) -> None:
        msgid = "See [its definition](%(ref_uri)s) for more."
        self.assertIsNone(heuristics.link_mismatch(msgid, "Voir [sa définition](%(ref_uri)s)."))

    def test_broken_markdown_placeholder_target(self) -> None:
        msgid = "See [its definition](%(ref_uri)s) for more."
        msgstr = "詳細は[定義] (%(ref_uri)s) を参照。"
        self.assertIn("%(ref_uri)s", heuristics.link_mismatch(msgid, msgstr) or "")

    def test_trailing_punctuation_ignored(self) -> None:
        self.assertIsNone(
            heuristics.link_mismatch("See https://example.com/a.", "Voir https://example.com/a,")
        )

    MSGID = "See [RFC 9111](https://example.com/rfc9111) for details."

    def test_space_before_parenthesis(self) -> None:
        # the target is still a real URL, so the set of targets alone looks fine
        details = heuristics.link_mismatch(
            self.MSGID, "Voir [RFC 9111] (https://example.com/rfc9111) pour plus."
        )
        self.assertIn("space between", details or "")

    def test_unclosed_link(self) -> None:
        details = heuristics.link_mismatch(
            self.MSGID, "Voir [RFC 9111](https://example.com/rfc9111 pour plus."
        )
        self.assertIn("0 well-formed", details or "")

    def test_lost_brackets(self) -> None:
        details = heuristics.link_mismatch(
            self.MSGID, "Voir RFC 9111 (https://example.com/rfc9111) pour plus."
        )
        self.assertIn("0 well-formed", details or "")

    def test_lost_closing_bracket(self) -> None:
        details = heuristics.link_mismatch(
            self.MSGID, "Voir [RFC 9111(https://example.com/rfc9111) pour plus."
        )
        self.assertIsNotNone(details)

    def test_extra_target_alone_is_flagged(self) -> None:
        details = heuristics.link_mismatch(
            self.MSGID,
            "Voir [RFC 9111](https://example.com/rfc9111) et https://example.com/other.",
        )
        self.assertIn("extra: https://example.com/other", details or "")
        self.assertNotIn("missing", details or "")

    def test_extra_link_alone_is_flagged(self) -> None:
        details = heuristics.link_mismatch(
            self.MSGID,
            "Voir [RFC 9111](https://example.com/rfc9111) et [autre](https://example.com/rfc9111).",
        )
        self.assertIn("2 well-formed", details or "")

    def test_well_formed_link_text_may_wrap_lines(self) -> None:
        msgid = "See [Cross-Origin\nOpener Policy](https://example.com/coop),\nplease."
        msgstr = "Voir [Politique d'ouverture\nCross-Origin](https://example.com/coop)."
        self.assertIsNone(heuristics.link_mismatch(msgid, msgstr))

    def test_space_already_in_msgid_is_not_blamed_on_translation(self) -> None:
        msgid = "A `[x] (y)` example and [link](https://example.com/a)."
        msgstr = "Un exemple `[x] (y)` et [lien](https://example.com/a)."
        self.assertIsNone(heuristics.link_mismatch(msgid, msgstr))


class TokenChangedTest(unittest.TestCase):
    def test_token_kept(self) -> None:
        self.assertIsNone(
            heuristics.token_changed(
                "The `Cache-Control` header has `max-age=0`.",
                "L'en-tête Cache-Control a max-age=0.",
            )
        )

    def test_header_name_translated(self) -> None:
        details = heuristics.token_changed(
            "The `Access-Control-Max-Age` header is bad.",
            "Access-控制-Max-Age 头不正确。",
        )
        self.assertIn("Access-Control-Max-Age", details or "")

    def test_value_translated(self) -> None:
        details = heuristics.token_changed(
            "It should almost always be `bytes`.", "Il devrait être `octets`."
        )
        self.assertIn("bytes", details or "")

    def test_case_matters(self) -> None:
        self.assertIsNotNone(
            heuristics.token_changed("Use `Content-Type`.", "Utilisez content-type.")
        )

    def test_field_line(self) -> None:
        self.assertIsNone(
            heuristics.token_changed(
                "Send `Cache-Control: no-store`.", "Envoyez `Cache-Control: no-store`."
            )
        )
        self.assertIsNotNone(
            heuristics.token_changed(
                "Send `Cache-Control: no-store`.", "Envoyez `Contrôle-Cache: no-store`."
            )
        )

    def test_status_code_only_needs_code(self) -> None:
        self.assertIsNone(
            heuristics.token_changed(
                "The `404 (Not Found)` status.", "Le statut `404 (Introuvable)`."
            )
        )
        self.assertIsNotNone(
            heuristics.token_changed("The `404 (Not Found)` status.", "Le statut introuvable.")
        )

    def test_ignored_spans(self) -> None:
        # placeholders (BAD_VARIABLE's job), bare punctuation, prose from unpaired backticks
        self.assertIsNone(
            heuristics.token_changed(
                "The `%(name)s` key, `*`, and `a b c d e f g` appear.", "La clé."
            )
        )


class DuplicatedTextTest(unittest.TestCase):
    def test_repeated_placeholder(self) -> None:
        msgid = "The `%(key)s` key has an invalid value; %(details)s."
        msgstr = "La clé `%(key)s` a une valeur non valide ; %(details)s.\nDétails : %(details)s"
        self.assertIn("%(details)s", heuristics.duplicated_text(msgid, msgstr) or "")

    def test_repeated_sentence(self) -> None:
        msgid = "The header is invalid. It must be a number."
        msgstr = (
            "L'en-tête est invalide. Il doit être un nombre. "
            "L'en-tête est invalide. Il doit être un nombre."
        )
        self.assertIn("repeated sentence", heuristics.duplicated_text(msgid, msgstr) or "")

    def test_repeated_paragraph(self) -> None:
        msgid = "First line here.\n\nSecond line here."
        msgstr = "Première ligne ici.\n\nDeuxième ligne ici.\n\nPremière ligne ici."
        self.assertIsNotNone(heuristics.duplicated_text(msgid, msgstr))

    def test_cjk_repeat(self) -> None:
        msgid = "The header is invalid."
        msgstr = "ヘッダーは無効です。ヘッダーは無効です。"
        self.assertIsNotNone(heuristics.duplicated_text(msgid, msgstr))

    def test_repeat_also_in_msgid_is_fine(self) -> None:
        msgid = "The value is wrong. The value is wrong."
        msgstr = "La valeur est fausse. La valeur est fausse."
        self.assertIsNone(heuristics.duplicated_text(msgid, msgstr))

    def test_placeholder_repeated_in_msgid_is_fine(self) -> None:
        msgid = "%(method)s here, and %(method)s there."
        msgstr = "%(method)s ici, et %(method)s là."
        self.assertIsNone(heuristics.duplicated_text(msgid, msgstr))

    def test_short_repeats_ignored(self) -> None:
        self.assertIsNone(heuristics.duplicated_text("Yes. No.", "Oui. Oui."))

    def test_second_repeated_sentence_is_flagged_even_if_msgid_repeats_one(self) -> None:
        msgid = "Check the value twice. Check the value twice. Then continue."
        msgstr = (
            "Vérifiez la valeur deux fois. Vérifiez la valeur deux fois. "
            "Ensuite continuez ici. Ensuite continuez ici."
        )
        self.assertIn("repeated sentence", heuristics.duplicated_text(msgid, msgstr) or "")

    def test_same_repeats_as_msgid_are_fine(self) -> None:
        msgid = "Check the value twice. Check the value twice. Then continue."
        msgstr = "Vérifiez la valeur deux fois. Vérifiez la valeur deux fois. Continuez."
        self.assertIsNone(heuristics.duplicated_text(msgid, msgstr))


class SuspiciousLengthTest(unittest.TestCase):
    MSGID = "The response is missing a Content-Type header field."  # 52 characters

    def test_normal(self) -> None:
        self.assertIsNone(heuristics.suspicious_length(self.MSGID, "A" * 60, "fr"))

    def test_too_short_latin(self) -> None:
        self.assertIsNotNone(heuristics.suspicious_length(self.MSGID, "La requête a expiré.", "fr"))

    def test_too_long_latin(self) -> None:
        self.assertIsNotNone(heuristics.suspicious_length(self.MSGID, "x" * 200, "es"))

    def test_cjk_is_shorter(self) -> None:
        msgstr = "Content-Type ヘッダーがありません。"  # ratio 0.46
        self.assertIsNone(heuristics.suspicious_length(self.MSGID, msgstr, "ja"))
        self.assertIsNotNone(heuristics.suspicious_length(self.MSGID, msgstr, "fr"))

    def test_cjk_too_short(self) -> None:
        self.assertIsNotNone(heuristics.suspicious_length(self.MSGID, "無効です。", "ja"))

    def test_region_suffix(self) -> None:
        msgstr = "响应缺少 Content-Type 头。"
        self.assertIsNone(heuristics.suspicious_length(self.MSGID, msgstr, "zh_Hans"))

    def test_short_msgid_skipped(self) -> None:
        self.assertIsNone(heuristics.suspicious_length("Bad value.", "x" * 100, "fr"))

    def test_zh_lower_bound(self) -> None:
        # 52 characters in: 6 or 4 out is below the 0.12 bound (0.115, 0.077), 8 is above
        self.assertIsNotNone(heuristics.suspicious_length(self.MSGID, "无效头字段。", "zh"))
        self.assertIsNotNone(heuristics.suspicious_length(self.MSGID, "无效头。", "zh"))
        self.assertIsNone(heuristics.suspicious_length(self.MSGID, "缺少头字段信息。", "zh"))


class PreambleTest(unittest.TestCase):
    def test_chatter(self) -> None:
        for msgstr in (
            "Here is the translation: L'en-tête est invalide.",
            "Sure! L'en-tête est invalide.",
            "Translation: L'en-tête est invalide.",
            "Voici la traduction : L'en-tête est invalide.",
            "Aquí está la traducción: El encabezado no es válido.",
            "以下是翻译：标头无效。",
            "翻訳: ヘッダーは無効です。",
            "```\nL'en-tête est invalide.\n```",
        ):
            with self.subTest(msgstr=msgstr):
                self.assertIsNotNone(heuristics.preamble("The header is invalid.", msgstr))

    def test_think_tags(self) -> None:
        self.assertIsNotNone(
            heuristics.preamble("The header is invalid.", "<think>hmm</think>L'en-tête.")
        )

    def test_normal(self) -> None:
        self.assertIsNone(heuristics.preamble("The header is invalid.", "L'en-tête est invalide."))

    def test_msgid_with_same_start_is_fine(self) -> None:
        self.assertIsNone(
            heuristics.preamble("Here is how it works.", "Here is how it works, in French.")
        )

    def test_more_chatter(self) -> None:
        for msgstr in (
            "Certainly! L'en-tête est invalide.",
            "Certainement ! L'en-tête est invalide.",
            "Sure, here you go. L'en-tête est invalide.",
            "As an AI language model, I cannot translate this.",
            "I'm sorry, but I can't help with that.",
            "Je suis désolé, mais je ne peux pas traduire cela.",
            "Lo siento, no puedo traducir esto.",
            "申し訳ありませんが、翻訳できません。",
            "抱歉，我无法翻译这个。",
            "L'en-tête est invalide.\n\n(Note: j'ai conservé les noms d'en-têtes.)",
            "L'en-tête est invalide.\nLet me know if you need anything else!",
            "El encabezado no es válido.\nEspero que esto te ayude.",
        ):
            with self.subTest(msgstr=msgstr):
                self.assertIsNotNone(heuristics.preamble("The header is invalid.", msgstr))

    def test_note_in_msgid_is_not_chatter(self) -> None:
        self.assertIsNone(
            heuristics.preamble(
                "The header is invalid.\nNote: this is common.",
                "L'en-tête est invalide.\nRemarque : c'est courant.",
            )
        )


class CatalogReportingTest(unittest.TestCase):
    """The new checks report issues but never fail the build."""

    @staticmethod
    def catalog() -> Catalog:
        catalog = Catalog(locale="fr")
        catalog.add(
            "The `Sunset` header indicates that this resource is gone, which is bad.",
            "La requête a expiré.",
            locations=[("x.py", 1)],
        )
        catalog.add("Fine string.", "Chaîne correcte.")
        return catalog

    def test_flags_reported(self) -> None:
        issues = CatalogChecker().check_catalog(self.catalog(), "fr")
        kinds = {i.issue_type for i in issues}
        self.assertEqual(
            kinds,
            {IssueType.TOKEN_CHANGED, IssueType.SUSPICIOUS_LENGTH, IssueType.FIELD_NAME_CHANGED},
        )

    def test_not_critical(self) -> None:
        for issue_type in (
            IssueType.LINK_MISMATCH,
            IssueType.TOKEN_CHANGED,
            IssueType.DUPLICATED_TEXT,
            IssueType.SUSPICIOUS_LENGTH,
            IssueType.PREAMBLE,
        ):
            self.assertNotIn(issue_type, CRITICAL_ISSUES)
        self.assertEqual(set(CRITICAL_ISSUES), {IssueType.BAD_VARIABLE, IssueType.SYNTAX_ERROR})

    def test_empty_skipped(self) -> None:
        catalog = Catalog(locale="fr")
        catalog.add("The `Sunset` header indicates that it is all bad, really.", "")
        self.assertEqual(
            [i.issue_type for i in CatalogChecker().check_catalog(catalog, "fr")],
            [IssueType.MISSING],
        )


class PoFixture(unittest.TestCase):
    """A temporary fr catalog with flagged, bad-variable, clean, missing and fuzzy entries."""

    FLAGGED = "The `Sunset` header indicates that this resource is gone, which is bad."
    BAD_VAR = "Found %(count)s items."
    FUZZY = "Already fuzzy string, with `Cache-Control` in it for good measure."

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.locale_dir = tmp.name
        self.po_path = os.path.join(tmp.name, "fr", "LC_MESSAGES", "messages.po")
        os.makedirs(os.path.dirname(self.po_path))
        catalog = Catalog(locale="fr")
        catalog.add(self.FLAGGED, "La requête a expiré.", locations=[("x.py", 1)])
        catalog.add(self.BAD_VAR, "Trouvé des éléments.", locations=[("x.py", 2)])
        catalog.add("Fine string.", "Chaîne correcte.", locations=[("x.py", 3)])
        catalog.add("Missing string, `Sunset` is here too.", "", locations=[("x.py", 4)])
        catalog.add(self.FUZZY, "La requête a expiré.", flags=["fuzzy"], locations=[("x.py", 5)])
        save_catalog(self.po_path, catalog)

    def run_check(self, *args: str) -> "tuple[int, str]":
        out = io.StringIO()
        argv = ["check.py", "--locale_dir", self.locale_dir, *args]
        code = 0
        with mock.patch("sys.argv", argv), contextlib.redirect_stdout(out):
            try:
                check.main()
            except SystemExit as exc:
                code = int(exc.code or 0)
        return code, out.getvalue()

    def flags(self) -> "dict[str, set[str]]":
        return {str(m.id): set(m.flags) for m in load_catalog(self.po_path) if m.id}

    def read_bytes(self) -> bytes:
        with open(self.po_path, "rb") as handle:
            return handle.read()


class PluralTest(unittest.TestCase):
    """Plural messages have a tuple of ids and strings (mnot/redbot#555)."""

    IDS = (" - %d problem\n", " - %d problems\n")

    def issues(self, strings, locale="fr"):
        catalog = Catalog(locale=locale)
        catalog.add(self.IDS, strings)
        return CatalogChecker().check_catalog(catalog, locale)

    def kinds(self, strings, locale="fr"):
        return sorted(
            (i.issue_type.name, i.details) for i in self.issues(strings, locale)
        )

    def test_good_plural_has_no_issues(self) -> None:
        self.assertEqual(self.kinds(("- %d problème", "- %d problèmes")), [])
        self.assertEqual(self.kinds(("%d problème",), "ja"), [])

    def test_extra_variable_in_any_form(self) -> None:
        self.assertEqual(
            self.kinds(("- %(n)s problème", "- %d problèmes")),
            [("BAD_VARIABLE", "Extra: %(n)s")],
        )

    def test_missing_variable_in_the_last_form(self) -> None:
        self.assertEqual(
            self.kinds(("- %d problème", "- des problèmes")),
            [("BAD_VARIABLE", "Missing: %d")],
        )
        self.assertEqual(self.kinds(("des problèmes",), "ja"), [("BAD_VARIABLE", "Missing: %d")])

    def test_a_form_may_leave_out_the_number(self) -> None:
        self.assertEqual(self.kinds(("un problème", "- %d problèmes")), [])

    def test_stray_percent(self) -> None:
        names = [name for name, _ in self.kinds(("- 5% problème", "- %d problèmes"))]
        self.assertEqual(names, ["SYNTAX_ERROR"])

    def test_empty_form_is_missing(self) -> None:
        self.assertEqual([i.issue_type for i in self.issues(("- %d problème", ""))], [IssueType.MISSING])
        self.assertEqual([i.issue_type for i in self.issues(("", ""))], [IssueType.MISSING])

    def test_filled_forms_are_still_checked_beside_an_empty_one(self) -> None:
        issues = self.issues(("- %(n)s problème", ""))
        self.assertEqual(
            sorted((i.issue_type.name, i.details) for i in issues),
            [("BAD_VARIABLE", "Extra: %(n)s"), ("MISSING", "")],
        )

    def test_reported_by_the_singular(self) -> None:
        issues = self.issues(("- %d problème", "- des problèmes"))
        self.assertEqual({i.message_id for i in issues}, {self.IDS[0]})

    def test_never_marked_fuzzy(self) -> None:
        catalog = Catalog(locale="fr")
        catalog.add(self.IDS, ("- %d problème", "- des problèmes"))
        issues = CatalogChecker().check_catalog(catalog, "fr")
        self.assertEqual(check.mark_fuzzy(catalog, issues), 0)


class MarkFuzzyTest(PoFixture):
    """--mark-fuzzy flags entries with issues; it never touches the others."""

    def test_marks_only_flagged(self) -> None:
        _, out = self.run_check("--mark-fuzzy")
        flags = self.flags()
        self.assertIn("fuzzy", flags[self.FLAGGED])
        self.assertIn("fuzzy", flags[self.BAD_VAR])
        self.assertNotIn("fuzzy", flags["Fine string."])
        self.assertNotIn("fuzzy", flags["Missing string, `Sunset` is here too."])
        self.assertIn("fr: marked 2 entries fuzzy", out)
        self.assertIn("TOKEN_CHANGED", out)

    def test_low_confidence_glossary_is_reported_but_not_marked(self) -> None:
        catalog = Catalog(locale="ja")
        catalog.add("The response is fine.", "レスポンスは問題ありません。")
        catalog.add("A response is sent.", "応答が送信されます。")  # only a LOW entry
        catalog.add("A directive is sent.", "指示が送信されます。")  # a regular entry
        issues = CatalogChecker().check_catalog(catalog, "ja")
        self.assertEqual(sorted(i.issue_type.name for i in issues), ["GLOSSARY", "GLOSSARY_LOW"])
        self.assertEqual(check.mark_fuzzy(catalog, issues), 1)
        self.assertNotIn("fuzzy", catalog.get("A response is sent.").flags)
        self.assertIn("fuzzy", catalog.get("A directive is sent.").flags)

    def test_added_backticks_are_marked_and_not_critical(self) -> None:
        catalog = load_catalog(self.po_path)
        for message in list(catalog):
            if message.id in (self.FLAGGED, self.BAD_VAR):
                del catalog[message.id]
        catalog.add("Vary is bad, and long enough.", "`Vary` est mauvais.")
        save_catalog(self.po_path, catalog)
        code, out = self.run_check("--mark-fuzzy")
        self.assertEqual(code, 0)  # report-only: the exit code is unchanged
        self.assertIn("BACKTICKS_ADDED", out)
        self.assertIn("fuzzy", self.flags()["Vary is bad, and long enough."])
        self.assertNotIn("fuzzy", self.flags()["Fine string."])

    def test_translations_not_changed(self) -> None:
        before = {str(m.id): m.string for m in load_catalog(self.po_path) if m.id}
        self.run_check("--mark-fuzzy")
        after = {str(m.id): m.string for m in load_catalog(self.po_path) if m.id}
        self.assertEqual(before, after)

    def test_already_fuzzy_untouched(self) -> None:
        self.run_check("--mark-fuzzy")
        self.assertIn("fuzzy", self.flags()[self.FUZZY])
        _, out = self.run_check("--mark-fuzzy")
        self.assertIn("fr: marked 0 entries fuzzy", out)

    def test_idempotent(self) -> None:
        self.run_check("--mark-fuzzy")
        saved = self.read_bytes()
        _, out = self.run_check("--mark-fuzzy")
        self.assertIn("marked 0 entries", out)
        self.assertEqual(self.read_bytes(), saved)

    def test_file_not_rewritten_when_nothing_marked(self) -> None:
        catalog = load_catalog(self.po_path)
        for message in list(catalog):
            if message.id in (self.FLAGGED, self.BAD_VAR):
                del catalog[message.id]
        save_catalog(self.po_path, catalog)
        with mock.patch.object(check, "save_catalog") as save:
            _, out = self.run_check("--mark-fuzzy")
        save.assert_not_called()
        self.assertIn("marked 0 entries", out)

    def test_default_does_not_modify(self) -> None:
        before = self.read_bytes()
        _, out = self.run_check()
        self.assertEqual(self.read_bytes(), before)
        self.assertNotIn("marked", out)

    def test_exit_code_unchanged(self) -> None:
        # BAD_VARIABLE is critical, so the exit status is 1 with or without the option.
        plain, _ = self.run_check()
        marking, _ = self.run_check("--mark-fuzzy")
        self.assertEqual((plain, marking), (1, 1))

    def test_exit_code_zero_without_critical(self) -> None:
        catalog = load_catalog(self.po_path)
        del catalog[self.BAD_VAR]
        save_catalog(self.po_path, catalog)
        code, out = self.run_check("--mark-fuzzy")
        self.assertEqual(code, 0)
        self.assertIn("marked 1 entry fuzzy", out)


if __name__ == "__main__":
    unittest.main()
