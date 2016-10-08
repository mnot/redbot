"""
Check all Note definitions.
"""

import re

from redbot.speak import Note, categories, levels

import common


def checkNote(note_cls):
    note_name = note_cls.__name__
    assert note_cls.category in list(categories.__class__.__dict__.values()), note_name
    assert note_cls.level in list(levels.__class__.__dict__.values()), note_name
    assert isinstance(note_cls.summary, str), note_name
    assert note_cls.summary != "", note_name
    assert not re.search(r"\s{2,}", note_cls.summary), note_name
    assert isinstance(note_cls.text, str), note_name
    
if __name__ == "__main__":
    common.checkSubClasses(Note, checkNote)
