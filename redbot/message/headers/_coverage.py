
import sys
import types
import unittest
import xml.etree.ElementTree as ET
from redbot.message.headers import load_header_func

def CheckCoverage(xml_file):
    """
    Given an XML file from <https://www.iana.org/assignments/message-headers/message-headers.xml>,
    See what headers are missing and check those remaining to see what they don't define.
    """
    
    registered_headers = ParseHeaderRegistry(xml_file)
    for record in registered_headers:
        hdr_module = load_header_func(record)
        if not hdr_module:
            sys.stderr.write("- %s registered but not defined\n" % record)
        else:
            CheckHeaderModule(hdr_module, record)


def CheckHeaderModule(hm, name):
    """
    Given a module and its name, make sure it's complete. Complain on STDERR if not.
    """
    
    print name
    attrs = dir(hm)
    if 'reference' not in attrs or type(hm.reference) != types.StringType:
        sys.stderr.write("* %s lacks reference\n" % name)
    if 'description' not in attrs or type(hm.description) != types.StringType:
        sys.stderr.write("* %s lacks description\n" % name)
    elif hm.description.strip() == "":
        sys.stderr.write("* %s appers to have an empty description\n" % name)
    if 'parse' not in attrs or type(hm.parse) != types.FunctionType:
        sys.stderr.write("* %s lacks parse\n" % name)
    else:
        parse = getattr(hm, 'parse')
        if not getattr(parse, 'valid_msgs', None):
            sys.stderr.write("* %s doesn't know if it's for requests or responses\n" % name)
        if "deprecated" in getattr(parse, 'state', []):
            return # deprecated header, don't need to look further.
        if not hasattr(parse, 'syntaxCheck'):
            sys.stderr.write("* %s doesn't check its syntax\n" % name)
    if 'evaluate' not in attrs or type(hm.evaluate) != types.FunctionType:
        sys.stderr.write("* %s lacks evaluate\n" % name)
    loader = unittest.TestLoader()
    tests = loader.loadTestsFromModule(hm)
    if tests.countTestCases() == 0:
        sys.stderr.write("* %s doesn't have any tests\n" % name)


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


if __name__ == "__main__":
    CheckCoverage(sys.argv[1])
