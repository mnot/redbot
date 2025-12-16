import argparse
import sys
import time
import llm
from .utils import load_catalog, save_catalog, find_po_files, get_lang_from_path


def autotranslate_file(po_file, lang, model_id, rpm):
    catalog = load_catalog(po_file)
    model = llm.get_model(model_id)

    # Identify messages that need translation (empty or fuzzy)
    to_translate = [
        m for m in catalog if m.id and (not m.string or "fuzzy" in m.flags)
    ]
    count = 0
    errors = []

    print(f"Found {len(to_translate)} messages to translate using {model_id}.")

    exception_count = 0
    sleep_time = 60.0 / rpm if rpm > 0 else 0

    for i, message in enumerate(to_translate):
        try:
            if i > 0 and sleep_time > 0:
                time.sleep(sleep_time)

            prompt = f"You are translating short strings and messages for use in a HTTP linting tool. Translate the following text to language code '{lang}'. When they appear, retain embeddded variables as they are. Do not translate HTTP protocol element names (such as header field names). Acronyms (such as 'IMS' and 'INM') should be retained. Return ONLY the translation, NO OTHER TEXT AT ALL. Here is the text to translate:\n\n{message.id}"
            response = model.prompt(prompt)
            translation = response.text().strip()
            exception_count = 0

            if translation:
                message.string = translation
                if "fuzzy" in message.flags:
                    message.flags.remove("fuzzy")
                count += 1
                sys.stdout.write(".")
            else:
                sys.stdout.write("x")
        except KeyboardInterrupt:
            print("\n\nAborting: User interrupted.")
            save_catalog(po_file, catalog)
            sys.exit(1)
        except Exception as e:
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

    if errors:
        print(f"\nEncountered {len(errors)} errors:")
        # Print first few errors to avoid spamming
        for err in errors[:10]:
            print(f"  - {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more.")


def main():
    parser = argparse.ArgumentParser(description="Auto-translate missing strings")
    parser.add_argument("--po_file", help="Path to a single PO file")
    parser.add_argument(
        "--locale_dir", help="Path to locale directory (process all locales)"
    )
    parser.add_argument(
        "--lang", help="Target language code (required for single file)"
    )
    parser.add_argument(
        "--model",
        default="gemini-1.5-flash-latest",
        help="LLM model to use (default: gemini-1.5-flash-latest)",
    )
    parser.add_argument(
        "--rpm", type=int, default=60, help="Requests per minute (default: 60)"
    )

    args = parser.parse_args()

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
            autotranslate_file(po_file, lang, args.model, args.rpm)
    elif args.po_file:
        if not args.lang:
            print("Error: --lang is required for single file autotranslate")
            sys.exit(1)
        autotranslate_file(args.po_file, args.lang, args.model, args.rpm)
    else:
        print("Error: Either --po_file or --locale_dir must be specified.")
        sys.exit(1)


if __name__ == "__main__":
    main()

