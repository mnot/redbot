#!/usr/bin/env python




import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax


@rh.GenericHeaderSyntax
@rh.CheckFieldSyntax(
    r'(?:%(TOKEN)s(?:\s*;\s*%(PARAMETER)s)*)' % syntax.__dict__,
    rh.rfc6266
)
def parse(subject, value, red):
    try:
        disposition, params = value.split(";", 1)
    except ValueError:
        disposition, params = value, ''
    disposition = disposition.lower()
    param_dict = rh.parse_params(red, subject, params)
    if disposition not in ['inline', 'attachment']:
        red.add_note(subject,
            rs.DISPOSITION_UNKNOWN,
            disposition=disposition
        )
    if not param_dict.has_key('filename'):
        red.add_note(subject, rs.DISPOSITION_OMITS_FILENAME)
    if "%" in param_dict.get('filename', ''):
        red.add_note(subject, rs.DISPOSITION_FILENAME_PERCENT)
    if "/" in param_dict.get('filename', '') or \
       r"\\" in param_dict.get('filename*', ''):
        red.add_note(subject, rs.DISPOSITION_FILENAME_PATH_CHAR)
    return disposition, param_dict

@rh.SingleFieldValue
def join(subject, values, red):
    return values[-1]
    

class QuotedCDTest(rh.HeaderTest):
    name = 'Content-Disposition'
    inputs = ['attachment; filename="foo.txt"']
    expected_out = ('attachment', {'filename': 'foo.txt'})
    expected_err = [] 
    
class TokenCDTest(rh.HeaderTest):
    name = 'Content-Disposition'
    inputs = ['attachment; filename=foo.txt']
    expected_out = ('attachment', {'filename': 'foo.txt'})
    expected_err = [] 

class InlineCDTest(rh.HeaderTest):
    name = 'Content-Disposition'
    inputs = ['inline; filename=foo.txt']
    expected_out = ('inline', {'filename': 'foo.txt'})
    expected_err = [] 

class RepeatCDTest(rh.HeaderTest):
    name = 'Content-Disposition'
    inputs = ['attachment; filename=foo.txt, inline; filename=bar.txt']
    expected_out = ('inline', {'filename': 'bar.txt'})
    expected_err = [rs.SINGLE_HEADER_REPEAT]

class FilenameStarCDTest(rh.HeaderTest):
    name = 'Content-Disposition'
    inputs = ["attachment; filename=foo.txt; filename*=UTF-8''a%cc%88.txt"]
    expected_out = ('attachment', {
            'filename': 'foo.txt', 
            'filename*': u'a\u0308.txt'})
    expected_err = []

class FilenameStarQuotedCDTest(rh.HeaderTest):    
    name = 'Content-Disposition'
    inputs = ["attachment; filename=foo.txt; filename*=\"UTF-8''a%cc%88.txt\""]
    expected_out = ('attachment', {
            'filename': 'foo.txt', 
            'filename*': u'a\u0308.txt'})
    expected_err = [rs.PARAM_STAR_QUOTED]

class FilenamePercentCDTest(rh.HeaderTest):
    name = 'Content-Disposition'
    inputs = ["attachment; filename=fo%22o.txt"]
    expected_out = ('attachment', {'filename': 'fo%22o.txt', })
    expected_err = [rs.DISPOSITION_FILENAME_PERCENT]
    
class FilenamePathCharCDTest(rh.HeaderTest):
    name = 'Content-Disposition'
    inputs = ['"attachment; filename="/foo.txt"']
    expected_out = ('attachment', {'filename': '/foo.txt',})
    expected_err = [rs.DISPOSITION_FILENAME_PATH_CHAR]

