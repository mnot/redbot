
import os
import sys
import types
import unittest
import xml.etree.ElementTree as ET
from redbot.message.headers import HeaderProcessor, HttpHeader
from redbot.syntax.rfc7230 import list_rule


def CheckRegistryCoverage(xml_file):
    """
    Given an XML file from <https://www.iana.org/assignments/message-headers/message-headers.xml>,
    See what headers are missing and check those remaining to see what they don't define.
    """
    for header_name in ParseHeaderRegistry(xml_file):
        header_mod = HeaderProcessor.find_header_module(header_name)
        if not header_mod:
            sys.stderr.write("- %s registered but can't find module\n" % header_name)


def ParseHeaderRegistry(xml_file):
    """
    Given a filename containing XML, parse it and return a list of registered header names.
    """

    tree = ET.parse(xml_file)
    root = tree.getroot()
    result = []
    for record in root.iter('{http://www.iana.org/assignments}record'):
        if record.find('{http://www.iana.org/assignments}protocol').text.lower().strip() != "http":
            continue
        result.append(record.find('{http://www.iana.org/assignments}value').text)
    return result


def CheckHeaderDefinitions():
    """
    Return a list of all subclasses of HttpHeader.
    """
    LoadAllHeaders('../redbot/message/headers/')
    for header_class in HttpHeader.__subclasses__():
        CheckHeaderModule(header_class)
    

def LoadAllHeaders(header_dir):
    """
    Load all headers.
    """
    for root, dirs, files in os.walk(header_dir):
        for name in files:
            if name[0] == "_":
                continue
            base, ext = os.path.splitext(name)
            if ext != '.py':
                continue
            module_name = "redbot.message.headers.%s" % base
            __import__(module_name)


def CheckHeaderModule(header_cls):
    """
    Given a header class, make sure it's complete. Complain on STDERR if not.
    """

    header_name = getattr(header_cls, 'canonical_name') or header_cls.__name__
    attrs = dir(header_cls)
    checks = [
        ('canonical_name', [str], True),
        ('reference', [str], True),
        ('description', [str], True),
        ('valid_in_requests', [bool], True),
        ('valid_in_responses', [bool], True),
        ('syntax', [str, list_rule], True),
        ('list_header', [bool], True),
        ('deprecated', [bool], False),
    ]
    for (attr_name, attr_types, attr_required) in checks:
        attr_value = getattr(header_cls, attr_name)
        if getattr(header_cls, "no_coverage") and attr_name in ['syntax']:
            continue
        if attr_name in ['syntax'] and attr_value == False:
            continue
        if attr_required and attr_value == None:
            sys.stderr.write("* %s lacks %s\n" % (header_name, attr_name))
        elif True not in [isinstance(attr_value, t) for t in attr_types]:
            sys.stderr.write("* %s %s has wrong type\n" % (header_name, attr_name))

    canonical_name = getattr(header_cls, "canonical_name")
    if canonical_name != header_name:
        sys.stderr.write("* %s has mismatching canonical name %s\n" % (header_name, canonical_name))

# FIXME: check tests.
#    loader = unittest.TestLoader()
#    tests = loader.loadTestsFromModule(header_mod)
#    if tests.countTestCases() == 0 and getattr(header_obj, "no_coverage") == False:
#        sys.stderr.write("* %s doesn't have any tests\n" % header_name)




if __name__ == "__main__":
    CheckRegistryCoverage(sys.argv[1])
    CheckHeaderDefinitions()
