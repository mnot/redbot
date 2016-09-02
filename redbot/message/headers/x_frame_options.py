#!/usr/bin/env python

import redbot.message.headers as headers
from redbot.speak import Note, categories, levels
from redbot.message.headers import HttpHeader, HeaderTest

class x_frame_options(HttpHeader):
  canonical_name = u"X-Frame-Options"
  list_header = True
  deprecated = False
  valid_in_requests = False
  valid_in_responses = True
  
  def parse(self, field_value, add_note):
      return field_value.lower()
    
  def evaluate(self, add_note):
      if 'deny' in self.value:
          add_note(FRAME_OPTIONS_DENY)
      elif 'sameorigin' in self.value:
          add_note(FRAME_OPTIONS_SAMEORIGIN)
      else:
          add_note(FRAME_OPTIONS_UNKNOWN)


class FRAME_OPTIONS_DENY(Note):
    category = categories.SECURITY
    level = levels.INFO
    summary = u"%(response)s prevents some browsers from rendering it if it will be contained within a frame."
    text = u"""\
The `X-Frame-Options` response header controls how IE8 handles HTML frames; the `DENY` value
prevents this content from being rendered within a frame, which defends against certain types of
attacks.

See [this blog entry](http://bit.ly/v5Bh5Q) for more information.
     """

class FRAME_OPTIONS_SAMEORIGIN(Note):
    category = categories.SECURITY
    level = levels.INFO
    summary = u"%(response)s prevents some browsers from rendering it if it will be contained within a frame on another site."
    text = u"""\
The `X-Frame-Options` response header controls how IE8 handles HTML frames; the `DENY` value
prevents this content from being rendered within a frame on another site, which defends against
certain types of attacks.

Currently this is supported by IE8 and Safari 4.

See [this blog entry](http://bit.ly/v5Bh5Q) for more information.
     """

class FRAME_OPTIONS_UNKNOWN(Note):
    category = categories.SECURITY
    level = levels.WARN
    summary = u"%(response)s contains an X-Frame-Options header with an unknown value."
    text = u"""\
Only two values are currently defined for this header, `DENY` and `SAMEORIGIN`. Using other values
here won't necessarily cause problems, but they probably won't have any effect either.

See [this blog entry](http://bit.ly/v5Bh5Q) for more information.
     """


class DenyXFOTest(HeaderTest):
    name = 'X-Frame-Options'
    inputs = ['deny']
    expected_out = ['deny']
    expected_err = [FRAME_OPTIONS_DENY]
    
class DenyXFOCaseTest(HeaderTest):
    name = 'X-Frame-Options'
    inputs = ['DENY']
    expected_out = ['deny']
    expected_err = [FRAME_OPTIONS_DENY]
    
class SameOriginXFOTest(HeaderTest):
    name = 'X-Frame-Options'
    inputs = ['sameorigin']
    expected_out = ['sameorigin']
    expected_err = [FRAME_OPTIONS_SAMEORIGIN]

class UnknownXFOTest(HeaderTest):
    name = 'X-Frame-Options'
    inputs = ['foO']
    expected_out = ['foo']
    expected_err = [FRAME_OPTIONS_UNKNOWN]

