from parse import *
import stringcase

return_types = []


def gen_includes(f):
    f.write("#include <ichor/base.h>\n")
    f.write("#include <ichor/port.h>\n")
    f.write("#include <ichor/syscalls.h>\n")
    f.write("#include <stdc-shim/string.h>\n")


def gen_function_prototype(f, function, interface_name, port=True):
    global return_types
    f.write(f"{c_types[function.typing]} {interface_name}_{function.name}(")

    return_types.append(str(function.typing))

    if port == True:
        f.write("Port __port")

        if len(function.params.items()) > 0:
            f.write(", ")

    port_count = 0
    for p in function.params.items():
        if p[1].typing == "Port":
            port_count = port_count + 1

    if port_count > 1:
        print("Function cannot have more than one port as an argument!")
        sys.exit(-1)

    for p_i, p in enumerate(function.params.items()):

        f.write(f"{c_types[p[1].typing]} {p[1].name}")

        if p_i != len(function.params.items())-1:
            f.write(", ")
    f.write(")")


def gen_interface_decl(f, interface, interface_name, attr):
    gen_includes(f)
    curr_val = 0
    for i in interface:
        port = True

        if attr:
            if attr.name == "common_port":
                port = False
        f.write(
            f"#define {interface_name.upper()}_{str(i.name).upper()} {curr_val}\n")
        gen_function_prototype(f, i, interface_name,
                               port)
        f.write(";\n")
        curr_val = curr_val + 1


def gen_response_struct(f, interface, interface_name):
    global return_types
    return_types = list(set(return_types))

    f.write(
        "typedef struct \n{\n PortMessageHeader header;\n union \n {\n ")
    for i in return_types:
        if i == "string256":
            f.write(f"char {i}_val[256];\n")
        if i == "shared_ptr":
            f.write(f"int {i}_shmd;\n")
        elif i != "Port":
            f.write(f" {c_types[i]} {i}_val;\n")

    name = stringcase.pascalcase(f"{interface_name}_response")
    f.write(f" }} _data; \n}} {name}; \n")
    return name


def gen_request_struct_for_function(f, interface_name, function):
    f.write(f"typedef struct {{ PortMessageHeader header; ")

    for p in function.params.items():
        if p[1].typing == "string256":
            f.write(f"char {p[1].name}[256];")
        elif p[1].typing == "shared_ptr":
            f.write(f"int {p[1].name}_shmd;\n")
        elif p[1].typing != "Port":
            f.write(f"{c_types[p[1].typing]} {p[1].name};")

    name = stringcase.pascalcase(f"{interface_name}_{function.name}_req")
    f.write(f"}} {name};\n\n")


def gen_request_struct(f, interface_name, interface):
    f.write(
        "typedef struct \n{\n PortMessageHeader header;\n uint8_t call;\n union \n {\n ")

    struct_name = stringcase.pascalcase(f"{interface_name}_req")
    for i in interface:
        type_name = stringcase.pascalcase(f"{interface_name}_{i.name}_req")
        f.write(f" {type_name} {i.name};\n")
    f.write(f" }} requests;\n}} {struct_name};\n")
    return struct_name


def gen_interface_server(f, interface, interface_name, attr):
    gen_includes(f)
    f.write(f"#ifndef {interface_name.upper()}_SRV_H\n")
    f.write(f"#define {interface_name.upper()}_SRV_H\n")
    curr_val = 0
    for i in interface:

        gen_request_struct_for_function(f, interface_name, i)

        f.write(
            f"#define {interface_name.upper()}_{str(i.name).upper()} {curr_val}\n")
        gen_function_prototype(f, i, interface_name, False)
        f.write(";\n")
        curr_val = curr_val + 1

    gen_request_struct(f, interface_name, interface)
    gen_response_struct(f, interface, interface_name)

    f.write("#endif\n")


def gen_interface_def(f, interface, interface_name, attr):
    f.write(f"#include \"{interface_name}.h\"\n")

    resp_struct_name = gen_response_struct(f, interface, interface_name)

    for i in interface:
        gen_request_struct_for_function(f, interface_name, i)

    req_struct_name = gen_request_struct(f, interface_name, interface)

    for i in interface:

        port = True

        if attr:
            if attr.name == "common_port":
                port = False

        gen_function_prototype(f, i, interface_name,
                               port)

        f.write("\n{\n")
        f.write(f"\t{req_struct_name} msg = {{}};\n")
        f.write(f"\t{resp_struct_name} response = {{}};\n")

        port_name = "__port"

        if attr:
            if attr.name == "common_port":
                port_name = f"sys_get_common_port({int(attr.value.thing)})"

        f.write(
            f"\tmsg.call = {interface_name.upper()}_{str(i.name).upper()};\n\tmsg.header = (PortMessageHeader){{.size=sizeof(msg), .dest={port_name}, .type=PORT_MSG_TYPE_DEFAULT}};\n")

        has_port = False
        port = ""
        port_return_type = False

        if i.typing == "Port":
            port_return_type = True

        for p in i.params.items():
            if p[1].typing == "string256":
                f.write(
                    f"\tmemcpy((char*)msg.requests.{i.name}.{p[1].name}, {p[1].name}, strlen({p[1].name}));\n")
            elif p[1].typing == "Port":
                has_port = True
                port = p[1].name
            elif p[1].typing == "shared_ptr":
                f.write(f"\tmsg.header.shmd_count++;\n")
                f.write(
                    f"\tPortSharedMemoryDescriptor shmd_{p[1].name} = (PortSharedMemoryDescriptor){{.addr = {p[1].name}, .size = {p[1].name}_size}};\n")
                f.write(
                    f"\tmsg.requests.{i.name}.{p[1].name}_shmd = msg.header.shmd_count-1;\n")
            else:
                f.write(
                    f"\tmsg.requests.{i.name}.{p[1].name} = {p[1].name};\n")

        if has_port == False:
            f.write(
                f"\tresponse = *({resp_struct_name}*)ichor_send_and_wait_for_reply(&msg.header, sizeof(response), &response.header);\n")
        else:
            f.write(
                f"\tresponse = *({resp_struct_name}*)ichor_send_port_right_and_wait_for_reply({port}, &msg.header, sizeof(response), &response.header);\n")

        if port_return_type is not True:
            f.write(f"\treturn response._data.{i.typing}_val;\n")
        else:
            f.write(f"\treturn response.header.port_right;\n")

        f.write("}\n")
