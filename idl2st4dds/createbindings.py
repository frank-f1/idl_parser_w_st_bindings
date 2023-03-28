import argparse
from asyncio import exceptions
import os
from airspeed import CachingFileLoader
from idl_parser import parser, exception


class STTemplate(object):
    """Container for the airspeed velocity templates."""

    def __init__(self):
        """Loads the various airspeed velocity templates."""
        well_known_paths = ['.', '/usr/share/idl2st/']
        found_templates = False
        for wkp in well_known_paths:
            full_path = os.path.join(wkp, "templates")
            if not os.path.isdir(full_path):
                continue
            self.loader = CachingFileLoader(full_path, True)
            self.declare = self.loader.load_template("declare_struct.txt")
            self.type_support = self.loader.load_template("type_support.txt")
            self.init_struct = self.loader.load_template("init_struct.txt")
            self.program = self.loader.load_template("program.txt")
            found_templates = True
        if not found_templates:
            msg = "The folder with the Airspeed templates seems to be missing"
            raise exception.IDLCanNotFindException(0, 0, msg)


def get_string_size(type):
    n = ""
    """Extract the string length; could be more elegant...."""
    if type.startswith("string"):
        n = type.strip("string<>")
        if n.isnumeric():
            return f"[{str(n)}]"
    return ""


def to_Type_Enum(_type):
    """maps an IDL type to a ST type and its matching DDS type code"""
    if _type.is_primitive:
        type = _type.name.lower()
    elif _type.is_enum:
        return _type.name, "DDS_TK_ENUM"  # we return the enums name
    elif _type.is_typedef:
        return _type.full_path, "DDS_TK_ALIAS"
    elif _type.is_array:
        # Get the array size and the type
        if _type.inner_type.is_primitive:
            idl_type, _ = to_Type_Enum(_type.inner_type)
        else:
            idl_type, _ = to_Type_Enum(_type.inner_type.obj)
        return (
            f'ARRAY [1..{str(_type.size)}] OF {idl_type}', 
            "DDS_TK_ALIAS",
        )
    elif _type.is_struct:
        # A compound data type that contains pairs of tags and values , where
        # the values can be of any data type.
        return "STRUCT", "DDS_TK_STRUCT"
    if type == "boolean":
        # The boolean data type is used to denote a data item that can only
        # take one of the values TRUE and FALSE.
        return "BOOL", "DDS_TK_BOOLEAN"
    if type == "char":
        # IDL defines a char data type that is an 8-bit quantity that (1)
        # encodes a single-byte character from any byte-oriented
        # code set, or (2) when used in an array, encodes a multi-byte
        # character from a multi-byte code set.
        return "CHAR", "DDS_TK_CHAR"
    elif type == "int8":
        # A 8-bit signed integer ranging from –128 to 127
        return "SINT", "DDS_TK_INT8"
    elif type == "short" or type == "int16":
        # A 16-bit short signed integer ranging from –32,768 to +32,767.
        return "INT", "DDS_TK_SHORT"
    elif type == "long" or type == "int32":
        # A 32-bit long signed integer
        return "DINT", "DDS_TK_LONG"
    elif type == "long long" or type == "int64":
        # A signed integer in the range of -2^63… 2^63 - 1
        return "LINT", "DDS_TK_LONGLONG"
    elif type == "float":
        # A 32-bit, single-precision, floating-point numbe
        return "REAL", "DDS_TK_FLOAT"
    elif type == "double":
        # A 32-bit, single-precision, floating-point numbe
        return "LREAL", "DDS_TK_DOUBLE"
    elif type == "long double":
        # The long double data type represents an IEEE double-extended
        # floating-point number, which has an exponent of at least 15 bits in
        # length and a signed fraction of at least 64 bits.
        return "LREAL", "DDS_TK_LONGDOUBLE"
    elif type == "unsigned short" or type == "uint16":
        # A 16-bit short unsigned integer ranging from 0 to ...
        return "UINT", "DDS_TK_USHORT"
    elif type == "uint8":
        # A 8-bit signed integer ranging from –128 to 127
        return "USINT", "DDS_TK_OCTET"
    elif type == "unsigned long" or type == "uint32":
        # A 32-bit long unsigned integer
        return "UDINT", "DDS_TK_ULONG" or type == "uint64"
    elif type == "unsigned long long":
        # A unsigned integer in the range of 0… 2^64 - 1
        return "ULINT", "DDS_TK_ULONGLONG"
    elif type.startswith("string"):
        # A sequence of characters
        return "STRING" + get_string_size(type), "DDS_TK_STRING"
    elif type == "structure":
        # A compound data type that contains pairs of tags and values , where
        # the values can be of any data type.
        return "STRUCT", "DDS_TK_STRUCT"
    elif type == "octet":
        return "BYTE", "DDS_TK_OCTET"
    elif type == "wchar":
        return "WCHAR", "DDS_TK_WCHAR "
    else:
        # wstring
        # templates
        # sequences
        # void
        raise exception.InvalidDataTypeException
    raise exception.IDLParserException(0, 0, "Unsupported data type " + _type)


def is_int(st_type):
    l = ["CHAR", "SINT", "INT", "DINT", "LINT", "UINT", "USINT", "UDINT", "ULINT"]
    return True if st_type in l else False

def generate_DDS_API_calls(idl_struct, templates):
    """
    Expects an object of the type IDLStruct and generates the (currently Siemens
    internal, in the future maybe standardized) functions to use DDS in ST
    """

    # Do we have keyed members?
    is_keyed = idl_struct.is_keyed

    # some formatting to make the output file more human readable
    name_len = len(idl_struct.name)
    result = "\n// Struct " + idl_struct.name + (71 - name_len) * "-" + "\n"

    # Collect the base class - multiple inheritance is not allowed with ST
    base_class = ""
    inheritances = idl_struct.inheritances
    if len(inheritances) > 0:
        if len(inheritances) > 1:
            raise exception.IDLParserException(0, 0, "Multiple inheritance not supported")
        for b in inheritances:
            base_class += b.name

    # Collect the struct members
    members = []
    count = 0
    for m in idl_struct.members:
        is_keyed = "0"
        if m.attrib is not None:
            is_keyed = "1" if "@key" in m.attrib else "0"
        is_not_last = count + 1 < len(idl_struct.members)
        t = to_Type_Enum(m.type)[0]
        # Potentially dangerous if there is a class name like Circle2
        # \todo
        st = t.strip("[0123456789]")
        members.append(
            {
                "name": m.name,
                "type": t,
                "short_type": st,
                "keyed": is_keyed,
                "is_not_last": is_not_last,
                "is_int" : is_int(t)
            }
        )
        count = count + 1

    # Merge the struct template
    fn = {"name": idl_struct.name, "base_class": base_class, "members": members}
    result += templates.declare.merge(fn, loader=templates.loader)

    # Now the type support function
    fn = {"name": idl_struct.name, "count": len(idl_struct.members), "members": members}
    out = templates.type_support.merge(fn, loader=templates.loader)
    result += out + "\n"

    # Finally, the init string to be added to the program
    init_struct = templates.init_struct.merge(fn, loader=templates.loader)

    return result, init_struct


def generate_DDS_enum(idl_enum):
    """
    Expects an object of the type IDLEnum and generates the necessary ST definition
    Will be ported to velocity templates
    """
    # to do: how do we handle enums?
    result = f"TYPE {idl_enum.name}:\n(\n"
    for m in idl_enum.values:
        result += f"\t{m.name},\n"
    if len(result) > 2:
        result = result[:-2]
    result += "\n);\nEND_TYPE\n\n"
    return result


def parse_2_ST(in_path, out_path):
    """Generates the ST code for an IDL file"""
    _parser = parser.IDLParser()

    idl_str = ""
    with open(in_path, "r") as file:
        idl_str = file.read()

    # here we parse the IDL to an intermediate representation
    inc_folder = os.path.dirname(in_path)
    global_module = _parser.load(idl_str, [inc_folder])
    print("\n")

    # Load the airspeed templates
    templates = STTemplate()
    user_types = []
    init_commands = []

    # This is the generation part
    with open(out_path, "w") as text_file:

        result = "// Start of generated code\n"
        result += "using Siemens.Jupiter.Communication.DDS;\n"
        result += "using System.Strings;\n"
        text_file.write(result)

        for module in [global_module] + global_module.modules:

            if module != global_module:
                text_file.write("NAMESPACE " + module._name + "\n")

            # Currently, we do the enums first
            if len(module.enums) > 0:
                text_file.write("// Enums" + 72 * "-" + "\n")
            for e in module.enums:
                # the struct declaration
                gen_code = generate_DDS_enum(e)
                text_file.write(gen_code)
                text_file.write("\n\n")

            # Then the data types
            if len(module.structs) > 0:
                text_file.write("// Structs" + 71 * "-" + "\n")
            for s in module.structs:
                print("Struct " + s.name)
                for m in s.members:
                    attrib_str = ""
                    if m.attrib is not None:
                        attrib_str = f" with attribute {m.attrib}"
                    print(
                        f"- member: {m.name} of type {m.type.name} {attrib_str}"
                    )
                print("\n")
                gen_code, init_cmd = generate_DDS_API_calls(s, templates)
                init_commands.append(init_cmd)
                text_file.write(gen_code)
                text_file.write("\n")
                user_types.append({"name": s.name})
        if module != global_module:
            text_file.write("// end of namespace\n")
        text_file.write("// End of generated code\n")

    with open("program.st", "w") as text_file:
        # Generate the program: $user_structs 
        fn = {"user_types": user_types, "init_commands": init_commands}
        out = templates.program.merge(fn, loader=templates.loader)
        #for init_str in init_commands:
        #    text_file.write(init_str)
        text_file.write(out)

    print("Done")
    return True


def main():

    # Instantiate the parser
    arg_parser = argparse.ArgumentParser(description="Parses IDL files to ST")

    # Required positional argument is currently the file to parse
    arg_parser.add_argument(
        "path", type=str, help="Required string argument, " "namely the IDL file path"
    )
    # and the target file (which is to be created)
    arg_parser.add_argument(
        "out_path",
        type=str,
        nargs="?",
        help="Optional string argument, " "namely the output file path",
        default="",
    )
    args = arg_parser.parse_args()
    print("Parsing file " + args.path)
    out_path = args.out_path
    if out_path == "":
        # Default output is the same base name, but .st extension
        out_path = os.path.splitext(os.path.basename(args.path))[0] + ".st"
    parse_2_ST(args.path, out_path)


if __name__ == "__main__":
    main()
