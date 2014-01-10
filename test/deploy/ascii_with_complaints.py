"""
'ascii' codec, plus warnings. Suitable for use as the default encoding in
`site.py`.
Copyright Allen Short, 2010.

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


Based on ASCII codec from Python 2.7, made available under the Python license
(http://docs.python.org/license.html):

 Copyright (c) 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010
Python Software Foundation; All Rights Reserved

 Python 'ascii' Codec


Written by Marc-Andre Lemburg (mal@lemburg.com).

(c) Copyright CNRI, All Rights Reserved. NO WARRANTY.

"""
import codecs, warnings

def encode(input, errors='strict'):
    warnings.warn("Implicit conversion of unicode to str", UnicodeWarning, 2)
    return codecs.ascii_encode(input, errors)


def decode(input, errors='strict'):
#    warnings.warn("Implicit conversion of str to unicode", UnicodeWarning, 2)
    return codecs.ascii_decode(input, errors)



class Codec(codecs.Codec):

    def encode(self, input,errors='strict'):
        return encode(input,errors)
    def decode(self, input,errors='strict'):
        return decode(input,errors)


class IncrementalEncoder(codecs.IncrementalEncoder):
    def encode(self, input, final=False):
        return encode(input, self.errors)[0]

class IncrementalDecoder(codecs.IncrementalDecoder):
    def decode(self, input, final=False):
        return decode(input, self.errors)[0]

class StreamWriter(Codec,codecs.StreamWriter):
    pass

class StreamReader(Codec,codecs.StreamReader):
    pass


### encodings module API

def getregentry():
    return codecs.CodecInfo(
        name='ascii_with_complaints',
        encode=encode,
        decode=decode,
        incrementalencoder=IncrementalEncoder,
        incrementaldecoder=IncrementalDecoder,
        streamwriter=StreamWriter,
        streamreader=StreamReader,
    )

def search_function(encoding):
    if encoding == 'ascii_with_complaints':
        return getregentry()

codecs.register(search_function)
