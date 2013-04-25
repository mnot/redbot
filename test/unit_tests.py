#!/usr/bin/env python
# coding=UTF-8

import sys
import unittest
sys.path.insert(0, "..")

import redbot.message.headers as headers
import redbot.http_syntax as syntax
import redbot.speak as rs
from redbot.message import DummyMsg

class GeneralHeaderTesters(unittest.TestCase):
    def setUp(self):
        self.red = DummyMsg()
    
    def test_unquote_string(self):
        i = 0
        for (instr, expected_str, expected_notes) in [
            ('foo', 'foo', []),
            ('"foo"', 'foo', []),
            (r'"fo\"o"', 'fo"o', []),
            (r'"f\"o\"o"', 'f"o"o', []),
            (r'"fo\\o"', r'fo\o', []),
            (r'"f\\o\\o"', r'f\o\o', []),
            (r'"fo\o"', 'foo', []),
        ]:
            self.red.__init__()
            out_str = headers.unquote_string(unicode(instr))
            diff = set(
                [n.__name__ for n in expected_notes]).symmetric_difference(
                set(self.red.note_classes)
            )
            self.assertEqual(len(diff), 0, 
                "[%s] Mismatched notes: %s" % (i, diff)
            )
            self.assertEqual(expected_str, out_str, 
                "[%s] %s != %s" % (i, str(expected_str), str(out_str)))
            i += 1
    
    def test_split_string(self):
        i = 0
        for (instr, expected_outlist, item, split) in [
            ('"abc", "def"', 
             ['"abc"', '"def"'], 
             syntax.QUOTED_STRING, 
             r"\s*,\s*"
            ),
            (r'"\"ab", "c\d"', 
             [r'"\"ab"', r'"c\d"'], 
             syntax.QUOTED_STRING, 
             r"\s*,\s*"
            )
        ]:
            self.red.__init__()
            outlist = headers.split_string(unicode(instr), item, split)
            self.assertEqual(expected_outlist, outlist, 
                "[%s] %s != %s" % (i, str(expected_outlist), str(outlist)))
            i += 1
    
    def test_parse_params(self):
        i = 0
        for (instr, expected_pd, expected_notes, delim) in [
            ('foo=bar', {'foo': 'bar'}, [], ';'),
            ('foo="bar"', {'foo': 'bar'}, [], ';'),
            ('foo="bar"; baz=bat', {'foo': 'bar', 'baz': 'bat'}, [], ';'),
            ('foo="bar"; baz="b=t"; bam="boom"',
             {'foo': 'bar', 'baz': 'b=t', 'bam': 'boom'}, [], ';'
            ),
            (r'foo="b\"ar"', {'foo': 'b"ar'}, [], ';'),
            (r'foo=bar; foo=baz', 
             {'foo': 'baz'}, 
             [rs.PARAM_REPEATS], 
             ';'
            ),
            ('foo=bar; baz="b;at"', 
             {'foo': 'bar', 'baz': "b;at"}, 
             [],
             ';'
            ),
            ('foo=bar, baz="bat"', 
             {'foo': 'bar', 'baz': "bat"}, 
             [],
             ','
            ),
            ('foo=bar, baz="b,at"', 
             {'foo': 'bar', 'baz': "b,at"}, 
             [],
             ','
            ),
            ("foo=bar; baz='bat'", 
             {'foo': 'bar', 'baz': "'bat'"}, 
             [rs.PARAM_SINGLE_QUOTED], 
             ';'
            ),
            ("foo*=\"UTF-8''a%cc%88.txt\"", 
             {'foo*': u'a\u0308.txt'},
             [rs.PARAM_STAR_QUOTED], 
             ';'
            ),
            ("foo*=''a%cc%88.txt", 
             {},
             [rs.PARAM_STAR_NOCHARSET], 
             ';'
            ),
            ("foo*=utf-16''a%cc%88.txt", 
             {},
             [rs.PARAM_STAR_CHARSET], 
             ';'
            ),
            ("nostar*=utf-8''a%cc%88.txt",
             {},
             [rs.PARAM_STAR_BAD], 
             ';'
            ),
            ("NOstar*=utf-8''a%cc%88.txt",
             {},
             [rs.PARAM_STAR_BAD], 
             ';'
            )
        ]:
            self.red.__init__()
            param_dict = headers.parse_params(
              self.red, 'test', instr, ['nostar'], delim
            )
            diff = set(
                [n.__name__ for n in expected_notes]).symmetric_difference(
                set(self.red.note_classes)
            )
            self.assertEqual(len(diff), 0, 
                "[%s] Mismatched notes: %s" % (i, diff)
            )
            self.assertEqual(expected_pd, param_dict, 
                "[%s] %s != %s" % (i, str(expected_pd), str(param_dict)))
            i += 1
                
if __name__ == "__main__":
    # requires Python 2.7
    import sys
    loader = unittest.TestLoader()
    if len(sys.argv) == 2:
        auto_suite = loader.discover("../redbot/message/headers", 
                                    "%s.py" % sys.argv[1],  
                                    "../redbot"
        )
        all_tests = unittest.TestSuite([auto_suite])
    else:
        auto_suite = loader.discover(
            "../redbot", "*.py", '../redbot'
        )
        local_suite = loader.loadTestsFromTestCase(GeneralHeaderTesters)
        all_tests = unittest.TestSuite([local_suite, auto_suite])
    result = unittest.TextTestRunner().run(all_tests)
    if result.errors or result.failures:
        sys.exit(1)
