"""Tests for the language rules in tools/i18n/rules.py and glossary.py. No model is called."""

import os
import unittest
from typing import List, Optional

from babel.messages.pofile import read_po

from tools.i18n import glossary as glossary_data, rules
from tools.i18n.autotranslate import (
    HARD_PREFIXES,
    PROMPT_END,
    PROTECT_LINKS,
    build_prompt,
    match_whitespace,
    translate,
)
from tools.i18n.check import CRITICAL_ISSUES, CatalogChecker, IssueType

POT = os.path.join(os.path.dirname(__file__), "..", "redbot", "translations", "messages.pot")
TEXT_MARK = "Here is the text to translate:\n\n"


def text_of(prompt: str) -> str:
    return prompt.split(TEXT_MARK, 1)[1]


def replies(*texts: str):
    """A fake model that answers with each text in turn, recording the prompts."""
    prompts: List[str] = []
    answers = iter(texts)

    def ask(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    return ask, prompts


class FieldNameTest(unittest.TestCase):
    def test_names_in(self) -> None:
        msgid = "The Content-Length header and cache-control header; see `Vary` and %(Date)s."
        self.assertEqual(rules.names_in(msgid), ["Content-Length", "cache-control"])

    def test_hyphenated_names_need_no_label(self) -> None:
        self.assertEqual(
            rules.names_in("Access-Control-Max-Age is wrong."), ["Access-Control-Max-Age"]
        )

    def test_longest_name_wins_and_prefixes_do_not_match(self) -> None:
        self.assertEqual(
            rules.names_in("Content-Security-Policy-Report-Only is odd."),
            ["Content-Security-Policy-Report-Only"],
        )
        self.assertEqual(rules.names_in("The Access-Control-Foo thing."), [])

    def test_single_words_need_a_label(self) -> None:
        self.assertEqual(
            rules.names_in("The Date header is wrong; Link headers too."), ["Date", "Link"]
        )
        self.assertEqual(rules.names_in("Add a link to the date of the age range."), [])
        self.assertEqual(rules.names_in("Date is required. Link to Age."), [])
        self.assertEqual(rules.names_in("The Referer field is odd."), ["Referer"])

    def test_names_in_urls_links_and_placeholders_are_skipped(self) -> None:
        msgid = "See [x](https://example.com/Content-Type) and https://e.org/Cache-Control %(Vary header)s."
        self.assertEqual(rules.names_in(msgid), [])

    def test_lowercase_spelling_is_a_name_only_as_a_header(self) -> None:
        self.assertEqual(rules.names_in("The report-to parameter is bad."), [])
        self.assertEqual(rules.names_in("The report-to header is bad."), ["report-to"])

    def test_every_coding_name_is_protected(self) -> None:
        self.assertEqual(
            set(rules.CODING_NAMES), {"gzip", "deflate", "brotli", "zstd", "dcb", "dcz"}
        )
        for name in rules.CODING_NAMES:
            with self.subTest(name=name):
                self.assertEqual(rules.names_in(f"Use {name} here."), [name])
                self.assertIsNotNone(rules.field_name_changed(f"Use {name} here.", "ここ。"))
                self.assertIsNone(rules.field_name_changed(f"Use {name} here.", f"{name} を使う。"))

    def test_coding_names(self) -> None:
        self.assertEqual(
            rules.names_in("Compressed using Deflate or gzip; GZip-compressed."),
            ["Deflate", "gzip", "GZip"],
        )
        self.assertEqual(rules.names_in("We compress the identity."), [])

    def test_transliterated_names_are_flagged(self) -> None:
        cases = [
            (
                "The Access-Control-Max-Age header is bad.",
                "アクセス・コントロール・マックス・エイジヘッダーが不正です。",
            ),
            ("The Referrer-Policy value is unknown.", "リファラーポリシーの値は未知です。"),
            (
                "The Content-Range header is bad.",
                "Content-Range 头不正确。".replace("Content-Range", "内容范围"),
            ),
            ("Compressed with Brotli.", "ブロトリで圧縮されています。"),
        ]
        for msgid, msgstr in cases:
            with self.subTest(msgid=msgid):
                self.assertIn("exactly as written", rules.field_name_changed(msgid, msgstr) or "")

    def test_kept_names_pass(self) -> None:
        cases = [
            (
                "The Access-Control-Max-Age header is bad.",
                "Access-Control-Max-Ageヘッダーが不正です。",
            ),
            ("The Date header is bad.", "Date ヘッダーが不正です。"),
            ("Compressed with Brotli.", "Brotli で圧縮されています。"),
            ("Compressed with Brotli.", "brotli で圧縮されています。"),  # case is free
            ("Nothing here.", "何もありません。"),
        ]
        for msgid, msgstr in cases:
            with self.subTest(msgid=msgid):
                self.assertIsNone(rules.field_name_changed(msgid, msgstr))

    def test_a_longer_name_does_not_stand_in_for_a_shorter_one(self) -> None:
        msgid = "The Access-Control header is old."
        self.assertIsNotNone(rules.field_name_changed(msgid, "Access-Control-Max-Age は古い。"))

    def test_message_names_the_field(self) -> None:
        self.assertEqual(
            rules.field_name_changed("The Cache-Status header.", "ヘッダー。"),
            "keep the field name `Cache-Status` exactly as written",
        )

    def test_names_come_from_the_parsers(self) -> None:
        names = rules.field_names()
        for name in ("Access-Control-Max-Age", "Content-Disposition", "Referer", "ETag"):
            self.assertIn(name, names)


class GlossaryTest(unittest.TestCase):
    def check(self, lang: str, msgid: str, msgstr: str) -> Optional[str]:
        return rules.glossary(msgid, msgstr, lang) or rules.glossary_low(msgid, msgstr, lang)

    def test_ja_avoid_and_ok(self) -> None:
        self.assertIn(
            "ディレクティブ", self.check("ja", "Unknown directive.", "不明な指示です。") or ""
        )
        self.assertIsNone(self.check("ja", "Unknown directive.", "不明なディレクティブです。"))
        self.assertIsNotNone(
            self.check("ja", "A header.", "ヘッダの値")
        )  # ヘッダ not followed by ー
        self.assertIsNone(self.check("ja", "A header.", "ヘッダーの値"))
        self.assertIsNotNone(self.check("ja", "The response.", "応答です"))

    def test_ja_value_is_not_flagged_next_to_variable(self) -> None:
        self.assertIsNotNone(self.check("ja", "Bad value.", "不正な変数です"))
        self.assertIsNone(self.check("ja", "Bad value for the variable.", "変数の不正な値です"))

    def test_ja_origin_is_not_the_origin_field_or_cross_origin(self) -> None:
        self.assertIsNotNone(self.check("ja", "Unknown origin.", "不明な起源です"))
        self.assertIsNone(self.check("ja", "The Origin header is missing.", "起源が欠落"))
        self.assertIsNone(self.check("ja", "A Cross-Origin policy.", "起源ポリシー"))

    def test_ja_field_and_deprecated(self) -> None:
        self.assertIsNotNone(self.check("ja", "A header field.", "ヘッダー分野です"))
        self.assertIsNotNone(self.check("ja", "It is deprecated.", "廃止されました"))

    def test_zh(self) -> None:
        self.assertIsNotNone(self.check("zh", "The header is bad.", "头部不正确"))
        self.assertIsNotNone(self.check("zh", "The header is bad.", "请求头不正确"))
        self.assertIsNone(self.check("zh", "The header is bad.", "标头不正确"))
        self.assertIsNone(self.check("zh", "A cache hit.", "缓存命中头"))  # no 'header' in msgid
        self.assertIsNotNone(self.check("zh", "The speculation rule is bad.", "猜测规则不对"))
        self.assertIsNotNone(self.check("zh", "A cookie.", "一个饼干"))
        self.assertIsNone(self.check("zh", "A cookie.", "一个 Cookie"))

    def test_es(self) -> None:
        self.assertIsNotNone(self.check("es", "The header is bad.", "El encabezado es malo."))
        self.assertIsNone(self.check("es", "The header is bad.", "La cabecera es mala."))
        self.assertIsNotNone(self.check("es", "Not supported.", "No soportada."))
        self.assertIsNone(self.check("es", "Not supported.", "No compatible."))

    def test_fr_english_header_outside_names_and_code(self) -> None:
        self.assertIsNotNone(self.check("fr", "The header is bad.", "Le header est mauvais."))
        self.assertIsNone(self.check("fr", "The header is bad.", "L'en-tête est mauvais."))
        self.assertIsNone(self.check("fr", "The Cache-Control header.", "L'en-tête Cache-Control."))
        self.assertIsNone(self.check("fr", "The `x` header.", "L'en-tête `x-header`."))
        self.assertIsNone(
            self.check(
                "fr",
                "See cross-origin-opener-policy-header.",
                "Voir cross-origin-opener-policy-header.",
            )
        )

    def test_unknown_language_and_no_trigger(self) -> None:
        self.assertIsNone(self.check("de", "The header.", "Der header."))
        self.assertIsNone(self.check("ja", "Nothing.", "指示"))

    def test_ja_coding_does_not_flag_other_words_with_code(self) -> None:
        msgid = "Unknown coding."
        for ok in (
            "不明なエンコード",
            "不明なエラーコード",
            "不明なステータスコード",
            "不明なコーディング",
        ):
            self.assertIsNone(self.check("ja", msgid, ok), ok)
        self.assertIsNotNone(self.check("ja", msgid, "不明なコード"))

    def test_untranslated_string_is_not_flagged(self) -> None:
        msgid = "The Deprecation header has an invalid type."
        for lang in ("fr", "ja"):
            self.assertIsNone(self.check(lang, msgid, msgid))
            self.assertIsNone(self.check(lang, msgid, msgid + "\n"))
        self.assertIsNone(rules.strength("A MUST.", "A MUST.", "es"))

    def test_zh_terms_are_simplified_only(self) -> None:
        for lang in ("zh", "zh_CN", "zh-CN", "zh_Hans"):
            self.assertIsNotNone(self.check(lang, "The header.", "头部"), lang)
        for lang in ("zh_TW", "zh-Hant", "zh_HK", "zh_Hant_TW"):
            self.assertIsNone(self.check(lang, "The header.", "头部"), lang)
            self.assertEqual(rules.glossary_hint(lang, "The header."), "")
            self.assertIsNone(rules.strength("It should be set.", "必须设置。", lang))

    def test_low_entries_are_reported_separately(self) -> None:
        self.assertIsNone(rules.glossary("The response.", "応答です", "ja"))
        self.assertIsNotNone(rules.glossary_low("The response.", "応答です", "ja"))
        self.assertIsNotNone(rules.glossary("A directive.", "指示", "ja"))
        self.assertIsNone(rules.glossary_low("A directive.", "指示", "ja"))
        lows = [e.term for lang in glossary_data.GLOSSARY.values() for e in lang if e.low]
        self.assertIn("response", lows)

    def test_message_names_the_preferred_term(self) -> None:
        self.assertEqual(
            self.check("ja", "Unknown directive.", "不明な指示です。"),
            "use 'ディレクティブ' for 'directive', not '指示'",
        )

    def test_prompt_line_only_when_relevant(self) -> None:
        self.assertEqual(rules.glossary_hint("ja", "Nothing special."), "")
        self.assertEqual(rules.glossary_hint("de", "A header."), "")
        hint = rules.glossary_hint("ja", "A directive and a header.")
        self.assertEqual(
            hint, " Terminology: translate 'directive' as 'ディレクティブ'; 'header' as 'ヘッダー'."
        )
        plain = build_prompt("ja", "Nothing.", False, None)
        self.assertEqual(build_prompt("ja", "Nothing.", False, None, hint=""), plain)
        with_hint = build_prompt("ja", "A header.", False, None, hint=hint)
        self.assertIn(hint + PROMPT_END.format(text="A header."), with_hint)


class StrengthTest(unittest.TestCase):
    def test_should_became_must(self) -> None:
        cases = [
            ("fr", "Clients should send it.", "Les clients doivent l'envoyer."),
            ("fr", "You SHOULD send it.", "Vous devez l'envoyer."),
            ("es", "You should send it.", "Debes enviarlo."),
            ("ja", "Clients SHOULD send it.", "クライアントは送信する必要があります。"),
            ("ja", "It should not repeat.", "繰り返してはなりません。"),
            ("zh", "Clients should send it.", "客户端必须发送。"),
        ]
        for lang, msgid, msgstr in cases:
            with self.subTest(lang=lang, msgstr=msgstr):
                self.assertIn("'should'", rules.strength(msgid, msgstr, lang) or "")

    def test_must_became_should(self) -> None:
        cases = [
            ("ja", "Senders MUST send it.", "送信するべきです。"),
            ("fr", "It must be set.", "Il devrait être défini."),
            ("es", "It must be set.", "Debería definirse."),
            ("zh", "Senders must not generate it.", "发送方不应生成它。"),
        ]
        for lang, msgid, msgstr in cases:
            with self.subTest(lang=lang):
                self.assertIn("'must'", rules.strength(msgid, msgstr, lang) or "")

    def test_faithful_translations_pass(self) -> None:
        cases = [
            ("fr", "It should be set.", "Il devrait être défini."),
            ("es", "It should be set.", "Debería definirse."),
            ("ja", "It should be set.", "設定するべきです。"),
            ("zh", "It should be set.", "应该设置。"),
            ("fr", "It must be set.", "Il doit être défini."),
            ("zh", "It must be set.", "必须设置。"),
            (
                "fr",
                "It should be set; it must be valid.",
                "Il devrait être défini; il doit être valide.",
            ),
            (
                "fr",
                "It should be set; it must be valid.",
                "Il doit être défini.",
            ),  # both words in msgid
            ("fr", "It is set.", "Il doit être défini."),  # neither
            ("fr", "It should be set.", "Il est défini."),  # neither in msgstr
        ]
        for lang, msgid, msgstr in cases:
            with self.subTest(lang=lang, msgstr=msgstr):
                self.assertIsNone(rules.strength(msgid, msgstr, lang))

    def test_more_must_and_should_forms(self) -> None:
        should = [
            ("zh", "It must be an integer.", "值应为整数。"),
            ("zh", "It must be an integer.", "值应是整数。"),
            ("ja", "It should be set.", "設定しなければいけません。"),
            ("es", "It should be set.", "Tiene que definirse."),
            ("es", "It should be set.", "Deberá definirse."),
            ("fr", "It should be set.", "Il faut le définir."),
            ("zh", "It should be set.", "须设置。"),
            ("zh", "It should not be set.", "不得设置。"),
        ]
        for lang, msgid, msgstr in should:
            with self.subTest(msgstr=msgstr):
                self.assertIsNotNone(rules.strength(msgid, msgstr, lang))
        for lang, msgid, msgstr in [
            ("zh", "It must be set.", "须设置。"),
            ("zh", "It should be set.", "应为整数。"),
            ("ja", "It must be set.", "設定しなければいけません。"),
            ("es", "It must be set.", "Tiene que definirse."),
            ("es", "It must be set.", "Deberá definirse."),
            ("fr", "It must be set.", "Il faut le définir."),
            ("fr", "It should be set.", "Il faudrait le définir."),
        ]:
            with self.subTest(msgstr=msgstr):
                self.assertIsNone(rules.strength(msgid, msgstr, lang))

    def test_zh_ying_inside_other_words_is_not_a_should(self) -> None:
        for word in ("响应", "对应", "适应", "应用", "相应"):
            self.assertIsNotNone(rules.strength("It should be set.", f"{word}必须。", "zh"))
        self.assertIsNone(rules.strength("It must be set.", "必须设置响应。", "zh"))
        self.assertIsNone(rules.strength("It must be set.", "响应需要设置应用。", "zh"))

    def test_debe_is_not_a_prefix_of_deberia(self) -> None:
        self.assertIsNone(rules.strength("It should be set.", "Debería definirse.", "es"))

    def test_keyword_left_in_english(self) -> None:
        self.assertIn("left in English", rules.strength("A MUST NOT.", "Un MUST NOT.", "es") or "")
        self.assertIsNone(rules.strength("Use `MUST` here.", "Use `MUST` aquí.", "es"))

    def test_other_languages_are_skipped(self) -> None:
        self.assertIsNone(rules.strength("It should be set.", "Es muss gesetzt sein.", "de"))


class StyleRuleTest(unittest.TestCase):
    def test_leftover_the(self) -> None:
        self.assertIsNotNone(rules.leftover_english("The x.", "The 値は不正です。", "ja"))
        self.assertIsNotNone(rules.leftover_english("The x.", "The valeur est mauvaise.", "fr"))
        self.assertIsNone(rules.leftover_english("The x.", "値は不正です。", "ja"))
        self.assertIsNone(
            rules.leftover_english("The x.", "The x.", "ja")
        )  # untranslated as a whole
        self.assertIsNone(rules.leftover_english("The x.", "The y.", "en"))
        self.assertIsNone(rules.leftover_english("The x.", "The y.", None))

    def test_punctuation(self) -> None:
        for lang, good in (
            ("ja", "不正です。"),
            ("zh", "不正确！"),
            ("fr", "Mauvais ?"),
            ("es", "Malo."),
        ):
            self.assertIsNone(rules.punctuation("It is bad!", good, lang), good)
        self.assertIsNone(rules.punctuation("It is bad.", "不正です：", "ja"))
        self.assertIsNone(rules.punctuation("It is bad.", "不正です。」", "ja"))
        self.assertIsNone(rules.punctuation("It is bad.", "Il est « mauvais. »", "fr"))
        self.assertIsNotNone(rules.punctuation("It is bad.", "不正です", "ja"))
        self.assertIsNotNone(rules.punctuation("Is it bad?", "不正ですか", "ja"))
        self.assertIsNotNone(rules.punctuation("It is `bad`.", "Il est `mauvais`", "fr"))
        self.assertIsNone(rules.punctuation("It is bad", "Il est mauvais", "fr"))  # msgid has none
        self.assertIsNone(rules.punctuation("It is bad.", "Il est mauvais", None))

    def test_backticks_added(self) -> None:
        plain = "The Accept-Language header isn't valid."
        self.assertIsNotNone(
            rules.backticks_added(plain, "L'en-tête `Accept-Language` est invalide.")
        )
        self.assertIsNotNone(
            rules.backticks_added(plain, "L'en-tête `Accept-Language est invalide.")
        )
        self.assertIsNone(rules.backticks_added(plain, "L'en-tête Accept-Language est invalide."))
        self.assertIsNone(rules.backticks_added(plain, "\uff40\u2018\u2019"))  # other quotes
        self.assertIsNone(rules.backticks_added("The `Vary` header.", "L'en-tête `Vary`."))
        self.assertIsNone(rules.backticks_added("The `Vary` header.", "L'en-tête Vary."))

    def test_backticks_added_is_reported_and_not_critical(self) -> None:
        issues = CatalogChecker().check_pair("Vary is bad.", "`Vary` est mauvais.", "fr")
        self.assertEqual([i.issue_type for i in issues], [IssueType.BACKTICKS_ADDED])


class StructureTest(unittest.TestCase):
    def test_paragraphs(self) -> None:
        self.assertIn(
            "1 paragraphs, msgid has 2", rules.structure("A.\n\nB.\n", "AB。", "ja") or ""
        )
        self.assertIsNone(rules.structure("A.\n\nB.\n", "あ。\n\nい。\n", "ja"))

    def test_indented_code_block(self) -> None:
        msgid = "For example:\n\n    Content-Range: bytes 1-100/200\n"
        self.assertIn(
            "indentation",
            rules.structure(msgid, "例:\n\nContent-Range: bytes 1-100/200\n", "ja") or "",
        )
        self.assertIsNone(
            rules.structure(msgid, "例:\n\n    Content-Range: bytes 1-100/200\n", "ja")
        )

    def test_cjk_line_breaks(self) -> None:
        wrapped = "これは長い文章で、\nここで折り返されています。"
        self.assertIn("line break", rules.structure("A long\nsentence.", wrapped, "ja") or "")
        self.assertIsNone(rules.structure("A long\nsentence.", wrapped, "fr"))
        self.assertEqual(
            rules.collapse_cjk_breaks(wrapped, "ja"), "これは長い文章で、ここで折り返されています。"
        )

    def test_collapse_keeps_structure(self) -> None:
        keep = [
            "段落一。\n\n段落二。",
            "一覧:\n- 項目一\n- 項目二",
            "表:\n| a | b |\n| c | d |",
            "例:\n```\ncode\n```\nです。",
            "例:\n\n    code\n日本語。",
            "latin text\nmore latin",
            "### 見出し\nテキスト",
            "[1]: https://example.com/x\nテキスト",
            "- 項目一\n  続き\n- 項目二",
            "1. 項目一\n続きです。",
            "| 表 | 行 |\nテキスト",
        ]
        for text in keep:
            with self.subTest(text=text):
                self.assertEqual(rules.collapse_cjk_breaks(text, "ja"), text)
        self.assertEqual(rules.collapse_cjk_breaks("`code`\nです。", "zh"), "`code`です。")
        self.assertEqual(rules.collapse_cjk_breaks("あ\nい\n\nう\nえ", "ja"), "あい\n\nうえ")

    def test_match_whitespace_unwraps_cjk_only(self) -> None:
        self.assertEqual(match_whitespace("A\nb\n", "あ\nい", "ja"), "あい\n")
        self.assertEqual(match_whitespace("A\nb\n", "a\nb", "fr"), "a\nb\n")
        self.assertEqual(match_whitespace("A\nb\n", "あ\nい"), "あ\nい\n")


class CheckIntegrationTest(unittest.TestCase):
    def test_check_pair_reports_the_new_issue_types(self) -> None:
        issues = CatalogChecker().check_pair(
            "The Cache-Status header is a directive.", "The キャッシュステータスは指示", "ja"
        )
        kinds = {i.issue_type for i in issues}
        for kind in (
            IssueType.FIELD_NAME_CHANGED,
            IssueType.GLOSSARY,
            IssueType.LEFTOVER_ENGLISH,
            IssueType.PUNCTUATION,
        ):
            self.assertIn(kind, kinds)

    def test_only_variables_and_syntax_are_critical(self) -> None:
        self.assertEqual(CRITICAL_ISSUES, (IssueType.BAD_VARIABLE, IssueType.SYNTAX_ERROR))

    def test_plurals_are_ignored(self) -> None:
        self.assertEqual(CatalogChecker().check_heuristics(("a", "b"), ("c", "d"), "ja"), [])


class TranslateRulesTest(unittest.TestCase):
    MSGID = "The Cache-Status header is bad."

    def test_field_name_is_hard_and_retried_with_the_name(self) -> None:
        ask, prompts = replies(
            "キャッシュステータスヘッダーが不正です。", "Cache-Status ヘッダーが不正です。"
        )
        result = translate(ask, "ja", self.MSGID, mode=PROTECT_LINKS)
        self.assertEqual(result.text, "Cache-Status ヘッダーが不正です。")
        self.assertEqual(result.retries, 1)
        self.assertIn("keep the field name `Cache-Status` exactly as written", prompts[1])

    def test_field_name_failure_is_blanked(self) -> None:
        ask, _ = replies(*["ヘッダーが不正です。"] * 3)
        result = translate(ask, "ja", self.MSGID, mode=PROTECT_LINKS)
        self.assertIsNone(result.text)
        self.assertIn("FIELD_NAME_CHANGED", result.error)
        self.assertIn("FIELD_NAME_CHANGED", HARD_PREFIXES)

    def test_coding_name_is_hard(self) -> None:
        ask, _ = replies(*["ブロトリで圧縮。"] * 3)
        self.assertIsNone(translate(ask, "ja", "Compressed with Brotli.", mode=PROTECT_LINKS).text)

    def test_advisory_rules_end_as_fuzzy(self) -> None:
        cases = [
            ("ja", "Unknown directive.", "不明な指示です。"),  # glossary
            ("fr", "It should be set.", "Il doit être défini."),  # strength
            ("ja", "It is bad.", "The 不正です。"),  # leftover English
            ("ja", "It is bad.", "不正です"),  # punctuation
        ]
        for lang, msgid, msgstr in cases:
            with self.subTest(msgstr=msgstr):
                ask, prompts = replies(msgstr, msgstr, msgstr)
                result = translate(ask, lang, msgid)
                self.assertEqual((result.text, result.fuzzy, result.retries), (msgstr, True, 2))
                self.assertEqual(len(prompts), 3)

    def test_glossary_retry_names_the_preferred_term(self) -> None:
        ask, prompts = replies("不明な指示です。", "不明なディレクティブです。")
        result = translate(ask, "ja", "Unknown directive.")
        self.assertEqual((result.text, result.fuzzy), ("不明なディレクティブです。", False))
        self.assertIn("use 'ディレクティブ' for 'directive', not '指示'", prompts[1])

    def test_glossary_line_in_the_prompt_only_when_relevant(self) -> None:
        ask, prompts = replies("不明なディレクティブです。", "何もありません。")
        translate(ask, "ja", "Unknown directive.")
        translate(ask, "ja", "Nothing here.")
        self.assertIn("Terminology: translate 'directive' as 'ディレクティブ'.", prompts[0])
        self.assertNotIn("Terminology", prompts[1])

    def test_cjk_wrapping_is_removed_before_checking(self) -> None:
        ask, _ = replies("これは長い文章で、\nここで折り返されています。")
        result = translate(ask, "ja", "A long\nsentence.")
        self.assertEqual(result.text, "これは長い文章で、ここで折り返されています。")
        self.assertFalse(result.fuzzy)


class WholeCatalogTest(unittest.TestCase):
    """The English text echoed back is a stand-in for a perfect copy: no hard failures."""

    @staticmethod
    def msgids() -> List[str]:
        with open(POT, "rb") as handle:
            return [m.id for m in read_po(handle) if m.id and isinstance(m.id, str)]

    def test_echo_passes_every_hard_rule(self) -> None:
        for lang in ("fr", "es", "ja", "zh"):
            for msgid in self.msgids():
                result = translate(text_of_prompt, lang, msgid)
                self.assertIsNotNone(result.text, f"{lang}: {msgid[:60]!r}: {result.error}")

    def test_some_msgids_have_field_names(self) -> None:
        found = [m for m in self.msgids() if rules.names_in(m)]
        self.assertGreater(len(found), 20)
        for msgid in found:
            self.assertIsNone(rules.field_name_changed(msgid, msgid), msgid[:60])


def text_of_prompt(prompt: str) -> str:
    return text_of(prompt)


if __name__ == "__main__":
    unittest.main()
