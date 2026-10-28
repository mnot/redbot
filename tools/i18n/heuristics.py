"""
Cheap, offline, report-only checks on a (msgid, msgstr) pair.

Each function returns a human-readable problem description, or None if the pair looks
fine. They are heuristics: they miss things, and they can flag good translations, so
callers must treat the results as advisory.
"""

import re
from collections import Counter
from typing import Dict, List, Optional, Set, Tuple

PLACEHOLDER_RE = re.compile(r"%\([^)]+\)[-#0 +]*[\d\.]*[diouxXeEfFgGcrsa]")


def _lang_base(lang: Optional[str]) -> str:
    """'zh_Hans' / 'zh-TW' -> 'zh'."""
    if not lang:
        return ""
    return re.split(r"[_\-@.]", lang)[0].lower()


## LINK_MISMATCH

URL_RE = re.compile(r"""https?://[^\s<>"'`)\]]+""")
MD_TARGET_RE = re.compile(r"\]\(\s*<?((?:%\([^)]*\)s|[^)\s>])+)")


def _link_targets(text: str) -> Set[str]:
    found = set(URL_RE.findall(text))
    found.update(MD_TARGET_RE.findall(text))
    return {t.rstrip(".,;:!?") for t in found}


# A well-formed inline link: [text](target), no space between ']' and '('.
MD_LINK_RE = re.compile(r"\[[^\]]*\]\(\s*<?(?:%\([^)]*\)s|[^)\s>])+[^)]*\)")
SPACED_LINK_RE = re.compile(r"\]\s+\(")


def link_mismatch(msgid: str, msgstr: str) -> Optional[str]:
    """
    The links in msgstr should match those in msgid.

    Compares (1) the set of URLs and Markdown link targets, and (2) the number of
    well-formed `[text](target)` links, so that a link that kept its URL but lost its
    brackets, closing parenthesis, or got a space before the `(` is caught too.
    """
    problems = []
    want = _link_targets(msgid)
    got = _link_targets(msgstr)
    if want - got:
        problems.append(f"missing: {', '.join(sorted(want - got))}")
    if got - want:
        problems.append(f"extra: {', '.join(sorted(got - want))}")
    if SPACED_LINK_RE.search(msgstr) and not SPACED_LINK_RE.search(msgid):
        problems.append("space between ']' and '(' breaks a Markdown link")
    want_links = len(MD_LINK_RE.findall(msgid))
    got_links = len(MD_LINK_RE.findall(msgstr))
    if want_links != got_links:
        problems.append(f"{got_links} well-formed Markdown links, msgid has {want_links}")
    return "; ".join(problems) or None


## TOKEN_CHANGED

BACKTICK_RE = re.compile(r"`([^`\n]+)`")
# A span with no whitespace made only of characters legal in a token, a quoted
# string, or a field value.
SINGLE_TOKEN_RE = re.compile(r"""[A-Za-z0-9!#$&'*+.^|~/=:;,"()<>_\-\\]+""")
# 'Cache-Control: max-age', 'Vary *', 'Expect: 100-continue'
FIELD_LINE_RE = re.compile(
    r"""[A-Za-z][A-Za-z0-9\-]*(?::\s?|\s)[A-Za-z0-9!#$&'*+.^|~/=:;,"()<>_\-]+"""
)
STATUS_SPAN_RE = re.compile(r"(\d{3}) \(")


def _http_tokens(msgid: str) -> List[str]:
    """
    Backtick-quoted spans in msgid that look like HTTP syntax, reduced to the part that
    must survive translation unchanged.

    Conservative on purpose: a span is considered only if it is short and either one
    whitespace-free token, a 'Name: value' field line, or a status code with its reason
    phrase (only the code is required to survive; reason phrases are descriptive).
    Spans with placeholders are left to the BAD_VARIABLE check, and spans that look
    like prose (the usual sign of mis-paired backticks) are ignored.
    """
    tokens: List[str] = []
    for span in BACKTICK_RE.findall(msgid):
        if len(span) > 60 or "%(" in span:
            continue
        status = STATUS_SPAN_RE.match(span)
        if status:
            tokens.append(status.group(1))
            continue
        candidate = span.strip()
        if not candidate or candidate != span.strip(" "):
            continue
        if SINGLE_TOKEN_RE.fullmatch(candidate) or FIELD_LINE_RE.fullmatch(candidate):
            if not any(ch.isalnum() for ch in candidate):
                continue  # bare punctuation: '*', '=', '/'
            tokens.append(candidate)
    return tokens


def token_changed(msgid: str, msgstr: str) -> Optional[str]:
    """
    Each HTTP-looking backtick span of msgid must appear verbatim (case-sensitive,
    backticks not required) somewhere in msgstr.
    """
    missing = []
    for token in _http_tokens(msgid):
        if token not in msgstr and token not in missing:
            missing.append(token)
    if not missing:
        return None
    return "not found in translation: " + ", ".join(f"`{t}`" for t in missing)


## DUPLICATED_TEXT

SEGMENT_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+|(?<=[。！？；])|\n+")
MIN_SEGMENT_WEIGHT = 12  # letters; a CJK character counts as two
CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff\uac00-\ud7af]")


def _segments(text: str) -> List[str]:
    out = []
    for raw in SEGMENT_SPLIT_RE.split(text):
        seg = PLACEHOLDER_RE.sub("§", raw)
        seg = re.sub(r"^[\s*\-#>]+", "", seg)
        seg = re.sub(r"[\W_]+", " ", seg, flags=re.UNICODE).strip().casefold()
        weight = sum((2 if CJK_RE.match(ch) else 1) for ch in seg if ch.isalpha())
        if weight >= MIN_SEGMENT_WEIGHT:
            out.append(seg)
    return out


def _repeated_segments(text: str) -> Set[str]:
    return {s for s, n in Counter(_segments(text)).items() if n > 1}


def duplicated_text(msgid: str, msgstr: str) -> Optional[str]:
    """
    msgstr repeats text that msgid does not.

    Two signals:
    1. msgstr has more distinct repeated sentences than msgid. A sentence is a segment
       of at least 12 letters (a CJK character counts as two), compared ignoring
       placeholders, case and punctuation. Only exact repeats count: a paraphrased
       restatement (seen in zh) is not detected.
    2. A placeholder occurs more times in msgstr than in msgid. It needs the
       placeholder to be in msgid at least once.
    """
    problems = []
    again = sorted(_repeated_segments(msgstr))
    if len(again) > len(_repeated_segments(msgid)):
        problems.append("repeated sentence: " + "; ".join(again[:2]))
    want = Counter(PLACEHOLDER_RE.findall(msgid))
    got = Counter(PLACEHOLDER_RE.findall(msgstr))
    extra = sorted(name for name, n in got.items() if n > want.get(name, 0) > 0)
    if extra:
        problems.append("placeholder repeated more often than in msgid: " + ", ".join(extra))
    return "; ".join(problems) or None


## SUSPICIOUS_LENGTH

# Acceptable len(msgstr) / len(msgid). Observed on the shipped catalogs: Latin-script
# languages 0.85-1.45 (1st-99th percentile), ja 0.4-1.0, zh 0.2-0.8.
DEFAULT_LENGTH_RANGE: Tuple[float, float] = (0.5, 2.2)
LENGTH_RANGES: Dict[str, Tuple[float, float]] = {
    "ja": (0.2, 1.4),
    "zh": (0.12, 1.2),
    "ko": (0.2, 1.4),
}
MIN_LENGTH_CHECKED = 30  # shorter msgids have too noisy a ratio


def suspicious_length(msgid: str, msgstr: str, lang: Optional[str]) -> Optional[str]:
    """len(msgstr) / len(msgid) outside the range for the language."""
    if len(msgid) < MIN_LENGTH_CHECKED:
        return None
    low, high = LENGTH_RANGES.get(_lang_base(lang), DEFAULT_LENGTH_RANGE)
    ratio = len(msgstr) / len(msgid)
    if low <= ratio <= high:
        return None
    return f"length ratio {ratio:.2f} (expected {low}-{high})"


## PREAMBLE

PREAMBLE_RE = re.compile(
    r"""^\s*(?:
        here(?:\s+is|'s)\b | sure\b | certainly\b | of\scourse\b | okay\b |
        translat(?:ion|ed)\b\s*(?:text|result|version)?\s*[:：] |
        the\s+translation\b | as\s+an\s+ai\b | i\s+(?:cannot|can't|can\snot)\b |
        i'm\s+(?:sorry|unable)\b | i\s+am\s+(?:sorry|unable)\b |
        voici\b | traduction\s*[:：] | bien\s+s[uû]r\b | certainement\b |
        en\s+tant\s+qu'ia\b | je\s+suis\s+d[ée]sol[ée]\b | d[ée]sol[ée]\b |
        je\s+ne\s+peux\s+pas\b |
        aqu[ií]\s+(?:est[aá]|tiene)\b | traducci[oó]n\s*[:：] | claro\b |
        por\s+supuesto\b | como\s+ia\b | lo\s+siento\b | no\s+puedo\b |
        以下は | 以下是 | 翻訳\s*[:：] | 翻译\s*[:：] | 译文\s*[:：] | 好的 | 当然 |
        もちろん | 申し訳 | 抱歉 | 对不起 | 作为(?:一个)?\s*ai |
        ```
    )""",
    re.IGNORECASE | re.VERBOSE,
)
# Chatter after the translation: "(Note: ...)", "Let me know if ...", "I hope this helps".
TRAILER_RE = re.compile(
    r"""(?:^|\n)\s*\(?(?:note|nota|remarque)\s*:
        | let\s+me\s+know\b | hope\s+this\s+helps
        | n'hésitez\s+pas | j'espère\s+que\s+cela
        | espero\s+que\s+(?:esto|te)
        | 如果您需要 | 希望这对 | ご不明な点 | 何かあれば""",
    re.IGNORECASE | re.VERBOSE,
)
THINK_RE = re.compile(r"</?think(?:ing)?>", re.IGNORECASE)


def preamble(msgid: str, msgstr: str) -> Optional[str]:
    """
    msgstr opens with model chatter (a greeting, an acknowledgement, a refusal), a
    code fence, or ends with commentary; or it contains <think> tags. Patterns that
    also match msgid are ignored, so a string that genuinely begins "Note:" is fine.
    """
    if THINK_RE.search(msgstr) and not THINK_RE.search(msgid):
        return "contains <think> tags"
    if PREAMBLE_RE.match(msgstr) and not PREAMBLE_RE.match(msgid):
        return f"starts with chatter: {msgstr.strip()[:40]!r}"
    trailer = TRAILER_RE.search(msgstr)
    if trailer and not TRAILER_RE.search(msgid) and "note" not in msgid.casefold():
        return f"commentary after the translation: {trailer.group(0).strip()!r}"
    return None
