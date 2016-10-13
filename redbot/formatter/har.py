#!/usr/bin/env python

"""
HAR Formatter for REDbot.
"""


import datetime
import json


from thor.http import get_header
from redbot import __version__
from redbot.formatter import Formatter


class HarFormatter(Formatter):
    """
    Format a HttpResource object (and any descendants) as HAR.
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

    def feed(self, sample):
        pass

    def finish_output(self):
        "Fill in the template with RED's results."
        if self.resource.response.complete:
            page_id = self.add_page(self.resource)
            self.add_entry(self.resource, page_id)
            for linked_resource in [d[0] for d in self.resource.linked]:
                # filter out incomplete responses
                if linked_resource.response.complete:
                    self.add_entry(linked_resource, page_id)
        self.output(json.dumps(self.har, indent=4))

    def add_entry(self, resource, page_ref=None):
        entry = {
            "startedDateTime": isoformat(resource.request.start_time),
            "time": int((resource.response.complete_time - resource.request.start_time) * 1000),
            "_red_messages": self.format_notes(resource)
        }
        if page_ref:
            entry['pageref'] = "page%s" % page_ref

        request = {
            'method': resource.request.method,
            'url': resource.request.uri,
            'httpVersion': "HTTP/1.1",
            'cookies': [],
            'headers': self.format_headers(resource.request.headers),
            'queryString': [],
            'headersSize': -1,
            'bodySize': -1,
        }

        response = {
            'status': resource.response.status_code,
            'statusText': resource.response.status_phrase,
            'httpVersion': "HTTP/%s" % resource.response.version,
            'cookies': [],
            'headers': self.format_headers(resource.response.headers),
            'content': {
                'size': resource.response.decoded_len,
                'compression': resource.response.decoded_len - resource.response.payload_len,
                'mimeType': (get_header(resource.response.headers, 'content-type') or [""])[0],
            },
            'redirectURL': (
                get_header(resource.response.headers, 'location') or [""])[0],
            'headersSize': resource.response.header_length,
            'bodySize': resource.response.payload_len,
        }

        cache = {}
        timings = {
            'dns': -1,
            'connect': -1,
            'blocked': 0,
            'send': 0,
            'wait': int((resource.response.start_time - resource.request.start_time) * 1000),
            'receive': int((resource.response.complete_time - resource.response.start_time) * 1000),
        }

        entry.update({
            'request': request,
            'response': response,
            'cache': cache,
            'timings': timings,
        })
        self.har['log']['entries'].append(entry)


    def add_page(self, resource):
        page_id = self.last_id + 1
        page = {
            "startedDateTime": isoformat(resource.request.start_time),
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

    def format_notes(self, resource):
        out = []
        for m in resource.notes:
            msg = {
                "subject": m.subject,
                "category": m.category,
                "level": m.level,
                "summary": m.show_summary(self.lang)
            }
            out.append(msg)
        return out

def isoformat(timestamp):
    class TZ(datetime.tzinfo):
        def utcoffset(self, dt):
            return datetime.timedelta(minutes=0)
    return "%sZ" % datetime.datetime.utcfromtimestamp(timestamp).isoformat()
