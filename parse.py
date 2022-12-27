from pypeg2 import *

c_types = {
    "string256": "const char *",
    "i8": "int8_t",
    "i16": "int16_t",
    "i32": "int32_t",
    "i64": "int64_t",
    "u8": "uint8_t",
    "u16": "uint16_t",
    "u32": "uint32_t",
    "u64": "uint64_t",
    "ptr": "void *",
    "char": "char",
    "bool": "bool",
    "Port": "Port",
    "shared_ptr": "void*"
}


class Type(Keyword):
    grammar = Enum(
        K("string256"),
        K("i8"),
        K("i16"),
        K("i32"),
        K("i64"),
        K("u8"),
        K("u16"),
        K("u32"),
        K("u64"),
        K("ptr"),
        K("char"),
        K("Port"),
        K("bool"),
        K("shared_ptr"),
    )


class Parameter:
    grammar = attr("typing", Type), name()


class Attr:
    grammar = "@", name(), optional(attr("value", name()))


class Parameters(Namespace):
    grammar = csl(Parameter)


class Function(List):
    grammar = attr("typing", Type), name(), \
        "(", attr("params", Parameters), ")"


class Interface(List):
    grammar = "interface", name(), "{", csl(Function), "}"


class Program(List):
    grammar = optional(attr("attr", Attr)), Interface
