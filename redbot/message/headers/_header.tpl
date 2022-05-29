#!/usr/bin/env python

from redbot.message import headers
from redbot.speak import Note, categories, levels
from redbot.type import AddNoteMethodType

class SHORT_NAME(headers.HttpHeader):
    canonical_name = "SHORT_NAME"
    description = """\
FIXME
"""
    reference = None
    syntax = False
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> ...:
        return field_value

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        return


class SHORT_NAME_NOTE(Note):
    category = categories.GENERAL
    level = levels.INFO
    summary = "FIXME"
    text = """\
FIXME"""


class SHORT_NAMETest(headers.HeaderTest):
    name = 'SHORT_NAME'
    inputs = ['FIXME']
    expected_out = ('FIXME')
    expected_err = []
