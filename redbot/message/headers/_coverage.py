
import sys
import types
import unittest
import xml.etree.ElementTree as ET
from redbot.message.headers import HeaderProcessor

def CheckCoverage(xml_file):
    """
    Given an XML file from <https://www.iana.org/assignments/message-headers/message-headers.xml>,
    See what headers are missing and check those remaining to see what they don't define.
    """
    
    for record in ParseHeaderRegistry(xml_file):
      CheckHeaderModule(record)


def CheckHeaderModule(header_name):
    """
    Given a module and its name, make sure it's complete. Complain on STDERR if not.
    """
  
    header_mod = HeaderProcessor.find_header_module(header_name)
    if not header_mod:
#      sys.stderr.write("- %s registered but can't find module\n" % header_name)
      return
    header_obj = HeaderProcessor.find_header_handler(header_name, default=False)
    if not header_obj:
      sys.stderr.write("- %s found module but not object\n" % header_name)
      return
    
    attrs = dir(header_obj)
    checks = [
      ('canonical_name', types.UnicodeType),
      ('reference', types.UnicodeType),
      ('description', types.UnicodeType),
      ('valid_in_requests', types.BooleanType),
      ('valid_in_responses', types.BooleanType),
      ('syntax', types.StringType),
      ('list_header', types.BooleanType),
      ('deprecated', types.BooleanType),
    ]
    for (attr_name, attr_type) in checks:
      attr_value = getattr(header_obj, attr_name)
      if getattr(header_obj, "no_coverage") and attr_name in ['syntax']:
        continue
      if attr_name in ['syntax'] and attr_value == False:
        continue
      if attr_value == None:    
          sys.stderr.write("* %s lacks %s\n" % (header_name, attr_name))
      elif type(attr_value) != attr_type:
        sys.stderr.write("* %s %s has wrong type\n" % (header_name, attr_name))

    canonical_name = getattr(header_obj, "canonical_name")
    if canonical_name != header_name:
      sys.stderr.write("* %s has mismatching canonical name %s\n" % (header_name, canonical_name))

    loader = unittest.TestLoader()
    tests = loader.loadTestsFromModule(header_mod)
    if tests.countTestCases() == 0 and getattr(header_obj, "no_coverage") == False: 
        sys.stderr.write("* %s doesn't have any tests\n" % header_name)


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
