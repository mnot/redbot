
Response Header Handlers
========================

This directory contains response header handlers for REDbot. They are in
charge of taking the values values for each header, parsing it, and setting
any header-specific messages that are appropriate.

Note that not all tests are in these files; ones that require coordination 
between several headers' values, for example, belong in a separate type of 
test (as cache testing is done, in _cache\_check.py_). This is because headers 
can come in any order, so you can't be sure that another header's value will
be available when your header parser runs.

Likewise, tests that require another request go in the _subrequests_ 
directory.


Adding New Headers
------------------

It's pretty easy to add support for new response headers into REDbot. To
start, fork the source and add a new file into this directory, whose name
corresponds to the header's name, but in all lowercase, and with special
characters (most commonly, _-_) transposed to an underscore.

For example, if your header's name is `Foo-Example`, the appropriate filename is `foo_example.py`.

If your header name doesn't work with this convention, please raise an issue in [REDbot's tracker](https://github.com/mnot/redbot/issues).

### The _parse_ Function

Each header file should define a _parse_ function. This function must take
the following parameters:

 * `subject` - the subject ID of the test, for reference in messages.
 * `value` - a header field value; see below.
 * `red` - the current RedState object.

A value is a header field values; by default, it
corresponds to a header line. For example:

    Cache-Control: foo, bar
    Cache-Control: baz
  
would be sent in as two calls to _parse_; one as "foo, bar" and one as "baz". 

The _parse_ function must return a data structure that's suitable for the
header field; it could be a dictionary, a list, an integer, a string, etc. 
Take a look at similar headers to see what data structures they use. 

_parse_ is where you set messages that are specific to a header field-value,
rather than all field-values for that header.

If parsing fails, it should return `None`.

### The _join_ function

Each header file also needs to define a _join_ function. This coalesces the
output of one or more calls to _parse_ to produce a single data structure
that represents that header's value for the HTTP message.

It takes the following parameters:

 * `subject` - the subject ID of the test, for reference in messages.
 * `values` - a list of values, returned from _parse_.
 * `red` - the current RedState object.
 
Use _join_ to set messages that need to have the entire field's composite
value, rather than just one portion. Usually, these are tests for the 
header's semantics.



### Decorators for _parse_

There are also some handy decorators in _\_\_init\_\_.py_ that help with parsing, 
including:

 * `GenericHeaderSyntax` - Splits comma-separated list values, so that  
   `values` contains a field value per item.
   
    For example, `Cache-Control: foo, bar` will get `["foo", "bar"]` if 
    _parse_ is decorated with `@GenericHeaderSyntax`.
    
    Note that this decorator can ONLY be used on headers whose syntax does
    not allow an unquoted comma to appear; for example, it cannot be used
    on the `Set-Cookie` syntax, because it allows a bare date that includes
    a comma.
 
 * `SingleFieldValue` - For use on field values that expect only one value. 
   If more than one is present, it will set a warning message, and only send
   through the last value in `values`.
   
   If used in conjunction with `@GenericHeaderSyntax`, it should come
   afterwards.
   
 * `CheckFieldSyntax` - Checks the syntax of a field against a regex; if
   it does not match, a warning message will be set, and None will be
   forcibly returned; the code in _parse_ will not be run.
   
   This decorator takes two arguments; `expression`, containing a regex, and
   `reference`, which is a URI that's used to point people to more information
   about the syntax, if there's an error.
   
   `regex` is evaluated with `re.VERBOSE`, and already has start and end
   anchors, as well as whitespace trimming; see the code for details.
   
   See _http_syntax.py_ for some handy pre-defined regexen, based upon 
   the HTTP ABNF.


### Setting Messages

_parse_ can and should set header-specific messages as appropriate. Messages
are collected in _speak.py_; see that file for details of the appropriate 
format. They are set by calling `set_message` on the `red` object that's
passed to _parse_.

`set_message` expects the following parameters:

 * `name` - the header field name
 * `messsage` - a subclass of `redbot.speak.Message` (usually, one 
   you've added)
 * Optionally, any number of keyword arguments that are passed to the
   message's strings when they're formatted. See existing messages for 
   examples.

When writing new messages, it's important to keep in mind that the `text`
field is expected to contain valid HTML; any variables you pass to it will
be escaped for you before rendering.


### Writing Tests

You can test your _parse_ function by subclassing
`redbot.message_check.headers.HeaderTest`; it expects the following class
properties:

 * `name` - the header field-name
 * `inputs` - a list of header field-values, one item per line. 
   E.g., `["foo", "foo, bar"]`
 * `expected_out` - the data structure that _parse_ should return, given
   the inputs
 * `expected_err` - a list of `redbot.speak.Message` classes that are expected
   to be set with `set_message` when parsing the inputs
    
You can create any number of tests this way; they will be run automatically 
when _tests/test\_headers.py_ is run.
