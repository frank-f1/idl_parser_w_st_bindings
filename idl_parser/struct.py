import os, sys, traceback

from . import node
from . import type as idl_type
from . import exception


class IDLMember(node.IDLNode):
    def __init__(self, parent):
        super(IDLMember, self).__init__("IDLMember", "", parent)
        self._verbose = True
        self._type = None
        self._attrib = None
        self.sep = "::"

    @property
    def full_path(self):
        return self.parent.full_path + self.sep + self.name

    def parse_blocks(self, blocks, filepath=None):
        self._filepath = filepath
        name, typ, attrib = self._name_and_type_and_attrib(blocks)
        if name.find("[") >= 0:
            name_ = name[: name.find("[")]
            typ = typ.strip() + " " + name[name.find("[") :]
            name = name_
        self._name = name
        self._type = idl_type.IDLType(typ, self)
        self._attrib = attrib

    def to_simple_dic(self, recursive=False, member_only=False):
        if recursive:
            if self.type.is_primitive:
                return str(self.type) + " " + self.name
            elif self.type.obj.is_enum:
                return str("enum") + " " + self.name
            dic = {
                str(self.type)
                + " "
                + self.name: self.type.obj.to_simple_dic(
                    recursive=recursive, member_only=True
                )
            }
            return dic
        dic = {self.name: str(self.type)}
        return dic

    def to_dic(self):
        dic = {
            "name": self.name,
            "filepath": self.filepath,
            "classname": self.classname,
            "type": str(self.type),
        }
        return dic

    @property
    def type(self):
        if self._type.classname == "IDLBasicType":  # Struct
            typs = self.root_node.find_types(self._type.name)
            if len(typs) == 0:
                print("Can not find Data Type (%s)\n" % self._type.name)
                raise exception.InvalidDataTypeException()
            elif len(typs) > 1:
                typs = self.root_node.find_types(
                    self._type.name, parent=self.parent.parent
                )
                if len(typs) == 0:
                    print("Can not find Data Type (%s)\n" % self._type.name)
                    raise exception.InvalidDataTypeException()

            return typs[0]
        return self._type

    @property
    def attrib(self):
        return self._attrib

    def get_type(self, extract_typedef=False):
        if extract_typedef:
            if self.type.is_typedef:
                return self.type.type
        return self.type

    def post_process(self):
        self._type._name = self.refine_typename(self.type)


class IDLStruct(node.IDLNode):
    def __init__(self, name, parent):
        super(IDLStruct, self).__init__("IDLStruct", name.strip(), parent)
        self._verbose = False  # True
        self._members = []
        self.sep = "::"
        self._attrib = None
        self._inheritances = []
        self._keyed = False

    @property
    def inheritances(self):
        return [
            self.root_node.find_types(inheritance)[0]
            for inheritance in self._inheritances
        ]

    @property
    def full_path(self):
        return (self.parent.full_path + self.sep + self.name).strip()

    @property
    def attrib(self):
        return self._attrib

    @property
    def is_keyed(self):
        for parent in self.inheritances:
            if parent.is_keyed:
                return True
        return self._keyed

    def to_simple_dic(
        self, quiet=False, full_path=False, recursive=False, member_only=False
    ):
        name = self.full_path if full_path else self.name
        if quiet:
            return "struct %s" % name

        dic = {
            "struct %s"
            % name: [v.to_simple_dic(recursive=recursive) for v in self.members]
        }

        if member_only:
            return dic.values()[0]
        return dic

    def to_dic(self):
        dic = {
            "name": self.name,
            "classname": self.classname,
            "members": [v.to_dic() for v in self.members],
        }
        return dic

    def parse_tokens(self, token_buf, filepath=None):
        self._filepath = filepath
        ln, fn, kakko = token_buf.pop()
        if kakko == ":":  # Detect Inheritance
            ln, fn, name = token_buf.pop()
            structs = self.root_node.find_types(name)
            if len(structs) == 0:
                if self._verbose:
                    sys.stdout.write(
                        '# Error. Can not find "%s" struct which is generalization of "%s"\n'
                        % (name, self.name)
                    )
                raise exception.InvalidDataTypeException
            elif len(structs) > 1:
                if self._verbose:
                    sys.stdout.write("# Error. Multiple inheritance not supported")
                raise exception.InvalidDataTypeException
            self._inheritances.append(structs[0].full_path)
            ln, fn, kakko = token_buf.pop()

        if not kakko == "{":
            if self._verbose:
                sys.stdout.write('# Error. No kakko "{".\n')
            raise exception.InvalidIDLSyntaxError()

        block_tokens = []
        while True:

            ln, fn, token = token_buf.pop()
            if token == None:
                if self._verbose:
                    sys.stdout.write('# Error. No kokka "}".\n')
                raise exception.InvalidIDLSyntaxError()

            elif token == "}":
                ln2, fn2, token = token_buf.pop()
                if not token == ";":
                    if self._verbose:
                        sys.stdout.write('# Error. No semi-colon after "}".\n')
                    raise exception.InvalidIDLSyntaxError(
                        ln, fn, 'No semi-colon after "}"'
                    )
                break

            if token == ";":
                self._parse_block(block_tokens)
                block_tokens = []
                continue

            block_tokens.append(token)

        self._post_process()

    def _parse_block(self, blocks):
        v = IDLMember(self)
        v.parse_blocks(blocks, self.filepath)
        if v.attrib is not None:
            if v.attrib == "@key":
                self._keyed = True
        self._members.append(v)

    def _post_process(self):
        self.forEachMember(lambda m: m.post_process())

    @property
    def members(self):
        return self._members

    def member_by_name(self, name):
        """find a member using its name"""
        for m in self._members:
            if m.name == name:
                return m
        return None

    def forEachMember(self, func):
        """apply function to each member"""
        for m in self._members:
            func(m)
