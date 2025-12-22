# Translation

This document outlines the process for adding and updating translations in `redbot`.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Guidelines for Translators](#guidelines-for-translators)
- [Guidelines for Code](#guidelines-for-code)
- [Translation Workflow](#translation-workflow)
  - [1. Extract Messages](#1-extract-messages)
  - [2. Update PO Files](#2-update-po-files)
  - [3. Translate](#3-translate)
  - [4. Compile](#4-compile)
  - [5. Verify](#5-verify)
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

## Translation Workflow

### 1. Extract Messages

When code changes, new translatable strings might be added. Extract them to the template (`redbot/translations/messages.pot`):

Run this when you have modified the source code and want to capture new or changed strings.

```bash
make i18n-extract
```

### 2. Update PO Files

Update the `.po` files for all locales to include the new strings from the template:

Run this to propagate the changes from the template to the individual language files.

```bash
make i18n-update
```

### 3. Translate

You have two options for translation:

**Option A: Manual Translation**
Edit the `.po` files (e.g., `redbot/translations/fr/LC_MESSAGES/messages.po`) to add missing translations or correct existing ones.

**Option B: Auto-Translation**
Use an LLM (via the `llm` package) to automatically translate missing strings. You can specify the model using the `MODEL` variable (default: `mlx-community/aya-23-8B-4bit`) and the rate limit using `RPM` (default: unlimited; this is for remote models).

```bash
make i18n-autotranslate MODEL=gemini-2.5-flash-lite RPM=15
```
*Note: To use remote models you must have the `llm` package configured with valid API keys (e.g., `./.venv/bin/llm keys set gemini`; see <https://ai.google.dev/gemini-api/docs/api-key>).*

### 4. Compile

Compile the `.po` files into binary `.mo` files for use at runtime:

```bash
make i18n-compile
```

### 5. Verify

Run the tests to verify the translations:

```bash
make i18n_test
```

Alternatively, run the local server and visit it with your browser's language set to the target locale:

```bash
make server
```

## Adding a New Language

To add a new language (e.g., Spanish `es`):

```bash
make i18n-init LANG=es
```
Then follow steps 2-5 above. Once the language is ready, make sure to

1. Update the `httplint` dependency in `pyproject.toml` to a version that supports that language
2. Update `redbot/18n.py` to list the language in `AVAILABLE_LOCALES`
