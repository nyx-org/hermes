import string
from gen import *

file_template = R"""
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <nyx/syscall.h>

size_t strlen(const char *s);
void *memcpy(void * dest, const void * src, size_t n);

namespace {} {{
    constexpr int PORT_SEND = 0;
    constexpr int PORT_RECV = 1;
    
    constexpr int PORT_MSG_TYPE_DEFAULT = (1 << 0);
    constexpr int PORT_MSG_TYPE_RIGHT = (1 << 1);
    constexpr int PORT_MSG_TYPE_RIGHT_ONCE = (1 << 2);

    constexpr int PORT_RIGHT_RECV = (1 << 0);
    constexpr int PORT_RIGHT_SEND = (1 << 1);

    constexpr int PORT_NULL = 0;

    struct [[gnu::packed]] PortSharedMemoryDescriptor
    {{
        uintptr_t address;
        uint16_t size;
    }};

    struct [[gnu::packed]] PortMessageHeader
    {{
        uint8_t type;                         
        uint32_t size;                        
        uint32_t dest;                        
        uint32_t port_right;                  
        uint8_t shmd_count;                   
        PortSharedMemoryDescriptor shmds[16]; 
    }};

   using Port = uint32_t;

   static inline Port sys_alloc_port(uint8_t rights)
   {{
        return __syscall(SYS_ALLOC_PORT, rights).ret;
   }}
   static inline void sys_free_port(Port port)
   {{
        __syscall(SYS_FREE_PORT, port);
   }}
   static inline Port sys_get_common_port(uint8_t id)
   {{
      return (Port)__syscall(SYS_GET_COMMON_PORT, id).ret;
   }}

   static inline size_t sys_msg(uint8_t msg_type, Port port_to_receive, size_t bytes_to_receive, PortMessageHeader *header)
   {{
        return __syscall(SYS_MSG, msg_type, port_to_receive, bytes_to_receive, (uintptr_t)header).ret;
   }}

   static void wait_for_message(Port port, size_t size, PortMessageHeader *buffer)
   {{
        while (true)
        {{
            if (!sys_msg(PORT_RECV, port, size, buffer))
            {{   
                __sycall(SYS_YIELD);
            }}
	        else
	        {{
	            break;
	        }}
        }}
    }}

    static inline int send_bidirectional_message(Port port_to_reply_on, PortMessageHeader *message)
    {{
        message->type = PORT_MSG_TYPE_RIGHT_ONCE;
        message->port_right = port_to_reply_on;

        sys_msg(PORT_SEND, PORT_NULL, -1, message);

        return 0;
    }}

    static inline PortMessageHeader *send_and_wait_for_reply(PortMessageHeader *message_to_send, size_t size_to_recv, PortMessageHeader *msg_to_receive)
    {{
        Port port_to_reply_on = sys_alloc_port(PORT_RIGHT_RECV | PORT_RIGHT_SEND);

        send_bidirectional_message(port_to_reply_on, message_to_send);

        wait_for_message(port_to_reply_on, size_to_recv, msg_to_receive);

        sys_free_port(port_to_reply_on);

        return msg_to_receive;
    }}

    static inline PortMessageHeader *send_and_wait_for_reply(Port port, PortMessageHeader *message_to_send, size_t size_to_recv, PortMessageHeader *msg_to_receive)
    {{
        message_to_send->type = PORT_MSG_TYPE_RIGHT;
        message_to_send->port_right = port;

        sys_msg(PORT_SEND, PORT_NULL, -1, message_to_send);

        wait_for_message(port, size_to_recv, msg_to_receive);

        return msg_to_receive;
    }}

"""


def pascalcase(s):
    return string.capwords(s.replace('_', ' ')).replace(' ', '')


def gen_interface(f, interface, interface_name, attr):
    f.write(file_template.format(pascalcase(interface_name)))

    gen_interface_decl(f, interface, interface_name, attr,
                       constexpr=True, include=False, numbers_only=True)

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
                               port, static=True)

        f.write("\n{\n")
        f.write(f"\t{req_struct_name} msg = {{}};\n")
        f.write(f"\t{resp_struct_name} response = {{}};\n")

        port_name = "__port"

        if attr:
            if attr.name == "common_port":
                port_name = f"sys_get_common_port({int(attr.value.thing)})"

        f.write(
            f"\tmsg.call = {interface_name.upper()}_{str(i.name).upper()};\n\tmsg.header = (PortMessageHeader){{.type=PORT_MSG_TYPE_DEFAULT, .size=sizeof(msg), .dest={port_name}}};\n")

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
                    f"\tPortSharedMemoryDescriptor shmd_{p[1].name} = (PortSharedMemoryDescriptor){{.address = (uintptr_t){p[1].name}, .size = (uint16_t){p[1].name}_size}};\n")
                f.write(
                    f"\tmsg.requests.{i.name}.{p[1].name}_shmd = msg.header.shmd_count-1;\n")
                f.write(
                    f"\tmsg.header.shmds[msg.header.shmd_count-1] = shmd_{p[1].name};\n")
            else:
                f.write(
                    f"\tmsg.requests.{i.name}.{p[1].name} = {p[1].name};\n")

        if has_port == False:
            f.write(
                f"\tresponse = *({resp_struct_name}*)send_and_wait_for_reply(&msg.header, sizeof(response), &response.header);\n")
        else:
            f.write(
                f"\tresponse = *({resp_struct_name}*)send_port_right_and_wait_for_reply({port}, &msg.header, sizeof(response), &response.header);\n")

        if port_return_type is not True:
            f.write(f"\treturn response._data.{i.typing}_val;\n")
        else:
            f.write(f"\treturn response.header.port_right;\n")

        f.write("}\n")

    f.write("}\n")
