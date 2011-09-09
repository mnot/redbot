#!/usr/bin/env python

"""
W3C Unicorn Formatter for REDbot.
"""
import re
from redbot.speak import _Classifications
import operator

import thor.http.error as httperr
import redbot.speak as rs
from xml.dom import minidom
from xml.dom.minidom import parseString

from redbot.formatter import Formatter

__author__ = "Hirotaka Nakajima <hiro@skyblue.me.uk>"
__copyright__ = """\
Copyright (c) 2011 World Wide Web Consortium

This code is licensed under W3C Software License.
http://www.w3.org/Consortium/Legal/2002/copyright-software-20021231 
"""
__date__ = "Sep 8, 2011"


class BaseW3CUnicornFormatter(Formatter):
    """
    Base class for unicorn formatters."""
    media_type = "application/xml"

    def __init__(self, *args, **kw):
        self.groups = []
        Formatter.__init__(self, *args, **kw)

    def start_output(self):
        pass

    def feed(self, red, chunk):
        pass

    def status(self, msg):
        pass

    def finish_output(self):
        "Fill in the template with RED's results."
        if self.red.res_complete:
            self.output(self.format_recommendations(self.red).toprettyxml())
        else:
            if self.red.res_error == None:
                pass
            elif isinstance(self.red.res_error, httperr.ConnectError):
                self.output(
                  self._generate_error_xml(
                  "Could not connect to the server (%s)" % \
                  self.red.res_error.get('detail', "unknown")
                  ).toprettyxml()
                )
            elif isinstance(self.red.res_error, httperr.UrlError):
                self.output(self._generate_error_xml(self.red.res_error.get(
                    'detail', "RED can't fetch that URL.")).toprettyxml())
            elif isinstance(self.red.res_error, httperr.ReadTimeoutError):
                self.output(self._generate_error_xml(self.red.res_error['desc']).toprettyxml())
            elif isinstance(self.red.res_error, httperr.HttpVersionError):
                self.output(
                  self._generate_error_xml("<code>%s</code> isn't HTTP." % \
                  self.red.res_error.get('detail', '')[:20]).toprettyxml()
                )
            else:
                raise AssertionError, "Unidentified incomplete response error."

    def format_recommendations(self,red):
        """
        Generate Output XML Document
        @return: Output XML Document
        """
        rootDoc, doc = self._get_response_document()
        for message in red.messages:
            m = doc.createElement("message")
            m.setAttribute("type", self._convert_level(message.level))
    
            category = self._handle_category(message.category)
            m.setAttribute("group", category)
            m.setAttribute('id',str(message.__class__))            
            title = doc.createElement("title")
            title.appendChild(doc.createTextNode(message.summary['en'] % message.vars))
            text = "<description>" + (message.text['en'] % message.vars) + "</description>"
            try:
                text_dom = parseString(self._convert_html_tags(text))
            except:
                text_dom = parseString("<description>Internal Error</description>")
            text_element = text_dom.getElementsByTagName("description")
            m.appendChild(title)
            m.appendChild(text_element[0])
            rootDoc.appendChild(m)
        
        self._output_response_header(doc, rootDoc)
        self._add_group_elements(doc, rootDoc)
        
        return doc

    def _handle_category(self, category_value):
        """
        Getting Classification key from values
        """
        category = _Classifications.__dict__.keys()[_Classifications.__dict__.values().index(category_value)]
        self.groups.append(category)
        return str(category).lower()

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

    def _output_response_header(self, doc, rootDoc):
        """
        Generate HTTP Response Header to Outputs
        """

        m = doc.createElement("message")
        m.setAttribute("type", "info")
        m.setAttribute("group", "response_header")
        m.setAttribute('id','redbot.speak.RESPONSE_HEADER')
        title = doc.createElement("title")
        title.appendChild(doc.createTextNode("HTTP Response Header"))
        description = doc.createElement("description")
        ul = doc.createElement("ul")
        ul.setAttribute("class", "headers")
        description.appendChild(ul)
        for i in self.red.res_hdrs:
            li = doc.createElement("li")
            li.appendChild(doc.createTextNode(i[0] + ":" + i[1]))
            ul.appendChild(li)
        m.appendChild(title)
        m.appendChild(description)
        rootDoc.appendChild(m)
        
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
            text_dom = parseString("<description>Internal Error</description>")
        text_element = text_dom.getElementsByTagName("description")
        m.appendChild(title)
        m.appendChild(text_element[0])
        rootDoc.appendChild(m)
        return doc

    def _get_response_document(self):
        """
        Generate response document
        @return: Root response document DOM object
        """
        doc = minidom.Document()
        rootDoc = doc.createElement("observationresponse")
        rootDoc.setAttribute("xmlns", "http://www.w3.org/2009/10/unicorn/observationresponse")
        rootDoc.setAttribute("xml:lang", "en")
        rootDoc.setAttribute("ref", self.red.uri)
        doc.appendChild(rootDoc)
        return rootDoc, doc



class W3CUnicornFormatter(BaseW3CUnicornFormatter):
    """
    Format a RED object as W3C Unicorn validator output.
    """
    name = "unicorn"
    media_type = "application/xml"

    def __init__(self, *args, **kw):
        BaseW3CUnicornFormatter.__init__(self, *args, **kw)

    def finish_output(self):
        BaseW3CUnicornFormatter.finish_output(self)
        self.done()