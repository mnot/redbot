# -*- coding: utf-8 -*-

"""

Unicorn Interface for Red Cacheability Checker

Created on Jun 30, 2010
@author: Hirotaka Nakajima <hiro@w3.org>

"""
import sys
import os
from redbot.droid import InspectingResourceExpertDroid
from redbot.speak import _Classifications
import cgi
import logging
from string import Template
import thor
from redbot.formatter.unicorn import W3CUnicornFormatter

__date__ = "Jun 30, 2010"
__author__ = "Hirotaka Nakajima <hiro@w3.org>"
__copyright__ = """\
Copyright (c) 2011 World Wide Web Consortium

This code is licensed under W3C Software License.
http://www.w3.org/Consortium/Legal/2002/copyright-software-20021231 
"""

class UnicornUi(object):
    """
    Unicorn Interface of Red Cacheability checker
    """
    def __init__(self, test_uri):
        """
        Constractor
        @param test_uri: Test Uri
        """
        self.test_uri = test_uri
        try:
            self.red = InspectingResourceExpertDroid(self.test_uri)
            self.result = ""
            self.done = False
            self.groups = []
            logger = logging.getLogger()
            logger.setLevel(logging.DEBUG)
            self.formatter = W3CUnicornFormatter(self.test_uri, self.test_uri, [], 'en', self._output)
            self.formatter.set_red(self.red.state)
            self.formatter.start_output()

            self.red.run(self._done_cb)
            thor.run()
        except:
            import traceback
            logging.error(traceback.format_exc())
            self.result = """<?xml version="1.0" ?>
<observationresponse ref="None" xml:lang="en" xmlns="http://www.w3.org/2009/10/unicorn/observationresponse">
    <message type="error">
        <title>
            Internal Server Error
        </title>
        <description>
            Internal Server Error occured.
        </description>
    </message>
</observationresponse>"""

    def _done_cb(self):
        self.formatter.finish_output()
        thor.stop()
        
    def _output(self,msg):
        self.result = msg
        
    def get_result(self):
        """
        Return result if cacheability check was finished.
        If not, return None
        @return: Result of cacheablity checker.
        """
        return str(self.result)

def application(environ, start_response):
    method = environ.get('REQUEST_METHOD')
    test_uri = None
    result = None
    run_engine = False
    response_headers = None
    if method == "GET":
        query = cgi.parse_qsl(environ.get('QUERY_STRING'))
        for q in query:
            if len(q) == 2:
                if q[0] == "ca_uri":
                    uri = q[1]
                    test_uri = cgi.escape(uri, True) 
                if q[0] == "output":
                    if q[1] == "ucn":
                        run_engine = True
                    
    
    if test_uri != None:
        if run_engine == True:
            red = UnicornUi(test_uri)
            result = red.get_result()
            status = '200 OK'
            response_headers = [('Content-type', 'application/xml'), ('Content-Length', str(len(result)))]
        else:
            status = '200 OK'
            logging.error(os.path.abspath("."))
            t = Template(open(os.path.join(os.path.dirname(__file__), "redirect_template.html")).read())
            d = dict(uri="http://redbot.org/?uri=" + test_uri)
            result = t.safe_substitute(d)
            response_headers = [('Content-type', 'application/xhtml+xml'), ('Content-Length', str(len(result)))]
    if result == None:
        status = '200 OK'
        result = """<?xml version="1.0" ?>
<observationresponse ref="None" xml:lang="en" xmlns="http://www.w3.org/2009/10/unicorn/observationresponse">
    <message type="error">
        <title>
            No URI provided
        </title>
        <description>
            URI isn't provided
        </description>
    </message>
</observationresponse>"""
        response_headers = [('Content-type', 'application/xml'), ('Content-Length', str(len(result)))]

    start_response(status, response_headers)    
    return [result]

def standalone_main(test_uri):
    test_uri = cgi.escape(test_uri, True) 
    red = UnicornUi(test_uri) 
    print red.get_result()

if __name__ == "__main__":
    import sys
    test_uri = sys.argv[1]   
    standalone_main(test_uri)

