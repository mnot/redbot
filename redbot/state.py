#!/usr/bin/env python

"""
The Resource Expert Droid State container.

RedState holds all test-related state that's useful for analysis; ephemeral
objects (e.g., the HTTP client machinery) are kept elsewhere.
"""

import types

import redbot.speak as rs

class RedState(object):
    "Base class for things that have test state."

    def __init__(self, name):
        self.name = name
        self.notes = []
        self.transfer_in = 0
        self.transfer_out = 0

    def __repr__(self):
        status = [self.__class__.__module__ + "." + self.__class__.__name__]
        status.append("'%s'" % self.name)
        return "<%s at %#x>" % (", ".join(status), id(self))

    def __getstate__(self):
        state = self.__dict__.copy()
        return dict([(k, v) for k, v in state.items() \
                      if not isinstance(v, types.MethodType)])

    def add_note(self, subject, note, subreq=None, **kw):
        "Set a note."
        kw['response'] = rs.response.get(
            self.name, rs.response['this']
        )
        self.notes.append(note(subject, subreq, kw))
