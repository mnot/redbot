# -*- coding: utf-8 -*-

"""

Unicorn Interface for Red Cacheability Checker

Created on Jun 30, 2010
@author: Hirotaka Nakajima <hiro@w3.org>

"""
import sys
import os
from redbot.resource import HttpResource
from redbot.speak import _Classifications
from xml.dom import minidom
from xml.dom.minidom import parseString
import re
import cgi
import logging
import nbhttp
from string import Template

__date__ = "Jun 30, 2010"
__author__ = "Hirotaka Nakajima <hiro@w3.org>"

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
            self.red = HttpResource(self.test_uri)
            self.result = ""
            self.done = False
            self.groups = []
            logger = logging.getLogger()
            logger.setLevel(logging.DEBUG)
            if self.red.response.complete:
                self.result = self._generate_output_xml(test_uri).toprettyxml()
            else:
                error_string = ""
                if self.red.response.http_error['desc'] == nbhttp.error.ERR_CONNECT['desc']:
                    error_string = "Could not connect to the server (%s)" % self.red.response.http_error.get('detail', "unknown")
                elif self.red.response.http_error['desc'] == nbhttp.error.ERR_URL['desc']:
                    error_string = self.red.response.http_error.get('detail', "RED can't fetch that URL.")
                elif self.red.response.http_error['desc'] == nbhttp.error.ERR_READ_TIMEOUT['desc']:
                    error_string = self.red.response.http_error['desc']
                elif self.red.response.http_error['desc'] == nbhttp.error.ERR_HTTP_VERSION['desc']:
                    error_string = "<code>%s</code> isn't HTTP." % e(self.red.response.http_error.get('detail', '')[:20])
                else:
                    raise AssertionError("Unidentified incomplete response error.")
                self.result = self._generate_error_xml(error_string).toprettyxml()
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
        
    def get_result(self):
        """
        Return result if cacheability check was finished.
        If not, return None
        @return: Result of cacheablity checker.
        """
        return str(self.result)
        
    def _get_response_document(self):
        """
        Generate response document
        @return: Root response document DOM object
        """
        doc = minidom.Document()
        rootDoc = doc.createElement("observationresponse")
        rootDoc.setAttribute("xmlns", "http://www.w3.org/2009/10/unicorn/observationresponse")
        rootDoc.setAttribute("xml:lang", "en")
        rootDoc.setAttribute("ref", self.test_uri)
        doc.appendChild(rootDoc)
        return rootDoc, doc
    
    def _output_response_header(self, doc, rootDoc):
        """
        Generate HTTP Response Header to Outputs
        """
        m = doc.createElement("message")
        m.setAttribute("type", "info")
        m.setAttribute("group", "response_header")
        title = doc.createElement("title")
        title.appendChild(doc.createTextNode("HTTP Response Header"))
        description = doc.createElement("description")
        ul = doc.createElement("ul")
        ul.setAttribute("class", "headers")
        description.appendChild(ul)
        for i in self.red.response.headers:
            li = doc.createElement("li")
            li.appendChild(doc.createTextNode(i[0] + ":" + i[1]))
            ul.appendChild(li)
        m.appendChild(title)
        m.appendChild(description)
        rootDoc.appendChild(m)
    
    def _handle_category(self, category_value):
        """
        Getting Classification key from values
        """
        category = list(_Classifications.__dict__.keys())[list(_Classifications.__dict__.values()).index(category_value)]
        self.groups.append(category)
        return str(category).lower()
    
    def _add_group_elements(self, doc, rootDoc):
        """
        Getting group informations from _Classifications class
        This implimentation is little a bit hack :)
        """
        #Header group
        h_group_element = doc.createElement("group")
        h_group_element.setAttribute("name", "response_header")
        h_title_element = doc.createElement("title")
        h_title_element.appendChild(doc.createTextNode("HTTP Response Header"))
        h_group_element.appendChild(h_title_element)
        rootDoc.appendChild(h_group_element)
        
        for k in set(self.groups):
            group_element = doc.createElement("group")
            group_element.setAttribute("name", str(k).lower())
            title_element = doc.createElement("title")
            title_text = doc.createTextNode(getattr(_Classifications, k))
            title_element.appendChild(title_text)
            group_element.appendChild(title_element)
            rootDoc.appendChild(group_element)        

    def _generate_output_xml(self, test_uri):
        """
        Generate Output XML Document
        @return: Output XML Document
        """
        rootDoc, doc = self._get_response_document()
        for i in self.red.notes:
            m = doc.createElement("message")
            m.setAttribute("type", self._convert_level(i.level))

            """
            Hack
            TODO: clean up this code
            """            
            category = self._handle_category(i.category)
            m.setAttribute("group", category)
            
            title = doc.createElement("title")
            title.appendChild(doc.createTextNode(i.summary['en'] % i.vars))
            text = "<description>" + (i.text['en'] % i.vars) + "</description>"
            try:
                text_dom = parseString(self._convert_html_tags(text))
            except:
                logging.error(text)
                text_dom = parseString("<description>Internal Error</description>")
            text_element = text_dom.getElementsByTagName("description")
            m.appendChild(title)
            m.appendChild(text_element[0])
            rootDoc.appendChild(m)
        
        self._output_response_header(doc, rootDoc)
        self._add_group_elements(doc, rootDoc)
        
        return doc
        
    def _generate_error_xml(self, error_message):
        '''
        Return Error XML Document
        @return: Error XML Document
        '''
        rootDoc, doc = self._get_response_document()
        m = doc.createElement("message")
        m.setAttribute("type", "error")
        title = doc.createElement("title")
        title.appendChild(doc.createTextNode("Checker Error"))
        text = "<description>" + error_message + "</description>"
        try:
            text_dom = parseString(self._convert_html_tags(text))
        except:
            logging.error(text)
            text_dom = parseString("<description>Internal Error</description>")
        text_element = text_dom.getElementsByTagName("description")
        m.appendChild(title)
        m.appendChild(text_element[0])
        rootDoc.appendChild(m)
        return doc
    
    def _convert_level(self, level):
        '''
        Convert verbose level string from Redbot style to unicorn style
        '''
        level = re.sub("good", "info", level)
        level = re.sub("bad", "error", level)
        return level
    
    def _convert_html_tags(self, string):
        string = re.sub("<p>", "<br />", string)
        string = re.sub("</p>", "<br />", string)
        string = re.sub("<br/>", "<br />", string)
        string = re.sub("<br>", "<br />", string)
        return string
        

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
    print(red.get_result())

if __name__ == "__main__":
    import sys
    test_uri = sys.argv[1]   
    standalone_main(test_uri)

