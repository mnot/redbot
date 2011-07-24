#!/usr/bin/env python
# coding=UTF-8


import sys
import unittest
sys.path.insert(0, "..")
from lib import response_analyse as ra
from lib import speak as rs
# FIXME: imports for rest of red

class DummyRed(object):
    def __init__(self):
        self.res_hdrs = []
        self.res_phrase = ""
        self.messages = []
        self.msg_classes = []
        
    def setMessage(self, name, msg, **kw):
        self.messages.append(msg(name, None, kw))
        self.msg_classes.append(msg.__name__)


class ResponseHeaderParserTester(unittest.TestCase):
    def setUp(self):
        self.red = DummyRed()
        self.parser = ra.ResponseHeaderParser(self.red)
    
    def parseHeader(self, name, values):
        name_token = name.lower().replace('-', '_')
        return getattr(self.parser, name_token)(name, values)
    
    def test_content_disposition(self):
        i = 0
        for (hdrs, expected_val, expected_msgs) in [
            # 0: quoted-string
            (['attachment; filename="foo.txt"'], 
             ('attachment', {'filename': 'foo.txt'}),
             []
            ),
            # 1: token
            (['attachment; filename=foo.txt'], 
             ('attachment', {'filename': 'foo.txt'}),
             []
            ),
            # 2: inline
            (['inline; filename=foo.txt'], 
             ('inline', {'filename': 'foo.txt'}),
             []
            ),
            # 3: token
            (['attachment; filename=foo.txt, inline; filename=bar.txt'], 
             ('inline', {'filename': 'bar.txt'}),
             [rs.SINGLE_HEADER_REPEAT]
            ),
            # 4: filename*
            (["attachment; filename=foo.txt; filename*=UTF-8''a%cc%88.txt"],
             ('attachment', {
                'filename': 'foo.txt', 
                'filename*': u'a\u0308.txt'
             }),
             []
            ),
        ]:
            self.red.__init__()
            val = self.parseHeader('Content-Disposition', hdrs)
            self.assertEqual(expected_val, val, 
                "[%s] %s != %s" % (i, str(expected_val), str(val)))
            diff = set(
                [n.__name__ for n in expected_msgs]).symmetric_difference(
                set(self.red.msg_classes)
            )
            self.assertEqual(len(diff), 0, 
                "[%s] Mismatched messages: %s" % (i, diff)
            )
            i += 1

        
if __name__ == "__main__":
    unittest.main()