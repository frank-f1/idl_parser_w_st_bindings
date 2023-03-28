# idl_parser

[![Build Status](https://travis-ci.org/sugarsweetrobotics/idl_parser.svg?branch=master)](https://travis-ci.org/sugarsweetrobotics/idl_parser) [![Coverage Status](https://coveralls.io/repos/github/sugarsweetrobotics/idl_parser/badge.svg?branch=master)](https://coveralls.io/github/sugarsweetrobotics/idl_parser?branch=master)


## Description 

IDL to ST (structured text) converter

Converts an IDL file to matching ST (structured text) code. The ST code complies with the IEC 61131-3 standard. 

This work is based on the OMG IDL file parser (https://github.com/sugarsweetrobotics/idl_parser), a tool 
which reads IDL files and converts them into intermediate type objects. This open-source parser has been coupled with a ST code generator.

To run from a source tree, use `python3 -m idl2st4dds.createbindings %source %destination` where source should be a valid idl file and the result is written to the file specified by destination.
## Example
```
"""
    
"""
    
from idl_parser import parser
parser_ = parser.IDLParser()
idl_str = """
module my_module {
  struct Time {
    long sec;
    long usec;
  };

  typedef sequence<double> DoubleSeq;
  
  struct TimedDoubleSeq {
    Time tm;
    DoubleSeq data;
  };

  enum RETURN_VALUE {
    RETURN_OK,
    RETURN_FAILED,
  };

  interface DataGetter {
    RETURN_VALUE getData(out TimedDoubleSeq data);
  };

};
"""
    
global_module = parser_.load(idl_str)
my_module = global_module.module_by_name('my_module')
dataGetter = my_module.interface_by_name('DataGetter')
print 'DataGetter interface'
for m in dataGetter.methods:
  print '- method:'
  print '  name:', m.name
  print '  returns:', m.returns.name
  print '  arguments:'
  for a in m.arguments:
    print '    name:', a.name
    print '    type:', a.type
    print '    direction:', a.direction
    
doubleSeq = my_module.typedef_by_name('DoubleSeq')
print 'typedef %s %s' % (doubleSeq.type.name, doubleSeq.name)

timedDoubleSeq = my_module.struct_by_name('TimedDoubleSeq')
print 'TimedDoubleSeq'
for m in timedDoubleSeq.members:
  print '- member:'
  print '  name:', m.name
  print '  type:', m.type.name    
```
## How to install
    sudo pip install idl_parser

## Copyright

This project has components licensed under the following licenses:

- GPLv3
- SISL-1.4

For details, see `debian/copyright`.
