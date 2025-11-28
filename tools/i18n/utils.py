import glob
import os


def find_po_files(locale_dir):
    """Find all messages.po files in the given locale directory."""
    return glob.glob(os.path.join(locale_dir, "*", "LC_MESSAGES", "messages.po"))


def get_lang_from_path(po_path):
    """Derive language code from PO file path."""
    # .../locale/LC_MESSAGES/messages.po
    parts = po_path.split(os.sep)
    if len(parts) >= 3:
        return parts[-3]
    return None


from babel.messages import pofile


def load_catalog(po_path):
    with open(po_path, "rb") as f:
        return pofile.read_po(f)


def save_catalog(po_path, catalog):
    with open(po_path, "wb") as f:
        pofile.write_po(f, catalog)
