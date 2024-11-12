"""
This is adapted from xml.etree.ElementTree.XMLParser.

We adapt the official code here mainly because, the official XMLParser do not
maintain a source map between the xml source and xml elements.

Since from Python 3.3, the official XMLParser turns to use a fast implementation
whenever available, we're not able to subclass XMLParser and override XMLParser's
internal functions to add additional functionalities. So we have to copy the slow
implementation (i.e., the pythonic implementation) here and use the slow one back.
"""

# ---------------------------------------------------------------------
# Licensed to PSF under a Contributor Agreement.
# See https://www.python.org/psf/license for licensing details.
#
# ElementTree
# Copyright (c) 1999-2008 by Fredrik Lundh.  All rights reserved.
#
# fredrik@pythonware.com
# http://www.pythonware.com
# --------------------------------------------------------------------
# The ElementTree toolkit is
#
# Copyright (c) 1999-2008 by Fredrik Lundh
#
# By obtaining, using, and/or copying this software and/or its
# associated documentation, you agree that you have read, understood,
# and will comply with the following terms and conditions:
#
# Permission to use, copy, modify, and distribute this software and
# its associated documentation for any purpose and without fee is
# hereby granted, provided that the above copyright notice appears in
# all copies, and that both that copyright notice and this permission
# notice appear in supporting documentation, and that the name of
# Secret Labs AB or the author not be used in advertising or publicity
# pertaining to distribution of the software without specific, written
# prior permission.
#
# SECRET LABS AB AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD
# TO THIS SOFTWARE, INCLUDING ALL IMPLIED WARRANTIES OF MERCHANT-
# ABILITY AND FITNESS.  IN NO EVENT SHALL SECRET LABS AB OR THE AUTHOR
# BE LIABLE FOR ANY SPECIAL, INDIRECT OR CONSEQUENTIAL DAMAGES OR ANY
# DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS,
# WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS
# ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE
# OF THIS SOFTWARE.
# --------------------------------------------------------------------

import warnings
from xml.etree import ElementTree


class XMLParser:
    """Element structure builder for XML source data based on the expat parser.

    *target* is an optional target object which defaults to an instance of the
    standard TreeBuilder class, *encoding* is an optional encoding string
    which if given, overrides the encoding specified in the XML file:
    http://www.iana.org/assignments/character-sets

    """

    def __init__(self, *, target=None, encoding=None):
        try:
            from xml.parsers import expat
        except ImportError:
            try:
                import pyexpat as expat
            except ImportError:
                raise ImportError(
                    "No module named expat; use SimpleXMLTreeBuilder instead"
                )
        parser = expat.ParserCreate(encoding, "}")
        if target is None:
            target = ElementTree.TreeBuilder()
        # underscored names are provided for compatibility only
        self.parser = self._parser = parser
        self.target = self._target = target
        self._error = expat.error
        self._names = {}  # name memo cache
        # main callbacks
        parser.DefaultHandlerExpand = self._default
        if hasattr(target, "start"):
            parser.StartElementHandler = self._start
        if hasattr(target, "end"):
            parser.EndElementHandler = self._end
        if hasattr(target, "start_ns"):
            parser.StartNamespaceDeclHandler = self._start_ns
        if hasattr(target, "end_ns"):
            parser.EndNamespaceDeclHandler = self._end_ns
        if hasattr(target, "data"):
            parser.CharacterDataHandler = target.data
        # miscellaneous callbacks
        if hasattr(target, "comment"):
            parser.CommentHandler = target.comment
        if hasattr(target, "pi"):
            parser.ProcessingInstructionHandler = target.pi
        # Configure pyexpat: buffering, new-style attribute handling.
        parser.buffer_text = 1
        parser.ordered_attributes = 1
        self._doctype = None
        self.entity = {}
        try:
            self.version = "Expat %d.%d.%d" % expat.version_info
        except AttributeError:
            pass  # unknown

    def _setevents(self, events_queue, events_to_report):
        # Internal API for XMLPullParser
        # events_to_report: a list of events to report during parsing (same as
        # the *events* of XMLPullParser's constructor.
        # events_queue: a list of actual parsing events that will be populated
        # by the underlying parser.
        #
        parser = self._parser
        append = events_queue.append
        for event_name in events_to_report:
            if event_name == "start":
                parser.ordered_attributes = 1

                def handler(
                    tag, attrib_in, event=event_name, append=append, start=self._start
                ):
                    append((event, start(tag, attrib_in)))

                parser.StartElementHandler = handler
            elif event_name == "end":

                def handler(tag, event=event_name, append=append, end=self._end):
                    append((event, end(tag)))

                parser.EndElementHandler = handler
            elif event_name == "start-ns":
                # TreeBuilder does not implement .start_ns()
                if hasattr(self.target, "start_ns"):

                    def handler(
                        prefix,
                        uri,
                        event=event_name,
                        append=append,
                        start_ns=self._start_ns,
                    ):
                        append((event, start_ns(prefix, uri)))
                else:

                    def handler(prefix, uri, event=event_name, append=append):
                        append((event, (prefix or "", uri or "")))

                parser.StartNamespaceDeclHandler = handler
            elif event_name == "end-ns":
                # TreeBuilder does not implement .end_ns()
                if hasattr(self.target, "end_ns"):

                    def handler(
                        prefix, event=event_name, append=append, end_ns=self._end_ns
                    ):
                        append((event, end_ns(prefix)))
                else:

                    def handler(prefix, event=event_name, append=append):
                        append((event, None))

                parser.EndNamespaceDeclHandler = handler
            elif event_name == "comment":

                def handler(text, event=event_name, append=append, self=self):
                    append((event, self.target.comment(text)))

                parser.CommentHandler = handler
            elif event_name == "pi":

                def handler(
                    pi_target, data, event=event_name, append=append, self=self
                ):
                    append((event, self.target.pi(pi_target, data)))

                parser.ProcessingInstructionHandler = handler
            else:
                raise ValueError("unknown event %r" % event_name)

    def _raiseerror(self, value):
        err = ElementTree.ParseError(value)
        err.code = value.code
        err.position = value.lineno, value.offset
        raise err

    def _fixname(self, key):
        # expand qname, and convert name string to ascii, if possible
        try:
            name = self._names[key]
        except KeyError:
            name = key
            if "}" in name:
                name = "{" + name
            self._names[key] = name
        return name

    def _start_ns(self, prefix, uri):
        return self.target.start_ns(prefix or "", uri or "")

    def _end_ns(self, prefix):
        return self.target.end_ns(prefix or "")

    def _start(self, tag, attr_list):
        # Handler for expat's StartElementHandler. Since ordered_attributes
        # is set, the attributes are reported as a list of alternating
        # attribute name,value.
        fixname = self._fixname
        tag = fixname(tag)
        attrib = {}
        if attr_list:
            for i in range(0, len(attr_list), 2):
                attrib[fixname(attr_list[i])] = attr_list[i + 1]
        attrib["start_point"] = (
            self.parser.CurrentLineNumber,
            self.parser.CurrentColumnNumber,
        )
        attrib["start_byte_index"] = self.parser.CurrentByteIndex
        return self.target.start(tag, attrib)

    def _end(self, tag):
        elem = self.target.end(self._fixname(tag))
        # noinspection PyTypeChecker
        elem.attrib["end_point"] = (
            self.parser.CurrentLineNumber,
            self.parser.CurrentColumnNumber,
        )
        # noinspection PyTypeChecker
        elem.attrib["start_byte_index"] = self.parser.CurrentByteIndex
        return elem

    def _default(self, text):
        prefix = text[:1]
        if prefix == "&":
            # deal with undefined entities
            try:
                data_handler = self.target.data
            except AttributeError:
                return
            try:
                data_handler(self.entity[text[1:-1]])
            except KeyError:
                from xml.parsers import expat

                err = expat.error(
                    "undefined entity %s: line %d, column %d"
                    % (text, self.parser.ErrorLineNumber, self.parser.ErrorColumnNumber)
                )
                err.code = 11  # XML_ERROR_UNDEFINED_ENTITY
                err.lineno = self.parser.ErrorLineNumber
                err.offset = self.parser.ErrorColumnNumber
                raise err
        elif prefix == "<" and text[:9] == "<!DOCTYPE":
            self._doctype = []  # inside a doctype declaration
        elif self._doctype is not None:
            # parse doctype contents
            if prefix == ">":
                self._doctype = None
                return
            text = text.strip()
            if not text:
                return
            self._doctype.append(text)
            n = len(self._doctype)
            if n > 2:
                type = self._doctype[1]
                if type == "PUBLIC" and n == 4:
                    name, type, pubid, system = self._doctype
                    if pubid:
                        pubid = pubid[1:-1]
                elif type == "SYSTEM" and n == 3:
                    name, type, system = self._doctype
                    pubid = None
                else:
                    return
                if hasattr(self.target, "doctype"):
                    self.target.doctype(name, pubid, system[1:-1])
                elif hasattr(self, "doctype"):
                    warnings.warn(
                        "The doctype() method of XMLParser is ignored.  "
                        "Define doctype() method on the TreeBuilder target.",
                        RuntimeWarning,
                    )

                self._doctype = None

    def feed(self, data):
        """Feed encoded data to parser."""
        try:
            self.parser.Parse(data, False)
        except self._error as v:
            self._raiseerror(v)

    def close(self):
        """Finish feeding data to parser and return element structure."""
        try:
            self.parser.Parse(b"", True)  # end of data
        except self._error as v:
            self._raiseerror(v)
        try:
            close_handler = self.target.close
        except AttributeError:
            pass
        else:
            return close_handler()
        finally:
            # get rid of circular references
            del self.parser, self._parser
            del self.target, self._target


SlowXMLParser = XMLParser
