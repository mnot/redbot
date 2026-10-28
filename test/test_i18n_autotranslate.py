"""Tests for tools/i18n/autotranslate.py. No real model is ever called: a fake stands in."""

import contextlib
import io
import os
import tempfile
import unittest
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest import mock

from babel.messages.catalog import Catalog
from babel.messages.pofile import read_po

from tools.i18n import autotranslate
from tools.i18n.autotranslate import (
    DEFAULT_PROTECT,
    DEFAULT_TEMPERATURE,
    PROMPT_END,
    PROMPT_START,
    PROTECT_ALL,
    PROTECT_LINKS,
    PROTECT_MODES,
    PROTECT_NAMES,
    RETRIES,
    build_parser,
    code_span_rule,
    drop_added_backticks,
    MARK,
    pick_mark,
    prompt_text,
    protect,
    repair_code_spans,
    repair_placeholders,
    Result,
    restore,
    supports_option,
    token_error,
    translate,
    unwrapped,
    wrap_names,
)
from tools.i18n import glossary, rules
from tools.i18n.autotranslate import name_spans
from tools.i18n.rules import field_names
from tools.i18n.utils import load_catalog, save_catalog

POT = os.path.join(os.path.dirname(__file__), "..", "redbot", "translations", "messages.pot")

TEXT_MARK = "Here is the text to translate:\n\n"
OLD_PROMPT = (
    "You are translating short strings and messages for use in a HTTP linting tool. "
    "Translate the following text to language code 'fr'. When they appear, retain "
    "embeddded variables as they are. Do not translate HTTP protocol element names "
    "(such as header field names). Acronyms (such as 'IMS' and 'INM') should be "
    "retained. Return ONLY the translation, NO OTHER TEXT AT ALL. "
    "Here is the text to translate:\n\n"
)

SAMPLES = [
    "The `Content-Type` header declares `%(declared_charset)s`.",
    "Use `bytes */<length>` (e.g., `0.5`), or `a\nmulti-line span`, please.",
    "See [its\ndefinition](%(ref_uri)s) for more.%(position)s",
    "See [RFC 9112 Section 3.2](https://www.rfc-editor.org/rfc/rfc9112.html#section-3.2).",
    "Visit https://example.org/a, https://example.org/b; or https://example.org/c.",
    "([`Link`](https://example.org/x)), `%(a)s`, `%(b)s`: 50%% done.",
    "Nothing to protect here.",
    "``double `tick` span`` and `single`",
]


def protect_all(text: str) -> Tuple[str, List[str]]:
    return protect(text, mode=PROTECT_ALL)


def text_of(prompt: str) -> str:
    return prompt.split(TEXT_MARK, 1)[1]


class FakeResponse:
    def __init__(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text


class FakeModel:
    """Records prompts and options; `reply` maps a prompt to the reply text."""

    class Options:  # llm models expose a pydantic class; model_fields is what we use
        model_fields = {"temperature": None}

    def __init__(self, reply: Callable[[str], str]) -> None:
        self.reply = reply
        self.calls: List[Tuple[str, Dict[str, Any]]] = []

    def prompt(self, prompt: str, **options: Any) -> FakeResponse:
        self.calls.append((prompt, options))
        return FakeResponse(self.reply(prompt))


class FakeModelWithoutTemperature(FakeModel):
    class Options:
        model_fields = {"max_tokens": None}

    def prompt(self, prompt: str, **options: Any) -> FakeResponse:
        if options:  # a real llm model raises on options it doesn't have
            raise ValueError(f"unexpected options {options}")
        return super().prompt(prompt)


def faithful(prompt: str) -> str:
    """A 'translation' that keeps everything (tokens included) but adds a prefix."""
    return "FR: " + text_of(prompt)


def masked_reply(msgid: str, reply: str, mode: str) -> str:
    """reply as a model that copies the tokens would write it: protected text -> tokens."""
    for number, span in enumerate(prompt_text(msgid, MARK, mode)[1], 1):
        reply = reply.replace(span, f"@@{number}@@")
    return reply


def ask_for(model: FakeModel) -> Callable[[str], str]:
    return lambda prompt: model.prompt(prompt).text()


class ProtectTest(unittest.TestCase):
    def test_round_trip(self) -> None:
        for text in SAMPLES:
            masked, spans = protect_all(text)
            self.assertEqual(restore(masked, spans), text, text)

    def test_protected_text_is_gone(self) -> None:
        masked, spans = protect_all(
            "Use `a\nb` and [x](https://e.org/p) and %(v)s and https://e.org/q."
        )
        for secret in ("`", "https://", "%(", "a\nb"):
            self.assertNotIn(secret, masked)
        self.assertEqual(len(spans), 4)

    def test_multiline_code_span(self) -> None:
        masked, spans = protect_all("Use `bytes */\n<length>` here")
        self.assertEqual(spans, ["`bytes */\n<length>`"])
        self.assertEqual(masked, "Use @@1@@ here")

    def test_link_text_stays_translatable(self) -> None:
        masked, spans = protect_all("See [its definition](%(ref_uri)s) now")
        self.assertEqual(masked, "See [its definition]@@1@@ now")
        self.assertEqual(spans, ["(%(ref_uri)s)"])

    def test_code_in_link_text(self) -> None:
        masked, spans = protect_all("[`Link`](https://e.org/x)")
        self.assertEqual(masked, "[@@1@@]@@2@@")
        self.assertEqual(spans, ["`Link`", "(https://e.org/x)"])

    def test_url_keeps_trailing_punctuation_outside(self) -> None:
        masked, spans = protect_all("a https://e.org/x, b https://e.org/y.")
        self.assertEqual(masked, "a @@1@@, b @@2@@.")
        self.assertEqual(spans, ["https://e.org/x", "https://e.org/y"])

    def test_adjacent_placeholders_and_percent(self) -> None:
        masked, spans = protect_all("%(a)s%(b)s 50%% (%(c)s)")
        self.assertEqual(masked, "@@1@@@@2@@ 50@@3@@ (@@4@@)")
        self.assertEqual(restore(masked, spans), "%(a)s%(b)s 50%% (%(c)s)")

    def test_unbalanced_backtick_is_left_alone(self) -> None:
        masked, spans = protect_all("a `broken and `%(v)s` b")
        self.assertEqual(restore(masked, spans), "a `broken and `%(v)s` b")

    def test_blank_line_ends_a_code_span_search(self) -> None:
        # an unclosed backtick must not pair with one in a later paragraph
        text = "Odd `tick here.\n\nNext paragraph with `code` here."
        self.assertEqual(protect_all(text)[1], ["`code`"])

    def test_restore_ignores_unknown_tokens(self) -> None:
        self.assertEqual(restore("a @@5@@ b", ["x"]), "a @@5@@ b")

    def test_nothing_to_protect_gives_the_old_prompt(self) -> None:
        masked, spans = protect_all("Plain text.")
        self.assertEqual((masked, spans), ("Plain text.", []))
        prompt = autotranslate.build_prompt("fr", masked, False, None)
        self.assertEqual(prompt, OLD_PROMPT + "Plain text.")

    def test_prompt_mentions_tokens_only_when_needed(self) -> None:
        prompt = autotranslate.build_prompt("fr", "A @@1@@", True, None)
        self.assertIn("copy each one exactly", prompt)
        self.assertTrue(prompt.startswith(PROMPT_START.format(lang="fr")))
        self.assertTrue(prompt.endswith(PROMPT_END.format(text="A @@1@@")))


class TokenErrorTest(unittest.TestCase):
    MASKED = "A @@1@@ and @@2@@"

    def test_ok(self) -> None:
        self.assertIsNone(token_error(self.MASKED, "Un @@2@@ et @@1@@", 2))

    def test_missing(self) -> None:
        self.assertIn("missing @@2@@", token_error(self.MASKED, "Un @@1@@", 2) or "")

    def test_duplicated(self) -> None:
        error = token_error(self.MASKED, "Un @@1@@ et @@2@@ @@2@@", 2)
        self.assertIn("repeated @@2@@", error or "")

    def test_invented(self) -> None:
        error = token_error(self.MASKED, "Un @@1@@ et @@2@@ @@3@@", 2)
        self.assertIn("invented @@3@@", error or "")

    def test_reformatted_token_is_missing(self) -> None:
        self.assertIn("missing", token_error(self.MASKED, "Un @@ 1 @@ et @@2@@", 2) or "")

    def test_added_backticks(self) -> None:
        error = token_error(self.MASKED, "Un `@@1@@` et @@2@@", 2)
        self.assertIn("backticks", error or "")


class TranslateTest(unittest.TestCase):
    MSGID = (
        "The `Content-Type` field says `%(declared_charset)s`; "
        "see [its definition](%(ref_uri)s) or https://example.org/x."
    )

    def run_translate(
        self,
        reply: Callable[[str], str],
        msgid: Optional[str] = None,
        rules: Optional[List[autotranslate.Rule]] = None,
        mode: str = PROTECT_ALL,
    ) -> Tuple[Optional[str], int, str, FakeModel]:
        model = FakeModel(reply)
        self.res = translate(ask_for(model), "fr", msgid or self.MSGID, rules, mode)
        return self.res.text, self.res.retries, self.res.error, model

    def test_good_translation_passes_through(self) -> None:
        result, retries, _, model = self.run_translate(faithful)
        self.assertEqual(result, "FR: " + self.MSGID)
        self.assertEqual(retries, 0)
        self.assertEqual(len(model.calls), 1)

    def test_model_sees_masked_text_and_token_sentence(self) -> None:
        _, _, _, model = self.run_translate(faithful)
        prompt = model.calls[0][0]
        for secret in ("Content-Type", "declared_charset", "ref_uri", "example.org"):
            self.assertNotIn(secret, prompt)
        self.assertIn("copy each one exactly", prompt)

    def test_plain_text_prompt_is_unchanged(self) -> None:
        result, _, _, model = self.run_translate(faithful, "Nothing special here at all.")
        self.assertEqual(model.calls[0][0], OLD_PROMPT + "Nothing special here at all.")
        self.assertEqual(result, "FR: Nothing special here at all.")

    def test_missing_token_is_retried_with_the_error(self) -> None:
        replies = iter(["Sans jeton @@1@@ seulement", None])

        def reply(prompt: str) -> str:
            first = next(replies)
            return first if first is not None else faithful(prompt)

        result, retries, _, model = self.run_translate(reply)
        self.assertEqual(result, "FR: " + self.MSGID)
        self.assertEqual(retries, 1)
        self.assertNotIn("rejected", model.calls[0][0])
        self.assertIn("rejected: missing @@2@@", model.calls[1][0])
        self.assertTrue(model.calls[1][0].endswith(TEXT_MARK + text_of(model.calls[0][0])))

    def test_duplicated_and_invented_tokens_are_rejected(self) -> None:
        for bad in ("@@1@@ @@1@@ @@2@@ @@3@@ @@4@@", "@@1@@ @@2@@ @@3@@ @@4@@ @@5@@"):
            result, retries, error, model = self.run_translate(lambda p, b=bad: b)
            self.assertIsNone(result, bad)
            self.assertEqual(len(model.calls), 3)
            self.assertTrue(error)

    def test_validation_failure_is_retried(self) -> None:
        # tokens are fine, but a sentence repeats: caught by the i18n-check logic
        msgid = "The `%(directive)s` cache directive requires a value, which was not given."
        repeated = (
            "@@1@@ exige une valeur. Aucune valeur n'a été fournie. Aucune valeur n'a été fournie."
        )
        replies = iter([repeated, None])

        def reply(prompt: str) -> str:
            first = next(replies)
            return first if first is not None else faithful(prompt)

        result, retries, _, model = self.run_translate(reply, msgid)
        self.assertEqual(retries, 1)
        self.assertEqual(result, "FR: " + msgid)
        self.assertIn("rejected: DUPLICATED_TEXT", model.calls[1][0])

    def test_retry_exhaustion(self) -> None:
        result, retries, error, model = self.run_translate(lambda p: "Rien @@1@@")
        self.assertIsNone(result)
        self.assertEqual(retries, 2)
        self.assertEqual(len(model.calls), 3)
        self.assertIn("missing", error)

    def test_custom_rule_error_reaches_the_prompt(self) -> None:
        def no_prefix(msgid: str, msgstr: str, lang: Optional[str]) -> List[str]:
            return ["do not start with FR"] if msgstr.startswith("FR") else []

        replies = iter(["FR: @@1@@ @@2@@ @@3@@ @@4@@", None])

        def reply(prompt: str) -> str:
            first = next(replies)
            return first if first is not None else "Voir " + text_of(prompt)

        _, retries, _, model = self.run_translate(reply, rules=[no_prefix])
        self.assertEqual(retries, 1)
        self.assertIn("rejected: do not start with FR.", model.calls[1][0])

    def test_whitespace_copied_from_msgid(self) -> None:
        msgid = "\n  Some `code` text here, long enough to pass.\n\n"
        # the model drops the whitespace, as the maintainer's run showed
        result, _, _, _ = self.run_translate(lambda p: "FR: " + text_of(p).strip(), msgid)
        self.assertEqual(result, "\n  FR: " + msgid.strip() + "\n\n")
        self.assertEqual(autotranslate.match_whitespace("a\n", " b "), "b\n")

    def test_invented_token_without_spans_is_rejected(self) -> None:
        result = translate(lambda p: "Texte @@1@@", "fr", "Plain text.", mode=PROTECT_ALL)
        self.assertIsNone(result.text)
        self.assertIn("invented", result.error)

    def test_literal_token_in_msgid(self) -> None:
        msgid = "A literal @@1@@ here and `x` in the text."
        result, _, _, model = self.run_translate(faithful, msgid)
        self.assertEqual(result, "FR: " + msgid)
        self.assertIn("@@@1@@@", model.calls[0][0])

    def test_error_in_prompt_is_truncated(self) -> None:
        def noisy(msgid: str, msgstr: str, lang: Optional[str]) -> List[str]:
            return ["LINK_MISMATCH extra: " + "u" * 3000]

        _, _, error, model = self.run_translate(faithful, rules=[noisy])
        self.assertLessEqual(len(error), autotranslate.MAX_ERROR)
        self.assertNotIn("u" * 250, model.calls[1][0])
        self.assertIn("rejected: LINK_MISMATCH extra: uuu", model.calls[1][0])

    def test_advisory_failure_keeps_the_last_candidate_as_fuzzy(self) -> None:
        def advisory(msgid: str, msgstr: str, lang: Optional[str]) -> List[str]:
            return ["SUSPICIOUS_LENGTH length ratio 0.10"]

        self.run_translate(faithful, rules=[advisory])
        self.assertEqual(
            self.res, Result("FR: " + self.MSGID, 2, "SUSPICIOUS_LENGTH length ratio 0.10", True)
        )

    def test_variable_and_syntax_failures_are_blanked(self) -> None:
        for kind in ("BAD_VARIABLE Missing: %(x)s", "SYNTAX_ERROR Stray '%'"):
            self.run_translate(faithful, rules=[lambda i, o, lang, k=kind: [k]])
            self.assertEqual(self.res, Result(None, 2, kind, False))

    def test_i18n_check_rule_uses_the_language(self) -> None:
        msgid = "A message that is long enough for the length check to apply."
        rule = autotranslate.i18n_check_rule
        # ratio 0.3 is fine for ja, too short for the default range
        self.assertEqual(rule(msgid, "x" * 17 + "。", "ja"), [])
        self.assertTrue(rule(msgid, "x" * 18, "fr"))
        # ratio 1.8 is fine for the default range, too long for ja
        self.assertTrue(rule(msgid, "x" * 105, "ja"))
        self.assertEqual(rule(msgid, "x" * 104 + ".", "fr"), [])

    def test_empty_reply_is_retried(self) -> None:
        replies = iter(["", None])

        def reply(prompt: str) -> str:
            first = next(replies)
            return first if first is not None else faithful(prompt)

        result, retries, _, _ = self.run_translate(reply)
        self.assertEqual(retries, 1)
        self.assertIsNotNone(result)


class LinksModeTest(unittest.TestCase):
    """--protect links: only URLs and link targets are masked; spans are verified."""

    MSGID = TranslateTest.MSGID  # `Content-Type`, `%(declared_charset)s`, a target, a URL

    def run_translate(
        self, reply: Callable[[str], str], msgid: Optional[str] = None
    ) -> Tuple[Result, FakeModel]:
        model = FakeModel(reply)
        return translate(ask_for(model), "fr", msgid or self.MSGID, mode=PROTECT_LINKS), model

    def test_modes_and_default(self) -> None:
        self.assertEqual(PROTECT_MODES, ("names", "links", "all"))
        self.assertEqual(DEFAULT_PROTECT, PROTECT_NAMES)
        self.assertEqual(build_parser().parse_args([]).protect, "names")
        self.assertEqual(build_parser().parse_args(["--protect", "names"]).protect, "names")
        self.assertEqual(build_parser().parse_args(["--protect", "all"]).protect, "all")
        self.assertEqual(build_parser().parse_args(["--protect", "links"]).protect, "links")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            build_parser().parse_args(["--protect", "none"])

    def test_main_passes_the_mode_on(self) -> None:
        for argv, want in ((["--protect", "all"], "all"), ([], "names")):
            calls: List[Tuple[Tuple[Any, ...], Dict[str, Any]]] = []
            args = ["autotranslate", "--po_file", "x.po", "--lang", "fr", *argv]
            with (
                mock.patch.object(
                    autotranslate, "autotranslate_file", lambda *a, **k: calls.append((a, k))
                ),
                mock.patch("sys.argv", args),
            ):
                autotranslate.main()
            self.assertEqual(calls[0][1]["protect_mode"], want)

    def test_echo_passes_and_links_are_restored(self) -> None:
        result, model = self.run_translate(faithful)
        self.assertEqual(result, Result("FR: " + self.MSGID))
        self.assertEqual(len(model.calls), 1)

    def test_prompt_shows_spans_and_masks_only_links(self) -> None:
        _, model = self.run_translate(faithful)
        prompt = model.calls[0][0]
        self.assertIn("Copy text in backticks and %(name)s placeholders exactly", prompt)
        self.assertEqual(
            text_of(prompt),
            "The `Content-Type` field says `%(declared_charset)s`; "
            "see [its definition]@@1@@ or @@2@@.",
        )
        for secret in ("ref_uri", "example.org"):
            self.assertNotIn(secret, prompt)

    def test_no_visible_sentence_without_visible_spans(self) -> None:
        _, model = self.run_translate(faithful, "See https://example.org/x for more.")
        self.assertNotIn("backticks", model.calls[0][0])
        self.assertIn("copy each one exactly", model.calls[0][0])
        _, model = self.run_translate(faithful, "Nothing special here at all.")
        self.assertEqual(model.calls[0][0], OLD_PROMPT + "Nothing special here at all.")

    def test_unrepairable_span_is_retried_with_the_exact_span(self) -> None:
        replies = iter(  # two spans for one: not repairable
            [lambda p: "FR: " + text_of(p).replace("`Content-Type`", "`Tipo` `Tipo`"), faithful]
        )
        result, model = self.run_translate(lambda p: next(replies)(p))
        self.assertEqual(result, Result("FR: " + self.MSGID, 1))
        self.assertNotIn("rejected", model.calls[0][0])
        self.assertIn(
            "rejected: CODE_SPAN_CHANGED keep `Content-Type` exactly, including the backticks;",
            model.calls[1][0],
        )

    def test_dropped_span_fails_hard_after_retries(self) -> None:
        result, model = self.run_translate(lambda p: text_of(p).replace("`Content-Type` ", ""))
        self.assertIsNone(result.text)
        self.assertFalse(result.fuzzy)
        self.assertEqual(len(model.calls), 3)
        self.assertIn("keep `Content-Type` exactly, including the backticks", result.error)
        self.assertNotIn("TOKEN_CHANGED", result.error)  # only the hard cause is reported
        self.assertIn("keep `Content-Type` exactly, including the backticks", model.calls[1][0])

    def test_renamed_placeholder_fails_hard(self) -> None:
        result, model = self.run_translate(
            lambda p: text_of(p).replace("%(declared_charset)s", "%(charset)s %(other)s")
        )
        self.assertIsNone(result.text)
        self.assertEqual(len(model.calls), 3)
        self.assertIn("BAD_VARIABLE", result.error)
        self.assertIn("%(declared_charset)s", model.calls[1][0])

    def test_renamed_placeholder_outside_a_span_fails_hard(self) -> None:
        result, _ = self.run_translate(
            lambda p: text_of(p).replace("%(x)s", "%(y)s %(z)s"), "Value %(x)s is not valid here."
        )
        self.assertIsNone(result.text)
        self.assertIn("BAD_VARIABLE", result.error)

    def test_reordered_spans_are_fine(self) -> None:
        msgid = "Use `a` before `b`, not `c`."
        result, _ = self.run_translate(lambda p: "`c` ... `b` ... `a`", msgid)
        self.assertEqual(result.text, "`c` ... `b` ... `a`")

    def test_spans_are_compared_as_a_multiset(self) -> None:
        result, _ = self.run_translate(lambda p: "Utilisez `a`.", "Use `a` and `a` again.")
        self.assertIsNone(result.text)
        self.assertIn("keep `a` exactly", result.error)

    def test_extra_duplicate_span_is_flagged(self) -> None:
        msgid = "Use `a` here, which is long enough to measure."
        result, _ = self.run_translate(lambda p: "Utilisez `a` `a` `a` ici, assez long.", msgid)
        self.assertTrue(result.fuzzy)
        self.assertIn("you added `a`", result.error)

    def test_backticks_lost_but_text_kept_is_advisory(self) -> None:
        msgid = "The `Link` header is not valid here, which is long enough."
        replies = iter(["Link ヘッダーは無効です。", "L'en-tête `Link` est invalide ici."])
        result, model = self.run_translate(lambda p: next(replies), msgid)
        self.assertEqual(result, Result("L'en-tête `Link` est invalide ici.", 1))
        self.assertIn("rejected: CODE_SPAN_BACKTICKS keep `Link` exactly", model.calls[1][0])
        result, model = self.run_translate(lambda p: "Link ヘッダーは無効です。", msgid)
        self.assertEqual(len(model.calls), 3)
        self.assertTrue(result.fuzzy)
        self.assertEqual(result.text, "Link ヘッダーは無効です。")
        self.assertIn("CODE_SPAN_BACKTICKS", result.error)

    def test_changed_text_is_hard_even_if_other_spans_lost_only_backticks(self) -> None:
        msgid = "The `Link` and `NEL` headers are not valid here, long enough."
        result, _ = self.run_translate(lambda p: "Link と 「優先」 は無効です。", msgid)
        self.assertIsNone(result.text)
        self.assertIn("CODE_SPAN_CHANGED keep `NEL`", result.error)

    def test_percent_is_named_in_the_sentence_only_when_present(self) -> None:
        _, model = self.run_translate(faithful, "Done: 50%% of `x` is fine here.")
        self.assertIn("placeholders and %% exactly", model.calls[0][0])
        _, model = self.run_translate(faithful, "Done: `x` is fine here.")
        self.assertNotIn("%% exactly", model.calls[0][0])
        _, model = self.run_translate(faithful, "Done: 50%% is fine here.")
        self.assertIn("placeholders and %% exactly", model.calls[0][0])
        result, _ = self.run_translate(lambda p: "Fait: 50% ici.", "Done: 50%% is fine here.")
        self.assertIsNone(result.text)  # a lone % is a SYNTAX_ERROR

    def test_span_is_named_verbatim_and_long_spans_are_cut(self) -> None:
        msgid = "Use `a  b\nc` here, which is long enough to measure."
        _, model = self.run_translate(lambda p: "Rien.", msgid)
        self.assertIn("keep `a  b\nc` exactly, including the backticks", model.calls[1][0])
        long_span = "`" + "x" * 300 + "`"
        _, model = self.run_translate(lambda p: "Rien.", f"Use {long_span} here, long enough.")
        self.assertIn("including the backticks", model.calls[1][0])
        self.assertIn("`xxx", model.calls[1][0])
        self.assertNotIn("x" * 150, model.calls[1][0].split("Here is the text")[0])

    def test_odd_backtick_count_in_msgid_gives_no_verdict(self) -> None:
        msgid = "Use `Content-Encoding` and `gzip, and `br` here, long enough."
        result, model = self.run_translate(
            lambda p: "`br` ... `Content-Encoding` ... `gzip.", msgid
        )
        self.assertEqual(result.text, "`br` ... `Content-Encoding` ... `gzip.")
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(code_span_rule(msgid, "anything", "ja"), [])

    def test_added_span_in_msgid_with_backticks_is_unwrapped(self) -> None:
        msgid = "The `Expect` header is missing, and the Vary header too, which is long."
        reply = "L'en-tête `Expect` est absent, et `Vary` aussi."
        result, model = self.run_translate(lambda p: reply, msgid)
        self.assertEqual(result, Result("L'en-tête `Expect` est absent, et Vary aussi."))
        self.assertEqual(len(model.calls), 1)

    def test_odd_characters_in_spans(self) -> None:
        msgid = (
            "Use `a@@b` or `x@@1@@y`, `100%% {x}`, `日本 語`, ``a ` b``, "
            "and `multi\nline` with [t](https://e.org/x)."
        )
        result, model = self.run_translate(faithful, msgid)
        self.assertEqual(result.text, "FR: " + msgid)
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(text_of(model.calls[0][0]), msgid.replace("(https://e.org/x)", "@@@1@@@"))

    def test_links_around_and_inside_code_spans(self) -> None:
        masked, spans = protect("[`Link`](https://e.org/x), `https://e.org/y`", mode=PROTECT_LINKS)
        self.assertEqual(masked, "[`Link`]@@1@@, `https://e.org/y`")
        self.assertEqual(spans, ["(https://e.org/x)"])

    def test_protect_all_still_masks_everything(self) -> None:
        masked, _ = protect("A `b` %(c)s [d](https://e.org) 50%%", mode=PROTECT_ALL)
        self.assertEqual(masked, "A @@1@@ @@2@@ [d]@@3@@ 50@@4@@")

    def test_whitespace_is_copied_from_msgid(self) -> None:
        msgid = "\n Some `code` here, long enough.\n"
        result, _ = self.run_translate(lambda p: "FR: " + text_of(p).strip(), msgid)
        self.assertEqual(result.text, "\n FR: Some `code` here, long enough.\n")


class DropAddedBackticksTest(unittest.TestCase):
    """A msgid without backticks is plain text: backticks in the reply are removed."""

    CASES = [
        (
            "Access-Control-Max-Age must be an integer.",
            "`Access-Control-Max-Age` doit être un entier.",
        ),
        (
            "Vary: * effectively makes this response uncacheable.",
            "`Vary: *` rend cette réponse non cachable.",
        ),
        (
            "The Accept-Language header isn't valid.",
            "L'en-tête `Accept-Language` n'est pas valide.",
        ),
    ]

    def run_translate(self, msgid: str, reply: str, mode: str) -> Tuple[Result, FakeModel]:
        model = FakeModel(lambda p: masked_reply(msgid, reply, mode))
        return translate(ask_for(model), "fr", msgid, mode=mode), model

    def test_backticks_around_names_are_stripped_without_a_retry(self) -> None:
        for mode in PROTECT_MODES:
            for msgid, reply in self.CASES:
                result, model = self.run_translate(msgid, reply, mode)
                self.assertEqual(result.text, reply.replace("`", ""), (mode, msgid))
                self.assertFalse(result.fuzzy)
                self.assertEqual(result.retries, 0)
                self.assertEqual(len(model.calls), 1, (mode, msgid))

    def test_odd_count_is_stripped(self) -> None:
        msgid = "The Accept-Language header isn't valid."
        for mode in PROTECT_MODES:
            result, model = self.run_translate(
                msgid, "L'en-tête `Accept-Language n'est pas valide.", mode
            )
            self.assertEqual(result.text, "L'en-tête Accept-Language n'est pas valide.")
            self.assertEqual(len(model.calls), 1)

    def test_fence_lines_are_dropped_with_their_info_string(self) -> None:
        msgid = "The Accept-Language header isn't valid."
        body = "L'en-tête Accept-Language n'est pas valide."
        for mode in PROTECT_MODES:
            for reply in (
                f"```\n{body}\n```",
                f"```text\n{body}\n```",
                f"```markdown\n{body}\n```\n",
                f"  ``` md \n{body}\n  ```  ",
                f"```text\n{body}",  # a fence only at the start
                f"{body}\n```",  # and only at the end
            ):
                result, model = self.run_translate(msgid, reply, mode)
                self.assertEqual(result.text, body, (mode, reply))
                self.assertEqual(len(model.calls), 1)

    def test_inline_triple_backticks_are_not_a_fence_line(self) -> None:
        self.assertEqual(
            drop_added_backticks("Vary is bad.", "```x``` est mauvais."), "x est mauvais."
        )
        self.assertEqual(
            drop_added_backticks("Vary is bad.", "text\n```x``` est mauvais."),
            "text\nx est mauvais.",
        )

    def test_only_backticks_is_an_empty_reply(self) -> None:
        for reply in ("``", "```"):
            result, model = self.run_translate(
                "The Accept-Language header isn't valid.", reply, PROTECT_LINKS
            )
            self.assertIsNone(result.text)
            self.assertEqual(result.error, "the translation was empty")
            self.assertEqual(len(model.calls), RETRIES + 1)

    def test_other_quote_characters_are_untouched(self) -> None:
        reply = "L\u2019en-t\u00eate \uff40Accept-Language\uff40 \u2018n\u2019est\u2019 pas valide."
        result, _ = self.run_translate(
            "The Accept-Language header isn't valid.", reply, PROTECT_LINKS
        )
        self.assertEqual(result.text, reply)

    def test_msgid_with_backticks_keeps_names_masked_and_the_added_span_is_unwrapped(self) -> None:
        msgid = "The `Content-Type` header isn't valid, and Vary is long enough."
        for mode in PROTECT_MODES:
            reply = masked_reply(
                msgid, "L'en-tête `Content-Type` est invalide, et `Vary` aussi.", mode
            )
            model = FakeModel(lambda p: reply)
            result = translate(ask_for(model), "fr", msgid, mode=mode)
            if mode == PROTECT_ALL:  # `all` masks the span; the added one is rejected
                self.assertIsNone(result.text)
                self.assertEqual(len(model.calls), RETRIES + 1)
                self.assertIn("added", result.error.lower())
            else:  # kept as written; repair_code_spans removes the added span's backticks
                self.assertEqual(
                    result, Result("L'en-tête `Content-Type` est invalide, et Vary aussi.")
                )
                self.assertEqual(len(model.calls), 1)

    def test_function(self) -> None:
        self.assertEqual(drop_added_backticks("a b", "`a` ``b`"), "a b")
        self.assertEqual(drop_added_backticks("a `b`", "`a` b"), "`a` b")


class PluralTest(unittest.TestCase):
    def test_plural_reply_is_not_changed(self) -> None:
        catalog = Catalog(locale="fr")
        catalog.add(("One header.", "Many headers."), ("", ""), flags=["fuzzy"])
        model = FakeModel(lambda p: "Un `en-tête`.")
        saved: List[Any] = []
        with (
            mock.patch.object(autotranslate, "load_catalog", lambda path: catalog),
            mock.patch.object(autotranslate, "save_catalog", lambda path, cat: saved.append(cat)),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            autotranslate.autotranslate_file("x.po", "fr", "fake", 0, model=model)
        self.assertEqual(len(model.calls), 1)
        self.assertEqual([m.string for m in saved[0] if m.id], ["Un `en-tête`."])


class CodeSpanRuleTest(unittest.TestCase):
    def test_ok_and_reordered(self) -> None:
        self.assertEqual(code_span_rule("`a` `b`", "`b` x `a`", "ja"), [])
        self.assertEqual(code_span_rule("none", "none", "ja"), [])

    def test_missing_and_changed_are_hard(self) -> None:
        errors = code_span_rule("`NEL` and `Link`", "ネル and `Link`", "ja")
        self.assertEqual(errors, ["CODE_SPAN_CHANGED keep `NEL` exactly, including the backticks"])

    def test_kept_text_without_backticks_is_advisory(self) -> None:
        errors = code_span_rule("The `Link` header", "Link ヘッダー", "ja")
        self.assertEqual(
            errors, ["CODE_SPAN_BACKTICKS keep `Link` exactly, including the backticks"]
        )
        self.assertFalse(errors[0].startswith(autotranslate.HARD_PREFIXES))
        # the text must be a whole word outside code spans
        self.assertTrue(
            code_span_rule("`a` and `a`", "Utilisez `a`.", "ja")[0].startswith("CODE_SPAN_CHANGED")
        )
        self.assertTrue(code_span_rule("`Link`", "Linked", "ja")[0].startswith("CODE_SPAN_CHANGED"))

    def test_odd_backticks_in_msgid_are_skipped(self) -> None:
        self.assertEqual(code_span_rule("a `b` `c", "nothing", "ja"), [])

    def test_added_is_not_hard(self) -> None:
        errors = code_span_rule("none", "`x`", "ja")
        self.assertTrue(errors[0].startswith("CODE_SPAN_ADDED"))
        self.assertFalse(errors[0].startswith(autotranslate.HARD_PREFIXES))


class TemperatureTest(unittest.TestCase):
    def test_supports_option(self) -> None:
        self.assertTrue(supports_option(FakeModel(faithful), "temperature"))
        self.assertFalse(supports_option(FakeModelWithoutTemperature(faithful), "temperature"))
        self.assertFalse(supports_option(object(), "temperature"))

    def test_default(self) -> None:
        self.assertEqual(build_parser().parse_args([]).temperature, 0.2)
        self.assertEqual(DEFAULT_TEMPERATURE, 0.2)
        self.assertEqual(build_parser().parse_args(["--temperature", "0"]).temperature, 0.0)


class FileTest(unittest.TestCase):
    """autotranslate_file() on a real PO file with a fake model."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "messages.po")
        catalog = Catalog(locale="fr")
        catalog.add("Good `Content-Type` message, %(x)s.", "")
        catalog.add("Bad `Link` message that never works, %(y)s.", "vieux", flags=["fuzzy"])
        save_catalog(self.path, catalog)

    def run_file(self, model: FakeModel, **kwargs: Any) -> str:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            autotranslate.autotranslate_file(self.path, "fr", "fake", 0, model=model, **kwargs)
        return out.getvalue()

    def test_left_empty_is_reported_and_never_written(self) -> None:
        def reply(prompt: str) -> str:
            if "never" in text_of(prompt):
                return "garbage"  # no tokens at all
            return faithful(prompt)

        output = self.run_file(FakeModel(reply))
        messages = {m.id: m for m in load_catalog(self.path) if m.id}
        good = messages["Good `Content-Type` message, %(x)s."]
        bad = messages["Bad `Link` message that never works, %(y)s."]
        self.assertEqual(good.string, "FR: Good `Content-Type` message, %(x)s.")
        self.assertEqual(bad.string, "")
        self.assertNotIn("fuzzy", bad.flags)
        self.assertIn("1 entries left empty", output)
        self.assertIn("CODE_SPAN_CHANGED", output)  # the last error is listed with the msgid
        self.assertIn("Bad `Link` message that never works", output)

    def test_advisory_failure_is_kept_as_fuzzy_and_listed(self) -> None:
        catalog = load_catalog(self.path)
        catalog.add("A plain message that is long enough to measure.", "")
        save_catalog(self.path, catalog)

        def reply(prompt: str) -> str:
            return "Court." if "plain message" in prompt else faithful(prompt)

        output = self.run_file(FakeModel(reply))
        entry = {m.id: m for m in load_catalog(self.path)}[
            "A plain message that is long enough to measure."
        ]
        self.assertEqual(entry.string, "Court.")
        self.assertIn("fuzzy", entry.flags)
        self.assertIn("1 entries kept as fuzzy", output)
        self.assertIn("SUSPICIOUS_LENGTH", output)

    def test_protect_mode_is_passed_and_reported(self) -> None:
        for mode, visible in ((PROTECT_LINKS, True), (PROTECT_ALL, False)):
            self.setUp()  # a fresh catalog: the first pass fills it
            model = FakeModel(faithful)
            output = self.run_file(model, protect_mode=mode)
            self.assertIn(f"--protect {mode}", output)
            self.assertEqual("`Content-Type`" in model.calls[0][0], visible, mode)

    def test_left_empty_in_links_mode_says_so(self) -> None:
        output = self.run_file(
            FakeModel(lambda p: text_of(p).replace("`Link` ", "")), protect_mode=PROTECT_LINKS
        )
        self.assertIn("1 entries left empty (no valid translation; --protect links)", output)
        self.assertIn("keep `Link` exactly", output)

    def test_temperature_passed_when_supported(self) -> None:
        model = FakeModel(faithful)
        self.run_file(model, temperature=0.3)
        self.assertTrue(model.calls)
        for _, options in model.calls:
            self.assertEqual(options, {"temperature": 0.3})

    def test_temperature_omitted_when_unsupported(self) -> None:
        model = FakeModelWithoutTemperature(faithful)
        output = self.run_file(model, temperature=0.3)
        self.assertTrue(model.calls)
        for _, options in model.calls:
            self.assertEqual(options, {})
        self.assertIn("no temperature option", output)
        self.assertNotIn("left empty", output)


def pot_msgids() -> List[str]:
    with open(POT, "rb") as f:
        return [m.id for m in read_po(f) if m.id and isinstance(m.id, str)]


class NamesModeTest(unittest.TestCase):
    """--protect names: links, field names and coding names are masked."""

    def names(self, text: str) -> Tuple[str, List[str]]:
        return protect(text, mode=PROTECT_NAMES)

    def test_bare_name_in_a_summary(self) -> None:
        self.assertEqual(
            self.names("The Content-Length header is incorrect."),
            ("The @@1@@ header is incorrect.", ["Content-Length"]),
        )

    def test_two_names(self) -> None:
        self.assertEqual(
            self.names("Content-Length and Transfer-Encoding should not be present."),
            ("@@1@@ and @@2@@ should not be present.", ["Content-Length", "Transfer-Encoding"]),
        )

    def test_name_next_to_punctuation(self) -> None:
        self.assertEqual(
            self.names("Cache-Control: max-age and Expires. (Vary: User-Agent)"),
            ("@@1@@: max-age and Expires. (Vary: @@2@@)", ["Cache-Control", "User-Agent"]),
        )

    def test_every_occurrence_as_spelled_is_masked(self) -> None:
        masked, spans = self.names("(Content-Length), Content-Length-Foo and Content-Length.")
        self.assertEqual(masked, "(@@1@@), Content-Length-Foo and @@2@@.")
        self.assertEqual(spans, ["Content-Length"] * 2)

    def test_name_inside_a_code_span_is_masked_inside_it(self) -> None:
        masked, spans = self.names("The `Content-Type` field says `%(declared_charset)s`.")
        self.assertEqual(masked, "The `@@1@@` field says `%(declared_charset)s`.")
        self.assertEqual(spans, ["Content-Type"])
        masked, spans = self.names("The `Content-Encoding: gzip` header.")
        self.assertEqual(masked, "The `@@1@@: @@2@@` header.")
        self.assertEqual(spans, ["Content-Encoding", "gzip"])

    def test_coding_names_are_masked_in_any_position(self) -> None:
        masked, spans = self.names("The gzip and compress codings; `brotli`, Brotli.")
        self.assertEqual(masked, "The @@1@@ and compress codings; `@@2@@`, @@3@@.")
        self.assertEqual(spans, ["gzip", "brotli", "Brotli"])

    def test_ordinary_words_are_not_masked(self) -> None:
        for text in ("Follow the link and check the date.", "The link header and the date field."):
            self.assertEqual(self.names(text), (text, []), text)
        self.assertEqual(self.names("The Date header and a link.")[1], ["Date"])

    def test_names_in_placeholders_and_link_targets_are_not_masked_alone(self) -> None:
        masked, spans = self.names("The Link header: %(Link)s, see [Link](https://e.org/Link).")
        self.assertEqual(masked, "The @@1@@ header: %(Link)s, see [@@2@@]@@3@@.")
        self.assertEqual(spans, ["Link", "Link", "(https://e.org/Link)"])

    def test_code_spans_and_placeholders_stay_visible(self) -> None:
        masked, spans = self.names("Use `a b` and %(c)s here; 50%% of https://e.org/x.")
        self.assertEqual(masked, "Use `a b` and %(c)s here; 50%% of @@1@@.")
        self.assertEqual(spans, ["https://e.org/x"])

    def test_the_three_modes(self) -> None:
        text = "The `Content-Type` field is %(v)s: https://e.org/x, Foo header."
        self.assertEqual(
            protect(text, mode=PROTECT_NAMES)[0],
            "The `@@1@@` field is %(v)s: @@2@@, Foo header.",
        )
        self.assertEqual(
            protect(text, mode=PROTECT_LINKS)[0],
            "The `Content-Type` field is %(v)s: @@1@@, Foo header.",
        )
        self.assertEqual(
            protect(text, mode=PROTECT_ALL)[0], "The @@1@@ field is @@2@@: @@3@@, Foo header."
        )

    def test_round_trip_of_every_msgid_in_every_mode(self) -> None:
        msgids = pot_msgids()
        self.assertGreater(len(msgids), 100)
        for mode in PROTECT_MODES:
            for msgid in msgids:
                mark = pick_mark(msgid)
                masked, spans = protect(msgid, mark, mode)
                self.assertEqual(restore(masked, spans, mark), msgid, (mode, msgid))

    def test_echo_model_passes_for_every_msgid_in_every_mode(self) -> None:
        for mode in PROTECT_MODES:
            for msgid in pot_msgids():
                result = translate(text_of, "fr", msgid, mode=mode)
                self.assertEqual(result, Result(msgid), (mode, msgid))

    def test_model_sees_no_names_and_one_token_sentence(self) -> None:
        # a msgid with backticks keeps its names masked
        model = FakeModel(faithful)
        result = translate(ask_for(model), "fr", "Use `x`: Content-Length is wrong.")
        self.assertEqual(result, Result("FR: Use `x`: Content-Length is wrong."))
        prompt = model.calls[0][0]
        self.assertEqual(text_of(prompt), "Use `x`: @@1@@ is wrong.")
        self.assertEqual(prompt.count("Tokens like"), 1)

    def test_visible_sentence_when_code_spans_remain(self) -> None:
        model = FakeModel(faithful)
        translate(ask_for(model), "fr", "The `Content-Type` field is wrong here, as said.")
        self.assertIn("Copy text in backticks", model.calls[0][0])
        self.assertEqual(text_of(model.calls[0][0]), "The `@@1@@` field is wrong here, as said.")

    def test_dropped_token_is_retried_naming_it(self) -> None:
        replies = iter(["Elle est fausse.", None])

        def reply(prompt: str) -> str:
            first = next(replies)
            return first if first is not None else faithful(prompt)

        model = FakeModel(reply)
        result = translate(ask_for(model), "fr", "Use `x`: Content-Length is wrong.")
        self.assertEqual(result, Result("FR: Use `x`: Content-Length is wrong.", 1))
        self.assertIn("rejected: missing @@1@@", model.calls[1][0])

    def test_dropped_token_everywhere_is_left_empty(self) -> None:
        model = FakeModel(lambda p: "Elle est fausse.")
        result = translate(ask_for(model), "fr", "Use `x`: Content-Length is wrong.")
        self.assertEqual(len(model.calls), RETRIES + 1)
        self.assertIsNone(result.text)
        self.assertFalse(result.fuzzy)
        self.assertIn("missing @@1@@", result.error)

    def test_field_name_rule_still_guards_the_text(self) -> None:
        # with the name visible (links mode) a reply that loses it is a hard failure
        result = translate(lambda p: "Faux.", "fr", "Content-Length is wrong.", mode=PROTECT_LINKS)
        self.assertIsNone(result.text)
        self.assertIn("FIELD_NAME_CHANGED", result.error)


class RepairPlaceholdersTest(unittest.TestCase):
    """A placeholder the model renamed is put back, when that is unambiguous."""

    CASES = [
        (
            "The `%(field_name)s` field is not valid.",
            "`%(フィールド名)s` フィールドは無効です。",
            "`%(field_name)s` フィールドは無効です。",
        ),
        (
            "The `%(directive)s` cache directive requires a value.",
            "`%(ディレクティブ)s` には値が必要です。",
            "`%(directive)s` には値が必要です。",
        ),
        (
            "Status %(status)s is wrong.",
            "ステータス %(ステータスコード)s は誤りです。",
            "ステータス %(status)s は誤りです。",
        ),
        (
            "Fresh for %(effective)s seconds.",
            "%(有効)s 秒間有効です。",
            "%(effective)s 秒間有効です。",
        ),
        (
            "The value `%(value)s` is not defined for the `%(param)s` parameter.",
            "`%(値)s` は `%(パラメータ)s` では定義されていません。",
            "`%(value)s` は `%(param)s` では定義されていません。",
        ),
    ]

    def test_renamed_placeholders_are_put_back(self) -> None:
        for msgid, text, want in self.CASES:
            fixed, names = repair_placeholders(msgid, text)
            self.assertEqual(fixed, want, msgid)
            self.assertEqual(len(names), len(set(names)))
            self.assertTrue(names)

    def test_names_restored_are_returned(self) -> None:
        msgid, text, _ = self.CASES[4]
        self.assertEqual(repair_placeholders(msgid, text)[1], ["value", "param"])

    def test_mapping_is_by_order_of_appearance_not_sorted_order(self) -> None:
        self.assertEqual(
            repair_placeholders("%(a)s then %(b)s", "%(y)s dann %(x)s"),
            ("%(a)s dann %(b)s", ["a", "b"]),
        )
        self.assertEqual(
            repair_placeholders("%(b)s then %(a)s", "%(x)s dann %(y)s"),
            ("%(b)s dann %(a)s", ["b", "a"]),
        )

    def test_format_character_comes_from_the_msgid(self) -> None:
        self.assertEqual(
            repair_placeholders("Age %(age)d.", "年齢 %(年齢)s。")[0], "年齢 %(age)d。"
        )

    def test_valid_text_is_untouched(self) -> None:
        for msgid, _, want in self.CASES:
            self.assertEqual(repair_placeholders(msgid, want), (want, []))
        self.assertEqual(repair_placeholders("No placeholders.", "Aucun."), ("Aucun.", []))
        self.assertEqual(repair_placeholders("%(a)s %(b)s", "%(b)s %(a)s"), ("%(b)s %(a)s", []))

    def test_ambiguous_or_mismatched_counts_are_not_repaired(self) -> None:
        for msgid, text in (
            ("A %(a)s.", "A %(x)s %(y)s."),  # two unknown, one missing
            ("A %(a)s %(b)s.", "A %(x)s."),  # one unknown, two missing
            ("A %(a)s %(b)s.", "A %(x)s %(b)s %(y)s."),
            ("Plain.", "A %(x)s."),  # nothing is missing
            ("A %(a)s.", "A."),  # nothing is unknown
        ):
            self.assertEqual(repair_placeholders(msgid, text), (text, []), text)

    def test_repair_is_dropped_unless_the_placeholders_match_exactly(self) -> None:
        for msgid, text in (
            ("%(a)s and %(a)s", "%(b)s"),
            ("%(a)s", "%(b)s %(b)s"),
            ("%(a)s %(c)s", "%(b)s %(c)s %(c)s"),
        ):
            self.assertEqual(repair_placeholders(msgid, text), (text, []), text)

    def test_percent_percent_is_never_touched(self) -> None:
        self.assertEqual(
            repair_placeholders("50%% of %(x)s", "50%% の %(数)s"), ("50%% の %(x)s", ["x"])
        )
        text = "%%(数)s 100%%"
        self.assertEqual(repair_placeholders("%(x)s 100%%", text), (text, []))

    def test_repaired_entry_costs_one_call_and_is_clean(self) -> None:
        msgid = "The `%(field_name)s` field is not valid here, as it is long enough."
        for mode in (PROTECT_NAMES, PROTECT_LINKS):
            model = FakeModel(lambda p: text_of(p).replace("%(field_name)s", "%(フィールド名)s"))
            result = translate(ask_for(model), "fr", msgid, mode=mode)
            self.assertEqual(result, Result(msgid), mode)
            self.assertEqual(len(model.calls), 1, mode)

    VALUE_PARAM = "The value `%(value)s` is not defined for the `%(param)s` parameter."

    def test_several_renames_are_fuzzy_after_the_retries(self) -> None:
        model = FakeModel(
            lambda p: text_of(p)
            .replace("%(value)s", "%(値)s")
            .replace("%(param)s", "%(パラメータ)s")
        )
        result = translate(ask_for(model), "ja", self.VALUE_PARAM)
        self.assertEqual(len(model.calls), RETRIES + 1)
        self.assertTrue(result.fuzzy)
        self.assertEqual(result.text, self.VALUE_PARAM)
        self.assertIn("PLACEHOLDERS_RENAMED", result.error)
        self.assertIn("keep %(value)s, %(param)s exactly as written", model.calls[1][0])

    def test_swapped_order_is_not_accepted_silently(self) -> None:
        reply = "`%(パラメータ)s` パラメータには `%(値)s` は定義されていません。"
        model = FakeModel(lambda p: reply)
        result = translate(ask_for(model), "ja", self.VALUE_PARAM)
        self.assertEqual(len(model.calls), RETRIES + 1)
        self.assertTrue(result.fuzzy)  # mapped by position: wrong, but flagged for review
        self.assertEqual(
            result.text, "`%(value)s` パラメータには `%(param)s` は定義されていません。"
        )

    def test_a_retry_that_keeps_the_names_is_clean(self) -> None:
        replies = iter(["`%(パラメータ)s` と `%(値)s`。", None])

        def reply(prompt: str) -> str:
            first = next(replies)
            return first if first is not None else faithful(prompt)

        model = FakeModel(reply)
        result = translate(ask_for(model), "fr", self.VALUE_PARAM)
        self.assertEqual(result, Result("FR: " + self.VALUE_PARAM, 1))

    def test_three_renames_are_fuzzy(self) -> None:
        msgid = "Use %(a)s, %(b)s and %(c)s together, which is long enough."
        model = FakeModel(
            lambda p: text_of(p)
            .replace("%(a)s", "%(x)s")
            .replace("%(b)s", "%(y)s")
            .replace("%(c)s", "%(z)s")
        )
        result = translate(ask_for(model), "fr", msgid)
        self.assertEqual((result.text, result.fuzzy, len(model.calls)), (msgid, True, 3))

    def test_one_rename_stays_clean_in_one_call(self) -> None:
        msgid = "The `%(field_name)s` and `%(param)s` fields are not valid, long enough."
        model = FakeModel(lambda p: text_of(p).replace("%(field_name)s", "%(フィールド名)s"))
        result = translate(ask_for(model), "ja", msgid)
        self.assertEqual(result, Result(msgid))
        self.assertEqual(len(model.calls), 1)

    def test_unrepairable_rename_is_still_retried_and_left_empty(self) -> None:
        msgid = "The `%(field_name)s` field is not valid here, as it is long enough."
        model = FakeModel(lambda p: text_of(p).replace("%(field_name)s", "%(a)s %(b)s"))
        result = translate(ask_for(model), "fr", msgid)
        self.assertIsNone(result.text)
        self.assertEqual(len(model.calls), RETRIES + 1)
        self.assertIn("BAD_VARIABLE", result.error)


class RepairCodeSpansTest(unittest.TestCase):
    """A code span the model changed or unquoted is put back, when that is unambiguous."""

    STATUS = "The `412 (Precondition Failed)` status code means the condition was false."
    CASES = [
        (STATUS, "`412 (事前条件の失敗)` ステータスコードは条件が偽だったことを示します。"),
        ("Set `same-origin` here, which is long.", "ここに `同源` を設定します。"),
        ("The `Version` attribute is ignored.", "`バージョン`属性は無視されます。"),
        ("The `201 (Created)` status code.", "`201（作成済み）` ステータスコード。"),
        (
            "Do not use `'unsafe-inline'` here.",
            "ここでは `'安全でないインライン'` を使わないでください。",
        ),
        ("The `CONNECT` method is odd.", "`接続` メソッドは変です。"),
        ('Use `(self "https://example.com")` here.', 'ここでは `(自分 "https://example.com")`。'),
        ("Use ``a `b` c`` here.", "ここでは ``あ `b` c``。"),
        ("Use `a\nmulti-line span` here.", "ここでは `あ\n複数行` を使う。"),
    ]
    QUOTED = [
        ("「", "」"),
        ("『", "』"),
        ("“", "”"),
        ('"', '"'),
        ("‘", "’"),
        ("'", "'"),
        ("«", "»"),
        ("« ", " »"),
        ("«\u00a0", "\u00a0»"),
        ("„", "“"),
    ]

    def test_changed_content_is_restored_silently(self) -> None:
        for msgid, text in self.CASES:
            fixed, put_back = repair_code_spans(msgid, text)
            self.assertEqual(
                [m.group(0) for m in autotranslate.CODE_RE.finditer(fixed)],
                [m.group(0) for m in autotranslate.CODE_RE.finditer(msgid)],
                msgid,
            )
            self.assertEqual(len(put_back), 1, msgid)  # one: no advisory
            self.assertNotIn(put_back[0], text)
        self.assertEqual(
            repair_code_spans(self.STATUS, self.CASES[0][1])[0],
            "`412 (Precondition Failed)` ステータスコードは条件が偽だったことを示します。",
        )

    def test_quotes_are_turned_back_into_backticks(self) -> None:
        msgid = "Use `Link` and `max-age=0` here."
        for left, right in self.QUOTED:
            text = f"{left}Link{right} と {left}max-age=0{right} を使う。"
            self.assertEqual(
                repair_code_spans(msgid, text), ("`Link` と `max-age=0` を使う。", []), left
            )

    def test_quote_swap_and_one_changed_span_together(self) -> None:
        text = "「Link」 と `最大` を使う。"
        self.assertEqual(
            repair_code_spans("Use `Link` and `max-age` here.", text),
            ("`Link` と `max-age` を使う。", ["`max-age`"]),
        )

    def test_a_valid_span_in_another_place_is_kept(self) -> None:
        # the spans the model kept are not touched, even if it moved them: one changed span
        # is still unambiguous
        msgid = "Use `a` then `b` then `c`."
        self.assertEqual(
            repair_code_spans(msgid, "`b` と `a` と `X`。"), ("`b` と `a` と `c`。", ["`c`"])
        )

    def test_mapping_is_by_order_of_appearance_not_sorted_order(self) -> None:
        msgid = "Use `zeta` then `alpha`, and `mid`."
        self.assertEqual(
            repair_code_spans(msgid, "`ゼータ` と `アルファ`、`mid`。"),
            ("`zeta` と `alpha`、`mid`。", ["`zeta`", "`alpha`"]),
        )
        self.assertEqual(
            repair_code_spans(msgid, "`mid`、`アルファ` と `ゼータ`。"),
            ("`mid`、`zeta` と `alpha`。", ["`zeta`", "`alpha`"]),
        )

    def test_valid_text_is_untouched(self) -> None:
        for msgid, _ in self.CASES:
            self.assertEqual(repair_code_spans(msgid, msgid), (msgid, []))
        text = "`b` と `a`"  # reordered spans are fine
        self.assertEqual(repair_code_spans("`a` and `b`", text), (text, []))
        self.assertEqual(repair_code_spans("`a` and `a`", "`a` `a`"), ("`a` `a`", []))

    def test_repair_is_dropped_unless_the_spans_match_exactly(self) -> None:
        # replacing the span would pair up the backticks differently
        for text in ("`a`a``", "`a`b``", "`a` ``"):
            self.assertEqual(repair_code_spans("````", text), (text, []), text)

    def test_count_mismatch_is_not_repaired(self) -> None:
        for msgid, text in (
            ("Use `a` and `b`.", "`あ` を使う。"),  # one span lost
            ("Use `a`.", "`あ` と `b` を使う。"),  # one span added
            ("Use `a` and `b`.", "「a」 を使う。"),  # one quoted, one lost: still 1 span vs 2
            ("Use `a` and `a`.", "「a」 を使う。"),  # one candidate for two spans
        ):
            self.assertEqual(repair_code_spans(msgid, text), (text, []), text)

    def test_ambiguous_quoted_text_is_not_repaired(self) -> None:
        for text in ("「X」 と “X” を使う。", "「X」 と 「X」 を使う。"):
            self.assertEqual(repair_code_spans("Use `X` here.", text), (text, []), text)

    def test_only_exact_quoted_text_counts(self) -> None:
        for text in ("「x」 を使う。", "「X 」 を使う。", "「XY」 を使う。", "X を使う。"):
            self.assertEqual(repair_code_spans("Use `X` here.", text), (text, []), text)

    def test_quoted_text_inside_a_code_span_is_not_a_candidate(self) -> None:
        text = "`「X」` と `Y` を使う。"  # `「X」` is a span of its own, and `X` is lost
        self.assertEqual(
            repair_code_spans("Use `X` and `Y`.", text), ("`X` と `Y` を使う。", ["`X`"])
        )

    def test_quoted_text_inside_another_span_is_not_a_second_candidate(self) -> None:
        self.assertEqual(
            repair_code_spans("Use `X` and `Y`.", "「X」 と `Z「X」`。"),
            ("`X` と `Y`。", ["`Y`"]),
        )

    def test_quoted_candidate_twice_with_a_second_lacking_span_is_not_repaired(self) -> None:
        # two quoted X for one lost `X` is ambiguous; it must not be used to fill in `Z`
        text = "「X」 と 「X」 を使う。"
        self.assertEqual(repair_code_spans("Use `X` and `Z`.", text), (text, []))

    def test_overlapping_quotes_are_not_repaired(self) -> None:
        text = "'a'a' を使う。"
        self.assertEqual(repair_code_spans("Use `a` and `a`.", text), (text, []))

    def test_changed_span_whose_text_is_also_in_the_reply_is_fuzzy(self) -> None:
        msgid = "Use `a` (see) and `b`, which is long enough to measure."
        reply = "`a` (`参照`) と b、測れる長さです。"
        model = FakeModel(lambda p: reply)
        result = translate(ask_for(model), "ja", msgid)
        self.assertEqual(len(model.calls), RETRIES + 1)
        self.assertTrue(result.fuzzy)
        self.assertEqual(result.text, "`a` (`b`) と b、測れる長さです。")
        self.assertIn("CODE_SPANS_RESTORED", result.error)

    def test_identical_lacking_spans_are_not_a_guess(self) -> None:
        msgid = (  # the ETag-list `*` note: three identical spans
            "The `*` in the `%(field_name)s` field matches any current representation, so it is\n"
            "only valid on its own: the field's value is either `*` or a list of entity tags\n"
            "([RFC 9110, Section 13.1.1](https://www.rfc-editor.org/rfc/rfc9110.html#name-if-match)"
            " and\n[Section 13.1.2](https://www.rfc-editor.org/rfc/rfc9110.html#name-if-none-match))."
            "\n\nRecipients may handle a list that includes both in different ways; send either "
            "`*` or the\nentity tags."
        )
        self.assertEqual(msgid.count("`*`"), 3)
        model = FakeModel(lambda p: text_of(p).replace("`*`", "`星`"))
        result = translate(ask_for(model), "ja", msgid)
        self.assertEqual((result, len(model.calls)), (Result(msgid), 1))

    def test_msgid_without_backticks_or_with_an_odd_count_is_untouched(self) -> None:
        for msgid, text in (
            ("Use the Link field.", "`Link` を使う。"),
            ("Use the ` mark and `Link`.", "「Link」 を使う。"),
            ("Use it.", "それを使う。"),
        ):
            self.assertEqual(repair_code_spans(msgid, text), (text, []), text)

    def test_spans_with_placeholders_are_left_to_the_placeholder_checks(self) -> None:
        msgid = "The `%(field_name)s` field is `%(value)s` here."
        text = "`%(a)s %(b)s` フィールドは `%(value)s`。"
        self.assertEqual(repair_code_spans(msgid, text), (text, []))
        self.assertEqual(  # but unquoted ones are put back
            repair_code_spans(msgid, "「%(field_name)s」 フィールドは `%(value)s`。"),
            ("`%(field_name)s` フィールドは `%(value)s`。", []),
        )

    def test_repaired_entry_costs_one_call_and_is_clean(self) -> None:
        msgid = self.STATUS
        for mode in (PROTECT_NAMES, PROTECT_LINKS):
            model = FakeModel(
                lambda p: text_of(p).replace("412 (Precondition Failed)", "412 (失敗)")
            )
            result = translate(ask_for(model), "ja", msgid, mode=mode)
            self.assertEqual(result, Result(msgid), mode)
            self.assertEqual(len(model.calls), 1, mode)

    def test_quote_swap_costs_one_call_and_is_clean(self) -> None:
        msgid = "Use the `same-origin` and `credentialless` values here, which is long."
        model = FakeModel(
            lambda p: text_of(p)
            .replace("`same-origin`", "「same-origin」")
            .replace("`credentialless`", "“credentialless”")
        )
        result = translate(ask_for(model), "ja", msgid)
        self.assertEqual((result, len(model.calls)), (Result(msgid), 1))

    TWO = "Use the `same-origin` or `same-origin-allow-popups` value here, which is long."

    def test_several_changed_spans_are_fuzzy_after_the_retries(self) -> None:
        model = FakeModel(
            lambda p: text_of(p)
            .replace("`same-origin`", "`同源`")
            .replace("`same-origin-allow-popups`", "`同源弹出`")
        )
        result = translate(ask_for(model), "zh", self.TWO)
        self.assertEqual(len(model.calls), RETRIES + 1)
        self.assertTrue(result.fuzzy)
        self.assertEqual(result.text, self.TWO)
        self.assertIn("CODE_SPANS_RESTORED", result.error)
        self.assertIn(
            "Keep `same-origin`, `same-origin-allow-popups` exactly as written", model.calls[1][0]
        )

    def test_swapped_changed_spans_are_not_accepted_silently(self) -> None:
        reply = "值 `同源弹出` 或 `同源`。"  # the word order swapped the spans
        model = FakeModel(lambda p: reply)
        result = translate(ask_for(model), "zh", self.TWO)
        self.assertEqual(len(model.calls), RETRIES + 1)
        self.assertTrue(result.fuzzy)  # mapped by position: wrong, but flagged for review
        self.assertEqual(result.text, "值 `same-origin` 或 `same-origin-allow-popups`。")

    def test_a_retry_that_keeps_the_spans_is_clean(self) -> None:
        replies = iter(["`同源弹出` 和 `同源`。", None])

        def reply(prompt: str) -> str:
            first = next(replies)
            return first if first is not None else faithful(prompt)

        model = FakeModel(reply)
        result = translate(ask_for(model), "fr", self.TWO)
        self.assertEqual(result, Result("FR: " + self.TWO, 1))

    def test_unrepairable_span_is_still_retried_and_left_empty(self) -> None:
        model = FakeModel(lambda p: text_of(p).replace("`same-origin` or ", ""))
        result = translate(ask_for(model), "fr", self.TWO)
        self.assertIsNone(result.text)
        self.assertEqual(len(model.calls), RETRIES + 1)
        self.assertIn("CODE_SPAN_CHANGED", result.error)


class WrapNamesTest(unittest.TestCase):
    """--protect names: a msgid without backticks gets its names wrapped in them, not masked."""

    def prompt_text(self, msgid: str, mode: str = PROTECT_NAMES) -> Tuple[str, List[str]]:
        return prompt_text(msgid, MARK, mode)

    def test_summary_prompt_has_the_backticked_name_and_no_token_for_it(self) -> None:
        msgid = "The Age header's value is very large."
        model = FakeModel(lambda p: "FR: " + text_of(p))
        result = translate(ask_for(model), "ja", msgid)
        prompt = model.calls[0][0]
        self.assertEqual(text_of(prompt), "The `Age` header's value is very large.")
        self.assertNotIn("@@", prompt)
        self.assertNotIn("Tokens like", prompt)
        self.assertIn("Copy text in backticks", prompt)
        self.assertEqual(result, Result("FR: " + msgid))  # no backtick left
        self.assertNotIn("`", result.text or "")

    def test_a_reply_that_loses_the_name_is_retried_then_left_empty(self) -> None:
        model = FakeModel(lambda p: "Faux.")
        result = translate(ask_for(model), "fr", "Content-Length is wrong.")
        self.assertEqual(len(model.calls), RETRIES + 1)
        self.assertIsNone(result.text)
        self.assertIn("FIELD_NAME_CHANGED", result.error)

    def test_names_inside_link_text_links_stay_masked(self) -> None:
        self.assertEqual(
            self.prompt_text("See [the Content-Length header](https://e.org/Content-Length)."),
            ("See [the `Content-Length` header]@@1@@.", ["(https://e.org/Content-Length)"]),
        )
        self.assertEqual(
            self.prompt_text("Content-Length: see https://e.org/x."),
            ("`Content-Length`: see @@1@@.", ["https://e.org/x"]),
        )

    def test_two_names(self) -> None:
        self.assertEqual(
            self.prompt_text("Content-Length and Transfer-Encoding should not be present."),
            ("`Content-Length` and `Transfer-Encoding` should not be present.", []),
        )

    def test_names_next_to_punctuation(self) -> None:
        self.assertEqual(
            self.prompt_text("Cache-Control: max-age and Expires. (Vary: User-Agent)"),
            ("`Cache-Control`: max-age and Expires. (Vary: `User-Agent`)", []),
        )
        self.assertEqual(
            self.prompt_text("(Content-Length), Content-Length-Foo and Content-Length.")[0],
            "(`Content-Length`), Content-Length-Foo and `Content-Length`.",
        )

    def test_coding_names(self) -> None:
        self.assertEqual(
            self.prompt_text("The gzip and compress codings; Brotli.")[0],
            "The `gzip` and compress codings; `Brotli`.",
        )

    def test_placeholders_are_not_wrapped(self) -> None:
        self.assertEqual(
            self.prompt_text("The Link header: %(Link)s.")[0], "The `Link` header: %(Link)s."
        )

    def test_ordinary_words_are_not_wrapped(self) -> None:
        for text in ("Follow the link and check the date.", "The link header and the date field."):
            self.assertEqual(self.prompt_text(text), (text, []), text)
        self.assertEqual(
            self.prompt_text("The Date header and a link.")[0], "The `Date` header and a link."
        )

    def test_msgid_with_backticks_keeps_its_names_masked(self) -> None:
        for msgid in (
            "The `Content-Type` field is wrong: Content-Length too.",
            "Use `x`: Content-Length is wrong.",
        ):
            self.assertEqual(self.prompt_text(msgid), protect(msgid, MARK, PROTECT_NAMES), msgid)
            self.assertIn("@@1@@", self.prompt_text(msgid)[0])

    def test_links_and_all_modes_are_unchanged(self) -> None:
        msgid = "The Age header is large: https://e.org/x."
        for mode in (PROTECT_LINKS, PROTECT_ALL):
            self.assertEqual(self.prompt_text(msgid, mode), protect(msgid, MARK, mode))

    def test_urls_with_placeholders_are_masked_whole(self) -> None:
        for msgid, text in (
            (
                "See https://e.org/%(a)s?Date=1 and the Date header.",
                "See @@1@@ and the `Date` header.",
            ),
            ("Go to https://e.org/Age/%(a)s/gzip now.", "Go to @@1@@ now."),
            ("See https://e.org/%(path)s/Age for details.", "See @@1@@ for details."),
            ("See (https://e.org/%(a)s/Vary).", "See (@@1@@)."),
            ("See https://e.org/%(path)s/Age-x and Age header.", "See @@1@@ and `Age` header."),
        ):
            masked, spans = self.prompt_text(msgid)
            self.assertEqual(masked, text, msgid)
            self.assertEqual(len(spans), 1, msgid)
            self.assertEqual(spans, protect(msgid, MARK, PROTECT_LINKS)[1], msgid)
            self.assertEqual(masked.count("`") % 2, 0)

    def test_names_do_not_overlap(self) -> None:
        for name in field_names():
            text = f"The {name} header, {name}: {name}-x, ({name})."
            spans = name_spans(text)
            self.assertEqual(spans, sorted(spans), name)
            for (_, end), (start, _) in zip(spans, spans[1:]):
                self.assertLessEqual(end, start, name)
        for msgid in pot_msgids():
            spans = name_spans(msgid)
            for (_, end), (start, _) in zip(sorted(spans), sorted(spans)[1:]):
                self.assertLessEqual(end, start, msgid)

    def test_nothing_to_wrap(self) -> None:
        self.assertEqual(wrap_names("Nothing here."), "Nothing here.")

    def test_every_msgid_round_trips_in_every_mode(self) -> None:
        msgids = pot_msgids()
        self.assertGreater(len(msgids), 100)
        wrapped = 0
        for mode in PROTECT_MODES:
            for msgid in msgids:
                masked, spans = self.prompt_text(msgid, mode)
                back = drop_added_backticks(msgid, restore(masked, spans, pick_mark(msgid)))
                self.assertEqual(back.strip(), msgid.strip(), (mode, msgid))
                wrapped += mode == PROTECT_NAMES and "`" not in msgid and "`" in masked
        self.assertGreater(wrapped, 10)

    def test_echo_model_gives_back_the_msgid_in_every_mode(self) -> None:
        for mode in PROTECT_MODES:
            for msgid in pot_msgids():
                for lang in ("fr", "ja"):
                    result = translate(text_of, lang, msgid, mode=mode)
                    self.assertEqual(result, Result(msgid), (mode, lang, msgid))


class StrengthHintTest(unittest.TestCase):
    """A per-language line on 'should' and 'must' goes into the prompt."""

    def prompt(self, lang: str, msgid: str) -> str:
        model = FakeModel(lambda p: "x")
        translate(ask_for(model), lang, msgid)
        return model.calls[0][0]

    def test_words_found_as_the_strength_rule_reads_them(self) -> None:
        for msgid, found in (
            ("A server should reply.", ["should"]),
            ("A server SHOULD NOT reply, and must not.", ["should not", "must not"]),
            ("It must be, and should be.", ["should", "must"]),
            ("It should not be, but should.", ["should", "should not"]),
            ("Use `should` and `must` or https://e.org/should %(must)s.", []),
            ("It shouldn't; mustard.", []),
            ("Nothing.", []),
        ):
            self.assertEqual(rules.strength_words(msgid), found, msgid)

    def test_hint_once_for_the_words_that_occur(self) -> None:
        msgid = "A server should not send this, but must send that."
        hints = {
            "fr": "'should not' as 'ne devrait pas'; 'must' as 'doit'",
            "es": "'should not' as 'no debería'; 'must' as 'debe'",
            "ja": "'should not' as 'べきではありません'; 'must' as 'なければなりません'",
            "zh": "'should not' as '不应'; 'must' as '必须'",
        }
        for lang, line in hints.items():
            prompt = self.prompt(lang, msgid)
            self.assertEqual(prompt.count("Strength:"), 1, lang)
            self.assertIn(f" Strength: translate {line}.", prompt)
        self.assertIn(
            "'should' as 'devrait' or 'devraient' (never 'doit')",
            self.prompt("fr", "A server should reply."),
        )
        self.assertIn(
            "'should' as 'べきです' or 'ほうがよいです' (never 'なければなりません')",
            self.prompt("ja", "A server should reply."),
        )

    HINT_WORDS = {
        "fr": {
            "should": "'should' as 'devrait' or 'devraient' (never 'doit')",
            "should not": "'should not' as 'ne devrait pas'",
            "must": "'must' as 'doit'",
            "must not": "'must not' as 'ne doit pas'",
        },
        "es": {
            "should": "'should' as 'debería'",
            "should not": "'should not' as 'no debería'",
            "must": "'must' as 'debe'",
            "must not": "'must not' as 'no debe'",
        },
        "ja": {
            "should": "'should' as 'べきです' or 'ほうがよいです' (never 'なければなりません')",
            "should not": "'should not' as 'べきではありません'",
            "must": "'must' as 'なければなりません'",
            "must not": "'must not' as 'てはなりません'",
        },
        "zh": {
            "should": "'should' as '应该' or '应当'",
            "should not": "'should not' as '不应'",
            "must": "'must' as '必须'",
            "must not": "'must not' as '不得'",
        },
    }

    def test_every_hint_word_is_pinned(self) -> None:
        for lang, keys in self.HINT_WORDS.items():
            for key, line in keys.items():
                self.assertEqual(
                    rules.strength_hint(lang, f"A server {key} reply."),
                    f" Strength: translate {line}.",
                    (lang, key),
                )

    def test_hint_follows_the_terminology_sentence(self) -> None:
        prompt = self.prompt("fr", "The header should be present.")
        self.assertRegex(prompt, r"Terminology: [^.]*\. Strength: translate")

    def test_no_hint_for_other_languages(self) -> None:
        for lang in ("de", "zh_TW", "zh-TW", "pt_BR", "en"):
            self.assertNotIn("Strength", self.prompt(lang, "A server should or must reply."), lang)
        self.assertIn("Strength", self.prompt("zh_CN", "A server must reply."))
        self.assertIn("Strength", self.prompt("fr_CA", "A server must reply."))

    def test_prompts_without_the_words_are_unchanged(self) -> None:
        checked = 0
        for msgid in pot_msgids():
            if rules.strength_words(msgid):
                continue
            for lang in ("fr", "ja"):
                model = FakeModel(lambda p: "x")
                translate(ask_for(model), lang, msgid)
                mark = pick_mark(msgid)
                masked, spans = prompt_text(msgid, mark, DEFAULT_PROTECT)
                visible = bool(autotranslate.VISIBLE_RE.search(masked))
                expected = autotranslate.build_prompt(
                    lang,
                    masked,
                    bool(spans),
                    None,
                    mark,
                    visible,
                    visible and "%%" in masked,
                    rules.glossary_hint(lang, msgid),
                )
                self.assertEqual(model.calls[0][0], expected, (lang, msgid))
                checked += 1
        self.assertGreater(checked, 200)
        self.assertEqual(self.prompt("fr", "Nothing here."), OLD_PROMPT + "Nothing here.")

    def test_hint_words_agree_with_the_glossary(self) -> None:
        self.assertEqual(rules.strength_hint_problems(), [])
        self.assertEqual(set(glossary.STRENGTH_HINTS), set(glossary.STRENGTH))
        for table in glossary.STRENGTH_HINTS.values():
            self.assertEqual(set(table), set(rules.HINT_KEYS))

    def test_a_hint_word_the_rule_does_not_know_is_reported(self) -> None:
        wrong = {"fr": {**glossary.STRENGTH_HINTS["fr"], "must": (("devrait",), None)}}
        with mock.patch.object(rules, "STRENGTH_HINTS", wrong):
            problems = rules.strength_hint_problems()
        self.assertEqual(len(problems), 1)
        self.assertIn("'devrait' is not read as 'must'", problems[0])

    def test_the_wording_asked_for_passes_the_strength_rule(self) -> None:
        msgid = "A server should reply."
        self.assertIsNone(rules.strength(msgid, "Un serveur devrait répondre.", "fr"))
        self.assertIsNotNone(rules.strength(msgid, "Un serveur doit répondre.", "fr"))


class UnwrapAddedSpansTest(unittest.TestCase):
    """Spans the model added around words are unwrapped when the msgid's spans are all there."""

    def test_spanish_cabecera(self) -> None:
        msgid = "The `Link` header is invalid, which is long enough."
        text = "La `cabecera` `Link` no es válida, lo que es bastante largo."
        self.assertEqual(
            repair_code_spans(msgid, text),
            ("La cabecera `Link` no es válida, lo que es bastante largo.", []),
        )

    def test_japanese_header_and_location(self) -> None:
        msgid = "The `Location` header is invalid here."
        for text, fixed in (
            ("`ヘッダー` `Location` は無効です。", "ヘッダー `Location` は無効です。"),
            ("`Location` ヘッダーは `無効` です。", "`Location` ヘッダーは 無効 です。"),
        ):
            self.assertEqual(repair_code_spans(msgid, text), (fixed, []), text)
        msgid = "The `Location` header is invalid, as `Link`."
        text = "`ヘッダー` `Location` は `Link` と `Location` は無効です。"
        self.assertEqual(repair_code_spans(msgid, text), (text, []))  # `Location` twice

    def test_several_added_spans_all_go(self) -> None:
        self.assertEqual(
            repair_code_spans("Use `a` here.", "`x` usa `a` y `z`."), ("x usa `a` y z.", [])
        )

    def test_unwrapped(self) -> None:
        for span, inner in (
            ("`a`", "a"),
            ("``a `b` c``", "a `b` c"),
            ("`` a ``", "a"),
            ("` `", " "),
        ):
            self.assertEqual(unwrapped(span), inner, span)

    def test_unwrap_limit_is_three_words_and_thirty_characters(self) -> None:
        msgid = "Use `a` here."
        for extra, ok in (
            ("one two three", True),
            ("one two three four", False),
            ("x" * 30, True),
            ("x" * 31, False),
            ("あ" * 30, True),  # no spaces: the character limit applies
            ("あ" * 31, False),
            ("lo cual es bastante largo", False),
        ):
            text = f"`a` y `{extra}`."
            expected = (f"`a` y {extra}.", []) if ok else (text, [])
            self.assertEqual(repair_code_spans(msgid, text), expected, extra)

    def test_an_added_sentence_stays_advisory(self) -> None:
        msgid = "The `Link` header is invalid, which is long enough here."
        reply = "La cabecera `Link` no es válida, bastante largo. `Nota: este texto lo añadió el modelo.`"
        model = FakeModel(lambda p: reply)
        result = translate(ask_for(model), "es", msgid, mode=PROTECT_LINKS)
        self.assertTrue(result.fuzzy)
        self.assertEqual(result.text, reply)
        self.assertIn("CODE_SPAN_ADDED", result.error)
        self.assertEqual(len(model.calls), RETRIES + 1)

    def test_not_unwrapped_when_a_span_is_lacking(self) -> None:
        for msgid, text in (
            ("Use `a` and `b`.", "`a` `x` `y`"),  # `b` is lost: hard failure, not ours
            ("Use `a` and `b`.", "`a` `x` `y` `z`"),
        ):
            self.assertEqual(repair_code_spans(msgid, text), (text, []), text)

    def test_not_unwrapped_when_the_extra_span_repeats_one(self) -> None:
        for text in ("Usa `a` `a` `a` aquí.", "Usa `a` y `a` aquí."):
            self.assertEqual(repair_code_spans("Use `a` here.", text), (text, []), text)

    def test_not_unwrapped_with_an_odd_backtick_count_in_the_msgid(self) -> None:
        text = "`a` y `b`"
        self.assertEqual(repair_code_spans("Use ` and `a`.", text), (text, []))

    def test_not_unwrapped_when_an_inner_backtick_would_be_left_stray(self) -> None:
        text = "`a` y ``b ` c``"
        self.assertEqual(repair_code_spans("Use `a` here.", text), (text, []))

    def test_translate_is_clean_in_one_call(self) -> None:
        msgid = "The `Foo` header is invalid, which is long enough."
        reply = "La `cabecera` `Foo` no es válida, lo que es bastante largo."
        model = FakeModel(lambda p: reply)
        result = translate(ask_for(model), "es", msgid)
        self.assertEqual(
            result, Result("La cabecera `Foo` no es válida, lo que es bastante largo.")
        )
        self.assertEqual(len(model.calls), 1)

    def test_repeated_span_stays_advisory(self) -> None:
        model = FakeModel(lambda p: "Usa `a` y `a` aquí, lo bastante largo.")
        result = translate(ask_for(model), "es", "Use `a` here, which is long enough.")
        self.assertTrue(result.fuzzy)
        self.assertIn("CODE_SPAN_ADDED you added `a`", result.error)
        self.assertEqual(len(model.calls), RETRIES + 1)


if __name__ == "__main__":
    unittest.main()
