"""
Language rules on a (msgid, msgstr) pair, shared by i18n-check (report-only) and
autotranslate (retries). Like heuristics.py, each function returns a problem
description or None. The terminology data is in glossary.py.
"""

import functools
import importlib
import inspect
import pkgutil
import re
from typing import List, Optional, Tuple

from .glossary import GLOSSARY, STRENGTH, STRENGTH_HINTS, Entry
from .heuristics import _lang_base

MAX_LISTED = 3  # problems named in one message

CODE_RE = re.compile(r"(`+)(?:(?!\n[ \t]*\n).)+?\1(?!`)", re.DOTALL)
# What isn't prose: placeholders, Markdown link targets, bare URLs.
OPAQUE_RE = re.compile(
    r"""%\([^)]*\)[-\#0\ +]*[\d.]*[a-zA-Z]|%%
    | (?<=\])\((?:[^()\s]|\([^()\s]*\))+\)
    | https?://[^\s<>"'`)\]]+""",
    re.VERBOSE,
)


def prose(text: str, code: bool = True) -> str:
    """text without placeholders and links, and (code=True) without code spans."""
    text = OPAQUE_RE.sub(" ", text)
    return CODE_RE.sub(" ", text) if code else text


## FIELD_NAME_CHANGED

# Content-coding names the model transliterates (ブロトリ, デフラグ圧縮). 'compress' and
# 'identity' are ordinary words; they are only protected inside backticks.
CODING_NAMES = ("gzip", "deflate", "brotli", "zstd", "dcb", "dcz")


@functools.lru_cache(maxsize=1)
def field_names() -> Tuple[str, ...]:
    """The canonical field names of the parsers, longest first."""
    from httplint.field import HttpField  # pylint: disable=import-outside-toplevel
    import httplint.field.parsers as parsers  # pylint: disable=import-outside-toplevel

    names = set()
    for info in pkgutil.iter_modules(parsers.__path__):
        module = importlib.import_module(f"{parsers.__name__}.{info.name}")
        for _, cls in inspect.getmembers(module, inspect.isclass):
            name = cls.__dict__.get("canonical_name")
            if issubclass(cls, HttpField) and cls.__module__ == module.__name__ and name:
                names.add(name)
    return tuple(sorted(names, key=lambda n: (-len(n), n)))


@functools.lru_cache(maxsize=1)
def _name_regexes() -> Tuple["re.Pattern[str]", "re.Pattern[str]"]:
    """(hyphenated names, single-word names), as regexes with the name in group 1."""
    hyphenated = [re.escape(n) for n in field_names() if "-" in n]
    single = [re.escape(n) for n in field_names() if "-" not in n]
    edge = r"(?<![\w-])(%s)(?![\w-])"
    codings = r"(?<![\w-])(%s)(?!\w)" % "|".join(CODING_NAMES)
    return (
        re.compile(edge % "|".join(hyphenated) + "|" + codings, re.IGNORECASE),
        # a capitalised word is a field name only when called a header or field
        re.compile((edge % "|".join(single)) + r"`?\s+(?:headers?|fields?)\b"),
    )


LABEL_RE = re.compile(r"`?\s+(?:headers?|fields?)\b")


def names_in(msgid: str) -> List[str]:
    """
    Field names in msgid, as spelled there, in order of appearance. An all-lowercase
    spelling ('report-to parameter', 'brotli compression') counts only when it is
    followed by 'header' or 'field' (content-coding names are always names).
    """
    hyphenated, single = _name_regexes()
    text = prose(msgid, code=False)
    found = sorted(
        (m.start(m.lastindex or 0), m.group(m.lastindex or 0))
        for rx in (hyphenated, single)
        for m in rx.finditer(text)
        if m.group(m.lastindex or 0).lower() in CODING_NAMES
        or m.group(m.lastindex or 0) != m.group(m.lastindex or 0).lower()
        or LABEL_RE.match(text, m.end())
    )
    names: List[str] = []
    for _, name in found:
        if name not in names:
            names.append(name)
    return names


def name_pattern(name: str) -> str:
    """A regex for name as a whole token (not part of a longer name)."""
    after = (
        r"(?![A-Za-z0-9_])" if name.lower() in CODING_NAMES else r"(?![A-Za-z0-9_]|-[A-Za-z0-9])"
    )
    return rf"(?<![A-Za-z0-9_-]){re.escape(name)}{after}"


def has_name(name: str, msgstr: str) -> bool:
    """name is in msgstr as a whole token, in any case (not a prefix of a longer name)."""
    return bool(re.search(name_pattern(name), msgstr, re.IGNORECASE))


def field_name_changed(msgid: str, msgstr: str) -> Optional[str]:
    """Every field name in msgid, with or without backticks, is in msgstr as spelled."""
    missing = [n for n in names_in(msgid) if not has_name(n, msgstr)]
    if not missing:
        return None
    return "; ".join(
        f"keep the {'coding' if n.lower() in CODING_NAMES else 'field'} name `{n}` "
        "exactly as written"
        for n in missing[:MAX_LISTED]
    )


## GLOSSARY


SIMPLIFIED_ZH = ("zh", "zh_cn", "zh_sg", "zh_hans", "zh_hans_cn")


def locale_key(lang: Optional[str]) -> str:
    """The language the terms and words are for ('' for none): zh is Simplified Chinese only."""
    base = _lang_base(lang)
    if base == "zh" and (lang or "").lower().replace("-", "_") not in SIMPLIFIED_ZH:
        return ""
    return base


def untranslated(msgid: str, msgstr: str) -> bool:
    """msgstr is the English left as it was (not flagged by the language rules)."""
    return msgstr.strip() == msgid.strip()


def _applies(entry: Entry, english: str) -> bool:
    return bool(re.search(entry.when, english, re.IGNORECASE | re.DOTALL))


def glossary_hint(lang: Optional[str], msgid: str) -> str:
    """A prompt sentence for the glossary entries that apply to msgid ('' if none)."""
    english = prose(msgid)
    terms = [
        f"'{e.term}' as '{e.prefer}'"
        for e in GLOSSARY.get(locale_key(lang), ())
        if _applies(e, english)
    ]
    return f" Terminology: translate {'; '.join(terms)}." if terms else ""


def _glossary(msgid: str, msgstr: str, lang: Optional[str], low: bool) -> Optional[str]:
    if untranslated(msgid, msgstr):
        return None
    english, text = prose(msgid), prose(msgstr)
    problems = []
    for entry in GLOSSARY.get(locale_key(lang), ()):
        if entry.low != low or not _applies(entry, english):
            continue
        for pattern in entry.avoid:
            hit = re.search(pattern, text, re.IGNORECASE)
            if hit:
                problems.append(f"use '{entry.prefer}' for '{entry.term}', not '{hit.group(0)}'")
                break
    return "; ".join(problems[:MAX_LISTED]) or None


def glossary(msgid: str, msgstr: str, lang: Optional[str]) -> Optional[str]:
    """msgstr uses a term the glossary says to avoid for a term in msgid."""
    return _glossary(msgid, msgstr, lang, low=False)


def glossary_low(msgid: str, msgstr: str, lang: Optional[str]) -> Optional[str]:
    """As glossary(), for the low-confidence entries (reported, never marked fuzzy)."""
    return _glossary(msgid, msgstr, lang, low=True)


## STRENGTH

KEYWORD_RE = re.compile(r"\b(MUST|SHOULD)\b")  # in a translation: the English keyword


def _has(patterns: Tuple[str, ...], text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def strength(msgid: str, msgstr: str, lang: Optional[str]) -> Optional[str]:
    """
    'should' in msgid must not become a must-word in msgstr (unless a should-word is
    there too), nor 'must' a should-word alone. Only clear cases are flagged: a msgid
    with both words, or a msgstr with neither, gets no verdict. An English RFC 2119
    keyword left in msgstr is flagged too.
    """
    words = STRENGTH.get(locale_key(lang))
    if words is None or untranslated(msgid, msgstr):
        return None
    text, english = prose(msgstr), prose(msgid)
    leftover = KEYWORD_RE.search(text)
    if leftover:
        return f"RFC 2119 keyword '{leftover.group(0)}' left in English"
    should = re.search(r"\bshould\b", english, re.IGNORECASE)
    must = re.search(r"\bmust\b", english, re.IGNORECASE)
    musty, shouldy = _has(words[0], text), _has(words[1], text)
    if should and not must and musty and not shouldy:
        return "msgid says 'should' but the translation says 'must'"
    if must and not should and shouldy and not musty:
        return "msgid says 'must' but the translation says 'should'"
    return None


SHOULD_RE = re.compile(r"\bshould\b(?P<neg>\s+not\b)?", re.IGNORECASE)
MUST_RE = re.compile(r"\bmust\b(?P<neg>\s+not\b)?", re.IGNORECASE)
HINT_KEYS = ("should", "should not", "must", "must not")


def strength_words(msgid: str) -> List[str]:
    """The HINT_KEYS in msgid, found as strength() finds 'should' and 'must'."""
    english = prose(msgid)
    found = {
        f"{word} not" if m["neg"] else word
        for word, rx in (("should", SHOULD_RE), ("must", MUST_RE))
        for m in rx.finditer(english)
    }
    return [k for k in HINT_KEYS if k in found]


def strength_hint(lang: Optional[str], msgid: str) -> str:
    """A prompt sentence for the 'should' / 'must' wordings in msgid ('' if none)."""
    table = STRENGTH_HINTS.get(locale_key(lang))
    parts = []
    for key in strength_words(msgid) if table else ():
        use, avoid = table[key]
        parts.append(
            f"'{key}' as {' or '.join(repr(w) for w in use)}"
            + (f" (never '{avoid}')" if avoid else "")
        )
    return f" Strength: translate {'; '.join(parts)}." if parts else ""


def strength_hint_problems() -> List[str]:
    """Hint wordings that strength() would not read as the strength they are for (tested)."""
    problems = []
    for lang, table in STRENGTH_HINTS.items():
        musty, shouldy = STRENGTH[lang]
        for key, (use, avoid) in table.items():
            own, other = (musty, shouldy) if key.startswith("must") else (shouldy, musty)
            for word in use:
                if not _has(own, word) or _has(other, word):
                    problems.append(f"{lang} '{key}': '{word}' is not read as '{key.split()[0]}'")
            if avoid and not _has(other, avoid):
                problems.append(f"{lang} '{key}': avoided '{avoid}' is not the other strength")
    return problems


## LEFTOVER_ENGLISH, PUNCTUATION

SENTENCE_END_RE = re.compile(r"[.。!！?？:：…][\s\"'”’»)）」』\]]*$")


def leftover_english(msgid: str, msgstr: str, lang: Optional[str]) -> Optional[str]:
    """msgstr starts with the English article 'The' (a string left as is is not flagged)."""
    base = _lang_base(lang)
    if base in ("", "en") or not msgstr.startswith("The ") or msgstr.strip() == msgid.strip():
        return None
    return "starts with the English word 'The'"


def punctuation(msgid: str, msgstr: str, lang: Optional[str]) -> Optional[str]:
    """A msgid that ends a sentence with . ! or ? has a msgstr that ends with a sentence mark."""
    if _lang_base(lang) in ("", "en") or msgid.rstrip()[-1:] not in (".", "!", "?"):
        return None
    if SENTENCE_END_RE.search(msgstr.rstrip()):
        return None
    return f"msgid ends with '{msgid.rstrip()[-1]}' but the translation does not end a sentence"


## BACKTICKS_ADDED


def backticks_added(msgid: str, msgstr: str) -> Optional[str]:
    """msgstr has backticks but msgid has none (plain text: they would show literally)."""
    if "`" in msgid or "`" not in msgstr:
        return None
    return "msgid has no backticks, but the translation does"


## STRUCTURE

CJK_CHAR = "\u3000-\u303f\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff\uff00-\uffef"
CJK_BREAK_RE = re.compile(rf"(?<=[^\s{CJK_CHAR}])\n(?=[{CJK_CHAR}])|(?<=[{CJK_CHAR}])\n(?=\S)")
INDENT_RE = re.compile(r"^ {4}\S", re.MULTILINE)
LIST_START_RE = re.compile(r"[-*+>#|]|\d+[.)]|```")
# A line that is not a paragraph line: list item, heading, table row, link reference definition.
BLOCK_LINE_RE = re.compile(r"\s*(?:[-*+]\s|\d+[.)]\s|#{1,6}\s|\||\[[^\]]+\]:\s)")


def collapse_cjk_breaks(text: str, lang: Optional[str]) -> str:
    """
    Join the lines of a ja/zh paragraph that the model wrapped like the English (Markdown
    shows the break as a space). Text with a code block is left alone, as are lines that
    start or follow a list item, heading, table row or link reference definition.
    """
    if _lang_base(lang) not in ("ja", "zh") or "```" in text or INDENT_RE.search(text):
        return text

    def join(match: "re.Match[str]") -> str:
        rest = text[match.end() :]
        before = text[: match.start()].rsplit("\n", 1)[-1]
        if LIST_START_RE.match(rest) or BLOCK_LINE_RE.match(before) or not before.strip():
            return match.group(0)
        return ""

    return CJK_BREAK_RE.sub(join, text)


def paragraphs(text: str) -> int:
    return len([p for p in re.split(r"\n[ \t]*\n", text) if p.strip()])


def structure(msgid: str, msgstr: str, lang: Optional[str]) -> Optional[str]:
    """Paragraph count and indented code blocks match msgid; no hard breaks in CJK text."""
    problems = []
    if paragraphs(msgid) != paragraphs(msgstr):
        problems.append(f"{paragraphs(msgstr)} paragraphs, msgid has {paragraphs(msgid)}")
    if INDENT_RE.search(msgid) and not INDENT_RE.search(msgstr):
        problems.append("lost the 4-space indentation of a code block")
    if collapse_cjk_breaks(msgstr, lang) != msgstr:
        problems.append("single line break inside a paragraph")
    return "; ".join(problems) or None
