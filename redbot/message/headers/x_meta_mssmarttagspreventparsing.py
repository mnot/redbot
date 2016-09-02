#!/usr/bin/env python

import redbot.message.headers as headers
from redbot.speak import Note, c as categories, l as levels
from redbot.message.headers import HttpHeader, HeaderTest
from redbot.syntax import rfc7234

class x_meta_mssmarttagspreventparsing(HttpHeader):
  canonical_name = u"X-Meta-MSSmartTagsPreventParsing"
  list_header = False
  deprecated = False
  valid_in_requests = False
  valid_in_responses = True
  
  def evaluate(self, add_note):
      add_note(subject, SMART_TAG_NO_WORK)
      return values
    


class SMART_TAG_NO_WORK(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = u"The %(field_name)s header doesn't have any effect on smart tags."
    text = u"""\
This header doesn't have any effect on Microsoft Smart Tags, except in certain beta versions of
IE6. To turn them off, you'll need to make changes in the HTML content it"""

