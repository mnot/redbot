# Translation Workflow

This document outlines the process for adding and updating translations in `redbot`.

## Prerequisites

Ensure you have the development environment set up:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Coding Guidelines

*   **Note Classes**: Strings assigned to `_summary` and `_text` in `Note` subclasses are automatically extracted.
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

## Workflow

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
Use an LLM (via the `llm` package) to automatically translate missing strings. You can specify the model using the `MODEL` variable (default: `gemini-2.5-flash-lite`) and the rate limit using `RPM` (default: 15).

```bash
make i18n-autotranslate MODEL=gemini-2.5-flash-lite RPM=15
```
*Note: You must have the `llm` package configured with valid API keys (e.g., `./.venv/bin/llm keys set gemini`).*

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
Then follow steps 2-7 above.
