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

    def check_hdr(self, name, vals, expected_val, expected_msgs):
        self.red.__init__()
        val = self.parseHeader(name, vals)
        self.assertEqual(expected_val, val, 
            "[%s] %s != %s" % (name, str(expected_val), str(val)))
        diff = set(
            [n.__name__ for n in expected_msgs]).symmetric_difference(
            set(self.red.msg_classes)
        )
        self.assertEqual(len(diff), 0, 
            "[%s] Mismatched messages: %s" % (name, diff)
        )

    def test_unquoteString(self):
        i = 0
        for (instr, expected_str, expected_msgs) in [
            ('foo', 'foo', []),
            ('"foo"', 'foo', []),
            (r'"fo\"o"', 'fo"o', []),
            (r'"f\"o\"o"', 'f"o"o', []),
            (r'"fo\\o"', r'fo\o', []),
            (r'"f\\o\\o"', r'f\o\o', []),
            (r'"fo\o"', 'foo', []),
        ]:
            self.red.__init__()
            out_str = self.parser._unquoteString(unicode(instr))
            diff = set(
                [n.__name__ for n in expected_msgs]).symmetric_difference(
                set(self.red.msg_classes)
            )
            self.assertEqual(len(diff), 0, 
                "[%s] Mismatched messages: %s" % (i, diff)
            )
            self.assertEqual(expected_str, out_str, 
                "[%s] %s != %s" % (i, str(expected_str), str(out_str)))
            i += 1
    
    def test_splitString(self):
        i = 0
        for (instr, expected_outlist, item, split) in [
            ('"abc", "def"', 
             ['"abc"', '"def"'], 
             ra.QUOTED_STRING, 
             r"\s*,\s*"
            ),
            (r'"\"ab", "c\d"', 
             [r'"\"ab"', r'"c\d"'], 
             ra.QUOTED_STRING, 
             r"\s*,\s*"
            )
        ]:
            self.red.__init__()
            outlist = self.parser._splitString(unicode(instr), item, split)
            self.assertEqual(expected_outlist, outlist, 
                "[%s] %s != %s" % (i, str(expected_outlist), str(outlist)))
            i += 1
    
    def test_parse_params(self):
        i = 0
        for (instr, expected_pd, expected_msgs) in [
            ('foo=bar', {'foo': 'bar'}, []),
            ('foo="bar"', {'foo': 'bar'}, []),
            ('foo="bar"; baz=bat', {'foo': 'bar', 'baz': 'bat'}, []),
            ('foo="bar"; baz="b=t"; bam="boom"',
             {'foo': 'bar', 'baz': 'b=t', 'bam': 'boom'}, []
            ),
            (r'foo="b\"ar"', {'foo': 'b"ar'}, []),
            (r'foo=bar; foo=baz', {'foo': 'baz'}, 
             [rs.PARAM_REPEATS]
            ),
            ("foo=bar; baz='bat'", {'foo': 'bar', 'baz': "'bat'"}, 
             [rs.PARAM_SINGLE_QUOTED]
            ),
            ("foo*=\"UTF-8''a%cc%88.txt\"", 
             {'foo*': u'a\u0308.txt'},
             [rs.PARAM_STAR_QUOTED]
            ),
            ("foo*=''a%cc%88.txt", 
             {},
             [rs.PARAM_STAR_NOCHARSET]
            ),
            ("foo*=utf-16''a%cc%88.txt", 
             {},
             [rs.PARAM_STAR_CHARSET]
            ),
            ("nostar*=utf-8''a%cc%88.txt",
             {},
             [rs.PARAM_STAR_BAD]
            ),
            ("NOstar*=utf-8''a%cc%88.txt",
             {},
             [rs.PARAM_STAR_BAD]
            )
        ]:
            self.red.__init__()
            param_dict = self.parser._parse_params('test', instr, ['nostar'])
            diff = set(
                [n.__name__ for n in expected_msgs]).symmetric_difference(
                set(self.red.msg_classes)
            )
            self.assertEqual(len(diff), 0, 
                "[%s] Mismatched messages: %s" % (i, diff)
            )
            self.assertEqual(expected_pd, param_dict, 
                "[%s] %s != %s" % (i, str(expected_pd), str(param_dict)))
            i += 1
                

    def test_content_disposition(self):
        cd = 'Content-Disposition'
        # quoted-string
        self.check_hdr(cd, ['attachment; filename="foo.txt"'], 
         ('attachment', {'filename': 'foo.txt'}),
         []
        )

        # token
        self.check_hdr(cd, ['attachment; filename=foo.txt'], 
         ('attachment', {'filename': 'foo.txt'}),
         []
        )

        # inline
        self.check_hdr(cd, ['inline; filename=foo.txt'], 
         ('inline', {'filename': 'foo.txt'}),
         []
        )

        # token
        self.check_hdr(cd, 
         ['attachment; filename=foo.txt, inline; filename=bar.txt'], 
         ('inline', {'filename': 'bar.txt'}),
         [rs.SINGLE_HEADER_REPEAT]
        )

        # filename*
        self.check_hdr(cd, 
         ["attachment; filename=foo.txt; filename*=UTF-8''a%cc%88.txt"],
         ('attachment', {
            'filename': 'foo.txt', 
            'filename*': u'a\u0308.txt'
         }),
         []
        )

        # filename* quoted
        self.check_hdr(cd, 
         ["attachment; filename=foo.txt; filename*=\"UTF-8''a%cc%88.txt\""],
         ('attachment', {
            'filename': 'foo.txt', 
            'filename*': u'a\u0308.txt'
         }),
         [rs.PARAM_STAR_QUOTED]
        )

        # % in filename
        self.check_hdr(cd, ["attachment; filename=fo%22o.txt"],
         ('attachment', {
            'filename': 'fo%22o.txt', 
         }),
         [rs.DISPOSITION_FILENAME_PERCENT]
        )

        # pathchar in filename
        self.check_hdr(cd, ['"attachment; filename="/foo.txt"'],
         ('attachment', {
            'filename': '/foo.txt', 
         }),
         [rs.DISPOSITION_FILENAME_PATH_CHAR]
        )

    def test_link(self):
        li = 'Link'
        # basic
        self.check_hdr(li, ['<http://www.example.com/>; rel=example'], 
         ('http://www.example.com/', {'rel': 'example'}),
         []
        )

        # quoted relation
        self.check_hdr(li, ['<http://www.example.com/>; rel="example"'], 
         ('http://www.example.com/', {'rel': 'example'}),
         []
        )

        # relative URI
        self.check_hdr(li, ['</foo>; rel="example"'], 
         ('/foo', {'rel': 'example'}),
         []
        )
        
        # repeating rel
        self.check_hdr(li, ['</foo>; rel="example"; rel="another"'], 
         ('/foo', {'rel': 'another'}),
         [rs.PARAM_REPEATS]
        )
        
        # quotes (bad syntax)
        self.check_hdr(li, ['"/foo", rel="example"'],
         None,
         [rs.BAD_SYNTAX]
        )
        
        # rev
        self.check_hdr(li, ['</foo>; rev="bar"'],
         ('/foo', {'rev': 'bar'}),
         [rs.LINK_REV]
        )
        
        # bad anchor
        self.check_hdr(li, ['</foo>; rel="bar"; anchor="{blah}"'],
         ('/foo', {'rel': 'bar', 'anchor': '{blah}'}),
         [rs.LINK_BAD_ANCHOR]
        )
        
    def test_date(self):
        da = 'Date'
        # basic
        self.check_hdr(da, ['Mon, 04 Jul 2011 09:08:06 GMT'],
         1309770486, 
         []
        )
        
        # blank
        self.check_hdr(da, [''],
         None,
         [rs.BAD_DATE_SYNTAX])
        
if __name__ == "__main__":
    unittest.main()