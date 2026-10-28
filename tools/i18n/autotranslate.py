import argparse
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Tuple

from .check import CatalogChecker
from .rules import (
    MAX_LISTED,
    OPAQUE_RE,
    collapse_cjk_breaks,
    glossary_hint,
    name_pattern,
    names_in,
    strength_hint,
)
from .utils import load_catalog, save_catalog, find_po_files, get_lang_from_path

DEFAULT_MODEL = "mlx-community/aya-expanse-8b-4bit"
DEFAULT_TEMPERATURE = 0.2
RETRIES = 2

# --protect modes. "names": links are masked; known field and coding names are masked too,
# except in a msgid without backticks, where they are wrapped in backticks instead (models
# drop a name token from a short sentence, but copy a name in backticks); code spans and
# placeholders stay visible and are checked after translation. "links": only URLs and
# Markdown link targets are masked. "all": everything is masked ("all" dropped tokens in 5%
# of ja entries). Models translate or transliterate a name left in view (FIELD_NAME_CHANGED).
PROTECT_NAMES = "names"
PROTECT_LINKS = "links"
PROTECT_ALL = "all"
PROTECT_MODES = (PROTECT_NAMES, PROTECT_LINKS, PROTECT_ALL)
DEFAULT_PROTECT = PROTECT_NAMES

# Spans the model must not touch are swapped for opaque tokens (@@1@@, @@2@@, ...) and
# put back afterwards. ASCII, no Markdown meaning, and not a word the model translates.
# If the msgid already contains the delimiter, a longer one (@@@, ...) is used.
MARK = "@@"
MAX_ERROR = 200
# others are advisory heuristics (GLOSSARY, STRENGTH, ...): kept as fuzzy after the retries
HARD_PREFIXES = ("BAD_VARIABLE", "SYNTAX_ERROR", "CODE_SPAN_CHANGED", "FIELD_NAME_CHANGED")
MAX_SPAN = 120  # longer spans are cut when named in an error


def token_re(mark: str) -> "re.Pattern[str]":
    return re.compile(re.escape(mark) + r"(\d+)" + re.escape(mark))


def pick_mark(msgid: str) -> str:
    mark = MARK
    while mark in msgid:
        mark += "@"
    return mark


CODE_PATTERN = r"(?P<code>(?P<ticks>`+)(?:(?!\n[ \t]*\n).)+?(?P=ticks)(?!`))"  # may span lines
CODE_RE = re.compile(CODE_PATTERN, re.DOTALL)
VISIBLE_RE = re.compile(CODE_PATTERN + r"|%\(|%%", re.DOTALL)  # what links mode leaves in view
PROTECTED_RE = re.compile(
    CODE_PATTERN + r"""
    | (?<=\])(?P<target>\((?:[^()\s]|\([^()\s]*\))+\))             # [text]<(target)>
    | (?P<url>https?://(?:%\([^)]*\)[a-z]|[^\s<>"'`)\]])+)         # bare URL
    | (?P<var>%\([^)]+\)[-\#0\ +]*[\d.]*[diouxXeEfFgGcrsa]|%%)     # %(name)s, %%
    """,
    re.VERBOSE | re.DOTALL,
)
URL_TRAILING = ".,;:!?"

PROMPT_START = (
    "You are translating short strings and messages for use in a HTTP linting tool. "
    "Translate the following text to language code '{lang}'. "
    "When they appear, retain embeddded variables as they are. "
    "Do not translate HTTP protocol element names (such as header field names). "
    "Acronyms (such as 'IMS' and 'INM') should be retained. "
    "Return ONLY the translation, NO OTHER TEXT AT ALL."
)
TOKEN_SENTENCE = (
    " Tokens like {token} stand for protected text: copy each one exactly, "
    "once, in the same place."
)
VISIBLE_SENTENCE = " Copy text in backticks and %(name)s placeholders exactly, unchanged."
VISIBLE_SENTENCE_PERCENT = (
    " Copy text in backticks, %(name)s placeholders and %% exactly, unchanged."
)
PROMPT_END = " Here is the text to translate:\n\n{text}"


def name_spans(text: str) -> List[Tuple[int, int]]:
    """
    (start, end) of every occurrence, as spelled, of a field or coding name that
    rules.names_in() finds (the FIELD_NAME_CHANGED rule's detection), including inside
    code spans, but not inside placeholders, link targets or URLs.
    """
    opaque = [(m.start(), m.end()) for m in OPAQUE_RE.finditer(text)]
    return [
        (m.start(), m.end())
        for name in names_in(text)
        for m in re.finditer(name_pattern(name), text)
        if not any(m.start() < end and start < m.end() for start, end in opaque)
    ]


def protect(text: str, mark: str = MARK, mode: str = DEFAULT_PROTECT) -> Tuple[str, List[str]]:
    """
    Replace protected spans with tokens; return the new text and the spans. Always
    masked: URLs and Markdown link targets. Names mode adds field and coding names;
    all mode adds code spans and placeholders.
    """
    found: List[Tuple[int, int]] = []
    for match in PROTECTED_RE.finditer(text):
        if mode != PROTECT_ALL and match.lastgroup in ("code", "var"):
            continue
        end = match.end()
        if match.lastgroup == "url":
            end = match.start() + len(match.group(0).rstrip(URL_TRAILING))
        found.append((match.start(), end))
    if mode == PROTECT_NAMES:
        found += name_spans(text)
    found.sort(key=lambda s: (s[0], s[0] - s[1]))  # longest first at one position
    spans: List[str] = []
    out: List[str] = []
    pos = 0
    for start, end in found:
        if start < pos:  # overlaps a span already masked
            continue
        spans.append(text[start:end])
        out.append(f"{text[pos:start]}{mark}{len(spans)}{mark}")
        pos = end
    out.append(text[pos:])
    return "".join(out), spans


def wrap_names(text: str) -> str:
    """text with every field or coding name (see name_spans) in backticks; mask links first."""
    out: List[str] = []
    pos = 0
    for start, end in sorted(name_spans(text)):  # name_spans don't overlap
        out.append(f"{text[pos:start]}`{text[start:end]}`")
        pos = end
    out.append(text[pos:])
    return "".join(out)


def prompt_text(msgid: str, mark: str, mode: str) -> Tuple[str, List[str]]:
    """
    The text the model sees, and the spans its tokens stand for. As protect(), but in names
    mode a msgid without backticks gets its names wrapped in backticks instead of masked;
    translate() strips every backtick from the reply (drop_added_backticks). A msgid with
    backticks can't be told from the reply's added ones, so it keeps its names masked.
    """
    if mode == PROTECT_NAMES and "`" not in msgid:
        masked, spans = protect(msgid, mark, PROTECT_LINKS)  # links first: no names inside them
        return wrap_names(masked), spans
    return protect(msgid, mark, mode)


def token_error(
    masked: str, translation: str, count: int, mark: str = MARK, ticks: bool = True
) -> Optional[str]:
    """Why the translation can't be un-masked (None if it can)."""
    found = [int(n) for n in token_re(mark).findall(translation)]
    missing = [n for n in range(1, count + 1) if n not in found]
    extra = sorted({n for n in found if n < 1 or n > count})
    repeated = sorted({n for n in found if found.count(n) > 1})
    problems = []
    if missing:
        problems.append("missing " + ", ".join(f"{mark}{n}{mark}" for n in missing))
    if repeated:
        problems.append("repeated " + ", ".join(f"{mark}{n}{mark}" for n in repeated))
    if extra:
        problems.append("invented " + ", ".join(f"{mark}{n}{mark}" for n in extra))
    if ticks and translation.count("`") != masked.count("`"):  # links mode: code_span_rule
        problems.append("added backticks")
    if not problems:
        return None
    return "; ".join(problems) + f". Copy every {mark}N{mark} token exactly, once"


def restore(translation: str, spans: List[str], mark: str = MARK) -> str:
    def put(match: "re.Match[str]") -> str:
        n = int(match.group(1))
        return spans[n - 1] if 1 <= n <= len(spans) else match.group(0)

    return token_re(mark).sub(put, translation)


PLACEHOLDER_RE = re.compile(r"%%|%\((?P<name>[^)]+)\)(?P<fmt>[-#0 +]*[\d.]*[diouxXeEfFgGcrsa])")


def placeholders(text: str) -> List[Tuple[str, str]]:
    """(name, format) of each %(name)s in text, in order; %% is skipped."""
    return [(m["name"], m["fmt"]) for m in PLACEHOLDER_RE.finditer(text) if m["name"]]


def repair_placeholders(msgid: str, text: str) -> Tuple[str, List[str]]:
    """
    Undo placeholders the model renamed (%(field_name)s -> %(フィールド名)s), in code spans
    too. Only when as many distinct names are unknown as are missing; the n-th unknown name
    (by first appearance) becomes the n-th missing one, with msgid's format. The repair is
    dropped unless the placeholders then equal msgid's exactly. %% is never touched.
    Returns the text and the names restored; with several, the mapping is only a guess
    from the order (the language may reorder them).
    """
    want, got = placeholders(msgid), placeholders(text)
    unknown = list(dict.fromkeys(n for n, _ in got if n not in {w for w, _ in want}))
    missing = list(dict.fromkeys(n for n, _ in want if n not in {g for g, _ in got}))
    if not unknown or len(unknown) != len(missing):
        return text, []
    rename = dict(zip(unknown, missing))
    fmt = dict(reversed(want))

    def put(match: "re.Match[str]") -> str:
        name = match["name"]
        return f"%({rename[name]}){fmt[rename[name]]}" if name in rename else match.group(0)

    fixed = PLACEHOLDER_RE.sub(put, text)
    if Counter(placeholders(fixed)) != Counter(want):
        return text, []
    return fixed, missing


def renamed_problem(names: List[str]) -> str:
    """The advisory problem for several renamed placeholders (see repair_placeholders)."""
    listed = ", ".join(f"%({n})s" for n in names[:MAX_LISTED])
    return (
        f"PLACEHOLDERS_RENAMED placeholders were renamed and mapped by position; "
        f"keep {listed} exactly as written"
    )


# Quote pairs a model may use in place of backticks
QUOTE_PAIRS = (
    ("「", "」"),
    ("『", "』"),
    ("“", "”"),
    ("„", "“"),
    ("«", "»"),
    ("«\u00a0", "\u00a0»"),
    ("« ", " »"),
    ('"', '"'),
    ("‘", "’"),
    ("'", "'"),
)


def code_spans(text: str) -> List["re.Match[str]"]:
    return list(CODE_RE.finditer(text))


def requote(text: str, span: str, count: int) -> str:
    """
    Put backticks back on a code span the model quoted instead (「T」, “T”, 'T', ...), when
    exactly count quoted occurrences of its text are outside code spans.
    """
    ticks = len(span) - len(span.lstrip("`"))
    inner = span[ticks:-ticks]
    if not inner.strip():
        return text
    code = [(m.start(), m.end()) for m in code_spans(text)]
    found = sorted(
        {
            (m.start(), m.end())
            for left, right in QUOTE_PAIRS
            for m in re.finditer(re.escape(left + inner + right), text)
            if not any(m.start() < end and start < m.end() for start, end in code)
        }
    )
    if len(found) != count:  # ambiguous; overlapping ones are caught by repair_code_spans
        return text
    for start, end in reversed(found):
        text = text[:start] + span + text[end:]
    return text


def unwrapped(span: str) -> str:
    """span without its backticks (and the one space CommonMark strips inside them)."""
    ticks = len(span) - len(span.lstrip("`"))
    inner = span[ticks:-ticks]
    return inner[1:-1] if inner.startswith(" ") and inner.endswith(" ") and inner.strip() else inner


MAX_UNWRAP_WORDS = 3  # longer extra spans may be text the model added: left for review
MAX_UNWRAP_CHARS = 30  # also covers ja and zh, which have no spaces to count


def unwrap_all(unwanted: List["re.Match[str]"], want: List[str]) -> Optional[List[str]]:
    """
    What the extra spans become with their backticks removed; None if they can't be: one
    repeats a span of msgid (unclear which copy is the model's), is long (see above), or
    has a backtick inside (it would be left stray).
    """
    words = [unwrapped(m.group(0)) for m in unwanted]
    if any(m.group(0) in want for m in unwanted):
        return None
    if any(
        "`" in w or len(w.split()) > MAX_UNWRAP_WORDS or len(w) > MAX_UNWRAP_CHARS for w in words
    ):
        return None
    return words


def repair_code_spans(msgid: str, text: str) -> Tuple[str, List[str]]:
    """
    Undo code spans the model damaged. A span it quoted instead of backticking is backticked
    again (when unambiguous). Then, if the spans are as many as msgid's, each span that
    msgid does not have is replaced by one that text lacks, in order of appearance. If text
    has more spans and lacks none, the extra ones lose their backticks (the model backticked
    a word: 'the `cabecera` header'; see unwrap_all for the limits). The repair is
    dropped unless the spans then equal msgid's exactly. Returns the text and the spans put
    back by position; with several, the mapping is only a guess from the order (the
    language may reorder them).
    """
    if msgid.count("`") % 2:  # code_span_rule gives no verdict
        return text, []
    want = [m.group(0) for m in code_spans(msgid)]
    if not want or Counter(m.group(0) for m in code_spans(text)) == Counter(want):
        return text, []
    fixed = text
    for span, count in (Counter(want) - Counter(m.group(0) for m in code_spans(text))).items():
        fixed = requote(fixed, span, count)
    got = code_spans(fixed)
    if len(got) < len(want):  # cheap early exit; the final check would catch it
        return text, []
    unwanted, kept = [], Counter(want)
    for match in got:
        if kept[match.group(0)]:
            kept[match.group(0)] -= 1
        else:
            unwanted.append(match)
    lacking, have = [], Counter(m.group(0) for m in got)
    for span in want:
        if have[span]:
            have[span] -= 1
        else:
            lacking.append(span)
    if len(got) > len(want):
        replacements = unwrap_all(unwanted, want)
    elif any(PLACEHOLDER_RE.search(span) for span in lacking):  # placeholders: BAD_VARIABLE's
        replacements = None
    else:
        replacements = lacking
    if replacements is None:
        return text, []
    for match, span in reversed(list(zip(unwanted, replacements))):
        fixed = fixed[: match.start()] + span + fixed[match.end() :]
    if Counter(m.group(0) for m in code_spans(fixed)) != Counter(want):
        return text, []
    return fixed, lacking


def restored_problem(spans: List[str]) -> str:
    """The advisory problem for several code spans put back by position (see above)."""
    listed = ", ".join(named(s) for s in spans[:MAX_LISTED])
    return (
        f"CODE_SPANS_RESTORED code spans were restored by position; check the order. "
        f"Keep {listed} exactly as written"
    )


def shorten(text: str) -> str:
    """One line of at most MAX_ERROR characters (errors can echo model output)."""
    parts, pos = [], 0
    for match in CODE_RE.finditer(text):  # code spans are named verbatim in errors
        parts.append(re.sub(r"\s+", " ", text[pos : match.start()]))
        parts.append(match.group(0))
        pos = match.end()
    parts.append(re.sub(r"\s+", " ", text[pos:]))
    text = "".join(parts).strip()
    return text if len(text) <= MAX_ERROR else text[: MAX_ERROR - 3] + "..."


def build_prompt(
    lang: str,
    masked: str,
    tokens: bool,
    error: Optional[str],
    mark: str = MARK,
    visible: bool = False,
    percent: bool = False,
    hint: str = "",
) -> str:
    start = PROMPT_START.format(lang=lang)
    if tokens:
        start += TOKEN_SENTENCE.format(token=f"{mark}1{mark}")
    if visible:
        start += VISIBLE_SENTENCE_PERCENT if percent else VISIBLE_SENTENCE
    start += hint
    if error:
        start += f" Your previous translation was rejected: {shorten(error)}."
    return start + PROMPT_END.format(text=masked)


# A rule takes (msgid, msgstr, lang) and returns short error strings, which go into
# the retry prompt. The retry loop doesn't depend on which rules exist.
Rule = Callable[[str, str, Optional[str]], List[str]]
_CHECKER = CatalogChecker()


def i18n_check_rule(msgid: str, msgstr: str, lang: Optional[str]) -> List[str]:
    """The `make i18n-check` checks: variables, syntax, links, tokens, length, ..."""
    return [
        f"{i.issue_type.name} {i.details}".strip().replace("\n", " ")
        for i in _CHECKER.check_pair(msgid, msgstr, lang)
    ]


def named(span: str) -> str:
    """A span for an error message; a very long one is cut, keeping its backticks."""
    if len(span) <= MAX_SPAN:
        return span
    ticks = span[: len(span) - len(span.lstrip("`"))]
    return span[: MAX_SPAN - len(ticks) - 3] + "..." + ticks


def text_kept(span: str, msgstr: str) -> bool:
    """The text inside span is in msgstr, as a whole word, outside any code span."""
    inner = span.strip("`").strip()
    if not inner:
        return False
    before = r"(?<![A-Za-z0-9])" if inner[0].isalnum() else ""
    after = r"(?![A-Za-z0-9])" if inner[-1].isalnum() else ""
    return bool(re.search(before + re.escape(inner) + after, CODE_RE.sub(" ", msgstr)))


def code_span_rule(msgid: str, msgstr: str, lang: Optional[str]) -> List[str]:
    """
    Every backtick span of msgid must be in msgstr, byte for byte (multisets; order is
    free). A span whose text changed or went missing is a hard failure (CODE_SPAN_CHANGED);
    one that kept its text but lost its backticks, or an added span, is advisory.
    Placeholders are checked by BAD_VARIABLE in i18n_check_rule. An odd number of
    backticks in msgid means the spans can't be paired reliably, so there is no verdict.
    """
    if msgid.count("`") % 2:
        return []
    want = Counter(m.group(0) for m in CODE_RE.finditer(msgid))
    got = Counter(m.group(0) for m in CODE_RE.finditer(msgstr))
    errors = []
    for span in list(want - got)[:3]:
        kind = "CODE_SPAN_BACKTICKS" if text_kept(span, msgstr) else "CODE_SPAN_CHANGED"
        errors.append(f"{kind} keep {named(span)} exactly, including the backticks")
    if not errors:
        errors = [
            f"CODE_SPAN_ADDED you added {named(span)}: don't add backticks"
            for span in list(got - want)[:3]
        ]
    return errors


RULES: List[Rule] = [code_span_rule, i18n_check_rule]


def match_whitespace(msgid: str, msgstr: str, lang: Optional[str] = None) -> str:
    """Give msgstr the leading and trailing whitespace of msgid; unwrap ja/zh lines."""
    lead = msgid[: len(msgid) - len(msgid.lstrip())]
    trail = msgid[len(msgid.rstrip()) :]
    return lead + collapse_cjk_breaks(msgstr.strip(), lang) + trail


FENCE_LINE_RE = re.compile(r"`{3,}[ \t]*[\w+-]*")  # a code fence line, with an info string


def drop_added_backticks(msgid: str, msgstr: str) -> str:
    """
    A msgid without backticks is plain text (notes name header fields bare), so any
    backtick in msgstr was added by the model; remove it and keep the text inside. A
    leading or trailing code fence line goes first, with its info string ('```text').
    """
    if "`" in msgid:
        return msgstr
    lines = msgstr.strip().split("\n")
    if FENCE_LINE_RE.fullmatch(lines[0].strip()):
        lines = lines[1:]
    if lines and FENCE_LINE_RE.fullmatch(lines[-1].strip()):
        lines = lines[:-1]
    return "\n".join(lines).replace("`", "")


@dataclass
class Result:
    text: Optional[str]  # None: nothing usable
    retries: int = 0
    error: str = ""  # why the last attempt failed
    fuzzy: bool = False  # text failed only advisory checks; keep it for review


def translate(
    ask: Callable[[str], str],
    lang: str,
    msgid: str,
    rules: Optional[List[Rule]] = None,
    mode: str = DEFAULT_PROTECT,
) -> Result:
    """
    Translate msgid with protected spans masked (see PROTECT_*), validating the result with
    the rules and retrying up to RETRIES times. If the last attempt fails only advisory rules,
    its text is returned with fuzzy set; any other failure returns no text.
    """
    mark = pick_mark(msgid)
    masked, spans = prompt_text(msgid, mark, mode)
    visible = mode != PROTECT_ALL and bool(VISIBLE_RE.search(masked))
    percent = visible and "%%" in masked
    hint = glossary_hint(lang, msgid) + strength_hint(lang, msgid)
    error = ""
    candidate: Optional[str] = None
    advisory = False
    for attempt in range(RETRIES + 1):
        candidate, advisory = None, False
        raw = drop_added_backticks(
            msgid,
            ask(
                build_prompt(lang, masked, bool(spans), error or None, mark, visible, percent, hint)
            ),
        ).strip()
        if not raw:
            error = "the translation was empty"
            continue
        error = token_error(masked, raw, len(spans), mark, mode == PROTECT_ALL) or ""
        if error:
            continue
        repaired, renamed = repair_placeholders(msgid, restore(raw, spans, mark))
        repaired, put_back = repair_code_spans(msgid, repaired)
        text = match_whitespace(msgid, repaired, lang)
        problems = [
            p for rule in (RULES if rules is None else rules) for p in rule(msgid, text, lang)
        ]
        if len(renamed) > 1:  # one rename is unambiguous; several are mapped by order only
            problems.append(renamed_problem(renamed))
        # likewise for code spans, and a restored span whose text is also in the reply bare
        # may not be the model's rewrite of it
        if len(set(put_back)) > 1 or any(text_kept(span, repaired) for span in put_back):
            problems.append(restored_problem(put_back))
        if not problems:
            return Result(text, attempt)
        hard = [p for p in problems if p.startswith(HARD_PREFIXES)]
        error = shorten("; ".join(hard or problems))  # advisory noise would crowd out the cause
        candidate = text
        advisory = not hard
    if candidate is not None and advisory:
        return Result(candidate, RETRIES, error, fuzzy=True)
    return Result(None, RETRIES, shorten(error))


def supports_option(model: Any, name: str) -> bool:
    options = getattr(model, "Options", None)
    return name in getattr(options, "model_fields", {})


def autotranslate_file(
    po_file,
    lang,
    model_id,
    rpm,
    temperature=DEFAULT_TEMPERATURE,
    model=None,
    protect_mode=DEFAULT_PROTECT,
):
    catalog = load_catalog(po_file)
    if model is None:
        import llm  # pylint: disable=import-outside-toplevel

        model = llm.get_model(model_id)
    options = {}
    if supports_option(model, "temperature"):
        options["temperature"] = temperature
    else:
        print(f"{model_id} has no temperature option; using its default.")

    def ask(prompt: str) -> str:
        return model.prompt(prompt, **options).text()

    # Identify messages that need translation (empty or fuzzy)
    needed = [m for m in catalog if m.id and (not m.string or "fuzzy" in m.flags)]
    to_translate = [m for m in needed if isinstance(m.id, str)]
    if len(needed) > len(to_translate):
        print(
            f"Skipping {len(needed) - len(to_translate)} plural messages in {lang}; "
            "translate their forms by hand."
        )
    count = 0
    left_empty: List[Tuple[Any, str]] = []
    kept_fuzzy: List[Tuple[Any, str]] = []
    errors = []

    print(
        f"Found {len(to_translate)} messages to translate using {model_id} "
        f"(--protect {protect_mode})."
    )

    exception_count = 0
    sleep_time = 60.0 / rpm if rpm > 0 else 0

    for i, message in enumerate(to_translate):
        try:
            if i > 0 and sleep_time > 0:
                time.sleep(sleep_time)

            result = translate(ask, lang, message.id, mode=protect_mode)
            exception_count = 0

            if result.text and not result.fuzzy:
                message.string = result.text
                if "fuzzy" in message.flags:
                    message.flags.remove("fuzzy")
                count += 1
                sys.stdout.write(".")
            elif result.text:
                message.string = result.text
                message.flags.add("fuzzy")
                kept_fuzzy.append((message.id, result.error))
                sys.stdout.write("?")
            else:
                message.string = ""
                message.flags.discard("fuzzy")
                left_empty.append((message.id, result.error))
                sys.stdout.write("x")
        except KeyboardInterrupt:
            print("\n\nAborting: User interrupted.")
            save_catalog(po_file, catalog)
            sys.exit(1)
        except Exception as e:  # pylint: disable=broad-exception-caught
            exception_count += 1
            sys.stdout.write("E")

            error_msg = str(e)
            if exception_count == 1:
                print(f"\n\nFirst exception encountered: {error_msg}")

            errors.append(f"Error: {error_msg} for {message.id[:40]}...")

            if exception_count >= 3:
                print("\n\nAborting: Too many exceptions encountered.")
                save_catalog(po_file, catalog)
                sys.exit(1)

        sys.stdout.flush()

    save_catalog(po_file, catalog)
    print(f"\nAuto-translated {count} messages.")

    for entries, what in (
        (left_empty, f"left empty (no valid translation; --protect {protect_mode})"),
        (kept_fuzzy, "kept as fuzzy for review (failed advisory checks)"),
    ):
        if entries:
            print(f"\n{len(entries)} entries {what}:")
            for msgid, error in entries:
                print(f"  - {' '.join(str(msgid).split())[:70]}\n      {error}")

    if errors:
        print(f"\nEncountered {len(errors)} errors:")
        # Print first few errors to avoid spamming
        for err in errors[:10]:
            print(f"  - {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Auto-translate missing strings")
    parser.add_argument("--po_file", help="Path to a single PO file")
    parser.add_argument("--locale_dir", help="Path to locale directory (process all locales)")
    parser.add_argument("--lang", help="Target language code (required for single file)")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="LLM model to use (default: %(default)s)",
    )
    parser.add_argument(
        "--rpm",
        type=int,
        default=0,
        help="Requests per minute (default: 0; 0 or less: unlimited)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_TEMPERATURE,
        help="Sampling temperature, if the model supports it (default: %(default)s)",
    )
    parser.add_argument(
        "--protect",
        choices=PROTECT_MODES,
        default=DEFAULT_PROTECT,
        help="Text hidden from the model: 'names' (URLs, link targets, field and coding "
        "names; names in a text without backticks are wrapped in backticks instead), "
        "'links' (URLs and link targets only) or 'all' (everything, code spans and "
        "placeholders too; it dropped tokens in 5%% of ja entries). Code spans and "
        "placeholders left visible are verified afterwards (default: %(default)s)",
    )
    return parser


def main():
    args = build_parser().parse_args()

    if args.locale_dir:
        po_files = find_po_files(args.locale_dir)
        if not po_files:
            print(f"No PO files found in {args.locale_dir}")
            sys.exit(0)
        for po_file in po_files:
            lang = get_lang_from_path(po_file)
            if not lang:
                print(f"Could not determine language for {po_file}, skipping.")
                continue
            print(f"Processing {lang} ({po_file})...")
            autotranslate_file(
                po_file, lang, args.model, args.rpm, args.temperature, protect_mode=args.protect
            )
    elif args.po_file:
        if not args.lang:
            print("Error: --lang is required for single file autotranslate")
            sys.exit(1)
        autotranslate_file(
            args.po_file,
            args.lang,
            args.model,
            args.rpm,
            args.temperature,
            protect_mode=args.protect,
        )
    else:
        print("Error: Either --po_file or --locale_dir must be specified.")
        sys.exit(1)


if __name__ == "__main__":
    main()
