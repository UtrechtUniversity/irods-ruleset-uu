#!/usr/bin/env python3

import json
import sys
import xml.etree.cElementTree as ET

from urllib.parse import urlparse, urljoin # Not yet used, but will be needed
                                           # when resolving cross-document JSON
                                           # schema references.
from collections  import OrderedDict
from copy         import deepcopy
from functools    import reduce
from operator     import add
from argparse     import ArgumentParser

import traceback
import functools

def gentleAssert(predicate,
                 message,
                 fragment=None,
                 refName=None,
                 propertyName=None,
                 typeName=None,
                 trace=False):
    """
    Check a predicate and exit if it is false.
    The given message will be printed on failure, including a bit of context
    when one the relevant optional arguments are given (e.g. refName).

    When 'trace' is true, a full stack trace will be printed as well
    (this argument is forced to True by the '--trace' commandline flag).
    """
    if predicate:
        return # yay!

    stack = traceback.extract_stack(None)[:-1]

    print("Assertion failed at %s line %d:\n> %s\n"
          % (stack[-1].filename,
             stack[-1].lineno,
             message),
          file=sys.stderr)

    if fragment is not None:
        print('The error occurred while processing JSON fragment "%s"' % fragment, file=sys.stderr)
    elif refName is not None:
        print('The error occurred while resolving a JSON schema $ref.\nThe (partial or complete) URI was "%s"' % refName, file=sys.stderr)
    elif propertyName is not None:
        print('The error occurred while processing JSON property "%s"' % propertyName, file=sys.stderr)
    elif typeName is not None:
        print('The error occurred while processing or generating a type named "%s"' % typeName, file=sys.stderr)
    else:
        print('No further context is available.\nPlease consult the Python code at the line number printed above if you require more information.', file=sys.stderr)

    if not trace:
        print('\nYou may pass \'-t\' to this script to print a stack trace at the failing assertion.', file=sys.stderr)

    if trace:
        print('\nA complete stack trace follows:\n', file=sys.stderr)
        print(*traceback.format_stack(None), file=sys.stderr)

    sys.exit(1)

def flattenSchema(jsonDocument, uri):
    """
    Given a dict representing a JSON schema object, resolve all contained $ref
    objects into references to actual Python objects.

    Only references within the same document are supported for now.
    """
    jsonDocument = deepcopy(jsonDocument) # Return a flattened schema, do not modify the input.
    documents = dict() # URL(?) => JSON document object
    #documents.add(uri)

    def resolvePath(doc, *path):
        if len(path) != 0:
            gentleAssert(path[0] in doc,
                         'Could not resolve a $ref fragment. Please verify that the referenced type exists and is referenced with the correct name.',
                         refName='/'.join(path))
        return doc if len(path) == 0 else resolvePath(doc[path[0]], *path[1:])

    def flattenDocument(doc, uri):
        """Flatten the references for a single JSON document"""

        def flattenObject(el, fragment):
            """Flatten the references for a single JSON element"""

            def resolve(uri):
                """Resolve an URI (based on the current fragment)"""

                gentleAssert(uri.startswith('#/'),
                             'Only absolute references within the current document allowed for now',
                             refName=uri)

                return resolvePath(doc, *uri[2:].split('/'))

            if isinstance(el, dict):
                if '$ref' in el:
                    # Resolve that reference.
                    el = resolve(el['$ref'])
                else:
                    # Nothing to see here, move on.
                    for k, v in el.items():
                        el[k] = flattenObject(v, fragment)
            elif isinstance(el, list):
                for i, v in enumerate(el):
                    el[i] = flattenObject(v, fragment)

            return el
        return flattenObject(doc, '/')
    return flattenDocument(jsonDocument, uri)


def getTypes(obj):
    """
    Extract the type declarations from a JSON schema object.
    """
    return obj['definitions'] if 'definitions' in obj else {}

def El(tag, attrs=None, *children):
    """
    Construct an XML element with the given optional attributes and optional children.
    """
    el = ET.Element(tag, attrs if attrs is not None else {})
    el.extend(children)
    return el

def annotateTypes(jsonDocument):
    """
    Annotate type declaration structures with the key (typename) pointing to them.
    This ensures that elements that reference a type through $ref also know the type's name.
    """
    jsonDocument = deepcopy(jsonDocument)
    for k, v in getTypes(jsonDocument).items():
        gentleAssert(isinstance(v, dict),
                     'JSON Schema \'definitions\' type declaration must be an object',
                     typeName=k)
        v.jsosd_typename = k
    return jsonDocument

def markRequiredElements(elements, required):
    """
    Annotate requiredness on elements based on the 'required' array of the parent element.

    NB: This function is removed when --no-required is passed to the script.
    """
    # Verify that the set of required elements is the same as or a
    # subset of the actual child elements (i.e. no non-existent
    # required elements).
    names = [*map(lambda x: x.get('name'), elements)]
    gentleAssert(set(required) <= set(names),
                 'One or more properties of a structure are marked required, but do not exist. The missing properties are: %s.'
                 % ', '.join(set(required) - set(names)))

    for child in filter(lambda x: x.get('name') in required, elements):
        val = child.get('minOccurs')
        if val is None or int(val) < 1:
            child.set('minOccurs', '1')

def setArrayOccurs(element, min, max):
    """
    Set the min/max occurences on an array item.

    NB: This function is wrapped to force 'min' to '0' when --no-required is
    passed to the script.
    """
    element.set('minOccurs', min)
    element.set('maxOccurs', max)

def setDefaultOccurs(element):
    # Set min/max occurrences, if unset.
    if  element.get('minOccurs') is not None and element.get('maxOccurs') is None:
        element.set('maxOccurs', 'unbounded')
    if  element.get('minOccurs') is None:
        element.set('minOccurs', '0')
    if  element.get('maxOccurs') is None:
        element.set('maxOccurs', '1')

def convertType(body, typename=None):
    """
    Generate a type.
    """
    v = body # XXX

    if 'jsosd_typename' in dir(body) and typename is None:
        # Return an element of this type.
        return [El('xs:element',
                   {'name': fieldname, 'type': v.jsosd_typename})]

    gentleAssert('type' in v,
                 'All elements and types must contain a \'type\' attribute.',
                 typeName=typename)

    typ = None # The generated type, either a string (name), or an element describing the type.

    if 'yoda:structure' in v:
        # Handle compounds and subproperties.

        gentleAssert(v['type'] == 'object',
                     'Compounds and subproperties types must have \'type\' attribute \'object\'',
                     typeName=typename)
        gentleAssert(v['yoda:structure'] in ('compound', 'subproperties'),
                     'Invalid \'yoda:structure\' value "%s"' % v['yoda:structure'],
                     typeName=typename)
        gentleAssert('properties' in v and isinstance(v['properties'], dict),
                     'Compounds and subproperties types must have \'properties\' object',
                     typeName=typename)

        # Convert child properties.
        subs = reduce(add, [convertProperty(k, v) for k, v in v['properties'].items()], [])

        # Annotate requiredness.
        if 'required' in v:
            markRequiredElements(subs, v['required'])

        if v['yoda:structure'] == 'subproperties':
            # Splice off the main property.
            main, subs = subs[0], subs[1:]

        typ = El('xs:complexType',
                 {} if typename is None else {'name': typename},
                 # Subproperties case:
                 (El('xs:sequence', {},
                     main,
                     El('xs:element', {'name': 'Properties',
                                       'minOccurs': '0',#'1',
                                       'maxOccurs': '1'},
                        El('xs:complexType', {},
                           El('xs:sequence', {}, *subs))))
                  if v['yoda:structure'] == 'subproperties' else
                  # Compound case:
                  El('xs:sequence', {}, *subs)))

    elif 'enum' in v:
        gentleAssert(isinstance(v['enum'], list),
                     'Enum types must have a list attribute named \'enum\'',
                     typeName=typename)

        # Type should be string, or the like.
        gentleAssert(v['type'] in builtinTypes(),
                     'The \'type\' of enums must be a builtin type (got "%s" instead)' % v['type'],
                     typeName=typename)
        enumType = (convertBuiltinType(v['type'], v['format'] if 'format' in v else None)
                    if v['type'] in builtinTypes() else v['type'])

        typ = El('xs:simpleType',
                 {} if typename is None else {'name': typename},
                 El('xs:restriction', {'base': enumType},
                    # Turn the possible enum values into xs:enumeration tags.
                    *map(lambda val: El('xs:enumeration', {'value': val}),
                         v['enum'])))

    elif v['type'] in builtinTypes():
        # Simple builtin type.
        typ = convertBuiltinType(v['type'], v['format'] if 'format' in v else None)

    else:
        gentleAssert(False,
                     'Unknown type name "%s". (if you are trying to reference a user-defined type in \'definitions\', use a $ref attribute instead)' % v['type'],
                     typeName=typename)

    # Handle extra inline restrictions.
    if len(set(['maxLength']) & set(v.keys())):
        # Only allow extra restrictions if the base type can be specified by name.
        gentleAssert(isinstance(typ, str),
                     'Restrictions (such as \'maxLength\') can only be added when the base type can be specified by name',
                     typeName=typename)

        restriction = El('xs:restriction',
                         {'base': typ})
        if 'maxLength' in v:
            restriction.append(El('xs:maxLength',
                                  {'value': str(v['maxLength'])}))
        typ = El('xs:simpleType',
                 {} if typename is None else {'name': typename},
                 restriction)

    if typename is None:
        return typ
    else:
        if isinstance(typ, str):
            # We are declaring a type, so we are forced to create a type element.
            return El('xs:simpleType',
                      {'name': typename},
                      El('xs:restriction',
                         {'base': typ}))
        else:
            return typ

def convertProperty(name, body, topLevel = False):

    gentleAssert('type' in body,
                 'All properties must contain a \'type\' attribute.',
                 propertyName=name)

    if topLevel:
        # Toplevel properties always indicate grouping.
        # This level is not emitted in the XSD, so as a special case here we
        # immediately generate the child elements and return them.
        gentleAssert(body['type'] == 'object',
                     'Toplevel properties must have type \'object\'',
                     propertyName=name)

        subs = reduce(add, [convertProperty(k, v) for k, v in body['properties'].items()], [])

        if 'required' in body:
            markRequiredElements(subs, body['required'])

        # Return the child properties directly.
        return subs

    # Process a single property, and any child properties it may have.

    if 'jsosd_typename' in dir(body):
        # This property is a reference to an existing type.
        # The type can be simply named in a 'type' attribute.
        el = El('xs:element',
                {'name': name, 'type': body.jsosd_typename})

    else:
        # The type is specified by name (without using a reference), and
        # possible extra restrictions (e.g. maxLength) may be applied.

        if body['type'] == 'array':
            # Repeated element.

            gentleAssert(isinstance(body['items'], dict),
                         'Attribute \'items\' of an \'array\'-type property must be an object (JSON Schema "tuple" type is not supported)',
                         propertyName=name)

            # Delegate to convertProperty of the single child element.
            el = convertProperty(name, body['items'])
            gentleAssert(len(el) == 1, # There should be just one item.
                         'Internal logic error, this should not happen.',
                         propertyName=name)
            el = el[0]

            # Check min/max occurrences and annotate.
            setArrayOccurs(el,
                           str(body['minItems']) if 'minItems' in body else '0',
                           str(body['maxItems']) if 'maxItems' in body else 'unbounded')

        else:
            typ = convertType(body)
            if isinstance(typ, str):
                el = El('xs:element',
                        {'name': name, 'type': typ})
            else:
                el = El('xs:element',
                        {'name': name},
                        typ)

    setDefaultOccurs(el)

    return [el]


def builtinTypes():
    return {'string':  'xs:string',
            'integer': 'xs:integer',
            'number':  'xs:decimal',
            'uri':     'xs:anyURI'}

def convertBuiltinType(name, fmt):
    gentleAssert(name in builtinTypes(),
                 'Type "%s" is not a built-in type' % name)
    # Special cases for string types with certain 'format' values.
    if name == 'string' and fmt == 'date':
        return 'xs:date'
    else:
        return builtinTypes()[name]

def generateSystemGroup():
    system = ET.XML("""<?xml version="1.0" encoding="utf-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" elementFormDefault="qualified">
<xs:element name="System" minOccurs="0" maxOccurs="1">
  <xs:complexType>
    <xs:sequence>
      <xs:element name="Last_Modified_Date" type="xs:date" minOccurs="0" maxOccurs="1"/>
      <xs:element name="Persistent_Identifier_Datapackage" minOccurs="0" maxOccurs="unbounded">
        <xs:complexType>
          <xs:sequence>
            <xs:element name="Identifier_Scheme" type="optionsPersistentIdentifierScheme" minOccurs="0" maxOccurs="1"/>
            <xs:element name="Identifier" type="stringNormal" minOccurs="0" maxOccurs="1"/>
          </xs:sequence>
        </xs:complexType>
      </xs:element>
      <xs:element name="Publication_Date" type="xs:date" minOccurs="0" maxOccurs="1"/>
      <xs:element name="Open_Access_Link" type="xs:anyURI" minOccurs="0" maxOccurs="1"/>
      <xs:element name="License_URI" type="xs:anyURI" minOccurs="0" maxOccurs="1"/>
    </xs:sequence>
  </xs:complexType>
</xs:element>
</xs:schema>
""")

    return system.findall('*')[0]


if __name__ == '__main__':
    # Process arguments {{{

    argparse = ArgumentParser(description=
            """Converts JSON schema into a Yoda metadata XSD and XML form elements.

               Unless specified otherwise with arguments, this will accept JSON on stdin
               and output XSD on stdout.
            """)
    argparse.add_argument('-o', '--output',   help='An output file (by default, prints to stdout)')
    argparse.add_argument('input', nargs='?', help='An input file (by default, reads from stdin)')
    argparse.add_argument('--required',    action='store_true',  dest='required', default=True)
    argparse.add_argument('--no-required', action='store_false', dest='required',
                          help='Enables or disables the processing of the \'required\' attribute.'
                              +' \'--required\' is ON by default.')
    argparse.add_argument('-t', '--trace', action='store_true', default=False,
                          help='Enables full stack traces on assertion failures. This may aid in debugging schemas or the script itself when the printed error information is not sufficient.')
    args = argparse.parse_args()

    # Open input / output files.

    file_in  = sys.stdin  if args.input  is None else open(args.input)
    file_out = sys.stdout if args.output is None else open(args.output, 'w')

    if not args.required:
        # Disable 'required' handling.
        markRequiredElements = lambda *_: None

        # Force the minimum occurrences for array items to always be '0'.
        f = setArrayOccurs
        setArrayOccurs = lambda array, min, max: f(array, '0', max)

    if args.trace:
        # Change gentleAssert to print a trace by default.
        gentleAssert = functools.partial(gentleAssert, trace=True)

    # }}}

    # Parse and preprocess the JSON schema document, resolving all references.
    # This also embeds 'definitions' type names into their own type objects, such
    # that all type $refs can be easily converted to type names.

    jsonDocument = flattenSchema(annotateTypes(json.load(file_in, object_pairs_hook=OrderedDict)),
                      'XXX.json')

    #print(json.dumps(jsonDocument, indent=2))
    #sys.exit(0)

    # Sanity check.
    gentleAssert('type'       in jsonDocument and jsonDocument['type'] == 'object',
                 'The \'type\' of the toplevel JSON schema object must be \'object\'')
    gentleAssert('properties' in jsonDocument and isinstance(jsonDocument['properties'], dict),
                 'The toplevel JSON schema object must contain a \'properties\' object')

    # Generate the toplevel XML schema element.

    root = ET.fromstring('<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"'
                         + ' elementFormDefault="qualified"></xs:schema>')

    # Convert and insert all fields into the XSD.

    root.append(El('xs:element',
                   {'name': 'metadata'},
                   El('xs:complexType', {},
                      El('xs:sequence', {},
                         *reduce(add, (convertProperty(k, v, topLevel=True)
                                       for k, v in jsonDocument['properties'].items())),
                         generateSystemGroup()))))

    # Generate toplevel type declaration elements.

    for t in (convertType(v, typename=k) for k, v in getTypes(jsonDocument).items()):
        root.append(t)

    # The System group depends on this type, so it must be defined.
    gentleAssert('optionsPersistentIdentifierScheme' in getTypes(jsonDocument),
                 'The System group requires a \'optionsPersistentIdentifierScheme\' type to be defined in the \'definitions\' section of the JSON schema.')

    # Print the generated XML document.

    print('<?xml version="1.0" encoding="utf-8"?>', file=file_out)
    print(ET.tostring(root, encoding='unicode'),    file=file_out)
