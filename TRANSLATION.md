# Translation

This document outlines the process for adding and updating translations in `redbot`.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Guidelines for Translators](#guidelines-for-translators)
- [Guidelines for Code](#guidelines-for-code)
- [Release checklist](#release-checklist)
- [Reviewing translations](#reviewing-translations)
  - [Offline checks](#offline-checks)
  - [Model review](#model-review)
- [Adding a New Language](#adding-a-new-language)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->


## Guidelines for Translators

Suggestions and corrections for the translations in `redbot/translations` are welcome as GitHub Pull Requests. A few guidelines for doing so:

* Assume a technical audience, but prioritise clarity, accuracy, and brevity. Do not assume deep domain-specific knowledge about HTTP.
* Keep "%(foo)s" style variables in your content.
* Line endings are not important.

In your PR, please do not modify any file except for the .po. Making multiple suggestions in the same PR is fine.

Note that many of REDbot's messages come from the [httplint library](https://github.com/mnot/httplint/blob/main/TRANSLATION.md), which takes i18n PRs too.

## Guidelines for Code

Code that contains user-facing strings should follow these guidelines:

*   **Note Classes**: Strings assigned to `_summary` and `_text` in `Note` and `RedbotNote` subclasses are automatically extracted.
*   **Other Strings**: For other strings (e.g., class attributes, global constants), use the `_` lazy translation marker from `redbot.i18n`.
    ```python
    from redbot.i18n import _

    MY_STRING = _("This is a translatable string")
    ```
    Ensure these strings are passed to `get_translator().ugettext()` (from `redbot.i18n`) or used in a context that handles lazy translation before being displayed.
*   **Plurals**: Use `ngettext` from `redbot.i18n` for strings that have singular and plural forms.
    ```python
    from redbot.i18n import ngettext

    msg = ngettext("%(num)s item", "%(num)s items", count) % {"num": count}
    ```
    The tools don't translate plural entries: `make i18n-autotranslate` skips them and `make i18n-check MARK_FUZZY=1` doesn't mark them. Fill in every `msgstr[n]` by hand (the `Plural-Forms` header of each `.po` says how many: two for `fr` and `es`, one for `ja` and `zh`), then run `make i18n-check`.

## Release checklist

Run this when translatable strings have changed.

1. `make i18n-update`: re-extracts the strings and updates every catalog. Changed strings arrive as new, empty entries (no fuzzy matching); the old translation is kept as an obsolete `#~` entry.
2. `make i18n-check MARK_FUZZY=1`: marks entries the checks flag as `fuzzy`, so that step 4 retranslates them. Step 4 **discards the text** of those entries. This step can report FAILED if there are critical errors, even though the marking was saved; carry on.
3. Download the default model, once (Apple silicon only; other models work via `llm` plugins): `./.venv/bin/llm mlx download-model mlx-community/aya-expanse-8b-4bit`
4. `make i18n-autotranslate`: translates every empty or `fuzzy` entry with an LLM (via the `llm` package).
   * `MODEL=<model id>` chooses another model; remote models need API keys (e.g., `./.venv/bin/llm keys set gemini`).
   * `RPM=<n>` limits requests per minute (default: unlimited); use it with remote models that rate-limit.
   * `TEMPERATURE=<x>` sets the sampling temperature (default 0.2) if the model supports it.
   * `PROTECT=<mode>` chooses what the model cannot see. The default, `names`, hides URLs and link targets, and keeps the field and coding names (`Content-Length`, `gzip`) from being translated: in a text without backticks the model sees them in backticks (stripped from its reply), elsewhere they are hidden; code spans and variables stay visible and are checked afterwards. `links` hides only URLs and link targets; `all` also hides code spans and variables (some models dropped tokens, in 5% of Japanese entries).
   * Each result is checked as in `i18n-check` and retried twice if it fails. A single variable the model renamed (`%(field_name)s` translated) is put back first; several renamed ones are mapped by position and kept as `fuzzy` for review. Likewise, code spans whose text the model changed or swapped for quotes are put back (when the span count matches); several changed ones are mapped by position and kept as `fuzzy`. Backticks the model added around a short word (at most 3 words, 30 characters) are removed when the msgid's own spans are all present. For French, Spanish, Japanese and Simplified Chinese, the prompt also says how to translate 'should' and 'must' (`STRENGTH_HINTS` in `tools/i18n/glossary.py`).
   * Entries that still fail on variables, code spans, field names or syntax are left empty; entries that only trip the advisory checks are kept as `fuzzy`. Both are listed at the end.
5. `make i18n-check`: there must be no critical errors. Read any remaining flags and fix them by hand in the `.po` files.
6. Optional: `make i18n-review MODEL=<model id> LOCALE=fr SINCE=origin/main` (see [Reviewing translations](#reviewing-translations)).
7. `make i18n-compile`: builds the `.mo` files used at runtime.
8. Spot-check: run `make server` and visit it with your browser's language set to the new locale.
9. Commit the result as its own PR.

To translate by hand instead of step 4, edit the `.po` files (e.g., `redbot/translations/fr/LC_MESSAGES/messages.po`). `make i18n-clear-fuzzy` blanks entries already marked `fuzzy` (every form, for a plural entry) and **discards their text**, for translating them by hand.

## Reviewing translations

Machine translations need checking, and most maintainers cannot read every language. Both layers below are advisory.

### Offline checks

`make i18n-check` (part of `make test`) fails only on `BAD_VARIABLE` and `SYNTAX_ERROR`. It also reports, without failing:

* `MISSING`, `FUZZY`: no translation, or marked fuzzy.
* `LINK_MISMATCH`: URLs, Markdown link targets or the number of well-formed `[text](target)` links differ from the English.
* `TOKEN_CHANGED`: a backtick-quoted header name, token or value in the English does not appear verbatim in the translation.
* `DUPLICATED_TEXT`: sentences or placeholders repeat more than in the English (exact repeats only).
* `SUSPICIOUS_LENGTH`: the translation is much shorter or longer than the English.
* `PREAMBLE`: the translation starts or ends with model chatter, a code fence or a refusal, or contains `<think>` tags.
* `FIELD_NAME_CHANGED`, `GLOSSARY`, `GLOSSARY_LOW`, `STRENGTH`, `LEFTOVER_ENGLISH`, `PUNCTUATION`, `BACKTICKS_ADDED`, `STRUCTURE`: language rules (field and coding names kept as written, preferred terms, must/should strength, a leading "The", final punctuation, backticks in a translation of a string that has none, paragraphs and line breaks).

About the language rules:

* `i18n-autotranslate` applies them too. A changed field name is retried and then left empty; the others only leave the entry `fuzzy`.
* `MARK_FUZZY=1` does not mark entries flagged only by `GLOSSARY_LOW` (low-confidence terms).
* Edit the per-language terms in `tools/i18n/glossary.py`.

An untranslated string identical to the English is not flagged. A flag means "look at this", not "this is wrong".

### Model review

`make i18n-review` asks a language model to judge each translation. It is not part of `make test`, and there is no default model.

```bash
# Claude (needs an API key; this costs money)
./.venv/bin/llm install llm-anthropic
./.venv/bin/llm keys set anthropic
./.venv/bin/llm models                      # find the model id
make i18n-review MODEL=<model id> LOCALE=fr SINCE=origin/main
```

A local MLX model should also work through `llm-mlx` (installed by `make venv-i18n`), with no key and no per-call cost; this has not been tested.

Options (as `make` variables):

* `LOCALE`: a locale such as `fr`, or `all` (the default).
* `SINCE=REF`: only review entries whose translation is new or changed since git ref `REF`.
* `LIMIT=N`: review at most N entries per locale.
* `YES=1`: required if more than 50 model calls could be made (worst case: entries x (1 + `BACKTRANSLATE`) x 2, because an invalid reply is retried once).
* `BACKTRANSLATE=1`: translate each translation back to English first, then compare meanings. Doubles the calls.
* `MARK_FUZZY=1`: mark entries judged "major" as `fuzzy`, so `make i18n-compile` skips them. `make i18n-autotranslate` and `make i18n-clear-fuzzy` **discard the msgstr** of fuzzy entries, and with it the reviewer's suggestion (suggestions live only in the report), so copy what you want first. Leave this off unless you will read the report.
* `DRY_RUN=1`: show what would be reviewed and the number of calls; needs no `MODEL`.

The report is `i18n-review-<locale>.md` in the current directory (git-ignored), major problems first, and is rewritten after every entry. The review never changes a translation; apply suggestions by hand in the `.po` file.

Every reviewed string and its translation is sent to the model's provider, so check that this is acceptable and use `DRY_RUN`, `SINCE` and `LIMIT` to limit calls. Treat the verdicts as a second opinion, not a gate.

## Adding a New Language

To add a new language (e.g., German `de`):

```bash
make i18n-init LOCALE=de
```

This builds from the committed `messages.pot`, so run `make i18n-update` first. Then follow steps 3-9 of the [release checklist](#release-checklist). Once the language is ready:

1. Update the `httplint` dependency in `pyproject.toml` to a version that supports that language.
2. Update `redbot/i18n.py` to list the language in `AVAILABLE_LOCALES`.
