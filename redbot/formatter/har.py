#!/usr/bin/env python

"""
HAR Formatter for REDbot.
"""


import datetime
try:
    import json
except ImportError:
    import simplejson as json

from thor.http import get_header
from redbot import __version__
from redbot.formatter import Formatter
from redbot.speak import levels


class HarFormatter(Formatter):
    """
    Format a RED object (and any descendants) as HAR.
    """
    can_multiple = True
    name = "har"
    media_type = "application/json"

    def __init__(self, *args, **kw):
        Formatter.__init__(self, *args, **kw)
        self.har = {
            'log': {
                "version": "1.1",
                "creator": {
                    "name": "REDbot",
                    "version": __version__,
                },
                "browser": {
                    "name": "REDbot",
                    "version": __version__,
                },
                "pages": [],
                "entries": [],
            },
        }
        self.last_id = 0

    def start_output(self):
        pass

    def status(self, msg):
        pass

    def feed(self, state, sample):
        pass

    def finish_output(self):
        "Fill in the template with RED's results."
        if self.state.response.complete:
            page_id = self.add_page(self.state)
            self.add_entry(self.state, page_id)
            for linked_state in [d[0] for d in self.state.linked]:
                # filter out incomplete responses
                if linked_state.response.complete:
                    self.add_entry(linked_state, page_id)
        self.output(json.dumps(self.har, indent=4))
        self.done()

    def add_entry(self, state, page_ref=None):
        entry = {
            "startedDateTime": isoformat(state.request.start_time),
            "time": int((state.response.complete_time - state.request.start_time) * 1000),
            "_red_messages": self.format_notes(state)
        }
        if page_ref:
            entry['pageref'] = "page%s" % page_ref

        request = {
            'method': state.request.method,
            'url': state.request.uri,
            'httpVersion': "HTTP/1.1",
            'cookies': [],
            'headers': self.format_headers(state.request.headers),
            'queryString': [],
            'headersSize': -1,
            'bodySize': -1,
        }

        response = {
            'status': state.response.status_code,
            'statusText': state.response.status_phrase,
            'httpVersion': "HTTP/%s" % state.response.version,
            'cookies': [],
            'headers': self.format_headers(state.response.headers),
            'content': {
                'size': state.response.decoded_len,
                'compression': state.response.decoded_len - state.response.payload_len,
                'mimeType': (get_header(state.response.headers, 'content-type') or [""])[0],
            },
            'redirectURL': (
                get_header(state.response.headers, 'location') or [""])[0],
            'headersSize': state.response.header_length,
            'bodySize': state.response.payload_len,
        }

        cache = {}
        timings = {
            'dns': -1,
            'connect': -1,
            'blocked': 0,
            'send': 0,
            'wait': int((state.response.start_time - state.request.start_time) * 1000),
            'receive': int((state.response.complete_time - state.response.start_time) * 1000),
        }

        entry.update({
            'request': request,
            'response': response,
            'cache': cache,
            'timings': timings,
        })
        self.har['log']['entries'].append(entry)


    def add_page(self, state):
        page_id = self.last_id + 1
        page = {
            "startedDateTime": isoformat(state.request.start_time),
            "id": "page%s" % page_id,
            "title": "",
            "pageTimings": {
                "onContentLoad": -1,
                "onLoad": -1,
            },
        }
        self.har['log']['pages'].append(page)
        return page_id

    def format_headers(self, hdrs):
        return [{'name': n, 'value': v} for n, v in hdrs]

    def format_notes(self, state):
        out = []
        for m in state.notes:
            msg = {
                "subject": m.subject,
                "category": m.category,
                "level": m.level,
                "summary": m.show_summary(self.lang)
            }
            smsgs = [i for i in getattr(
                m.subrequest, "notes", []) if i.level in [levels.BAD]]
            msg["subrequests"] = [{
                "subject": sm.subject,
                "category": sm.category,
                "level": sm.level,
                "summary": m.show_summary(self.lang)
            } for sm in smsgs]
            out.append(msg)
        return out

def isoformat(timestamp):
    class TZ(datetime.tzinfo):
        def utcoffset(self, dt):
            return datetime.timedelta(minutes=0)
    return "%sZ" % datetime.datetime.utcfromtimestamp(timestamp).isoformat()
