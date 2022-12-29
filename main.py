import argparse
import sys
import parse as idl_parser
import gen
import gen_cpp
import os

parser = argparse.ArgumentParser(
    prog=sys.argv[0],
    description='IDL stuff lol',
    epilog='nerd')

parser.add_argument('filename')
parser.add_argument('-d', '--directory')
parser.add_argument('-l', '--language')

args = parser.parse_args()

source = ""

with open(args.filename) as f:
    source = f.read()

program = idl_parser.parse(source, idl_parser.Program)


attr = None
if hasattr(program, "attr"):
    attr = program.attr

interface = program[0]

interface_name = str(interface.name).lower()

output_dir = ""
cpp = False

if args.directory:
    output_dir = args.directory

if args.language:
    if args.language == "cpp":
        cpp = True

if cpp == False:
    output_c = os.path.join(output_dir, interface_name + '.c')
    output_h = os.path.join(output_dir, interface_name + '.h')

    output_srv_h = os.path.join(output_dir, interface_name + '_srv.h')

    with open(output_h, "w") as f:
        f.write(f"#ifndef {interface_name.upper()}_H\n")
        f.write(f"#define {interface_name.upper()}_H\n")
        f.write("#include <stdint.h>\n#include <stddef.h>\n")

        gen.gen_interface_decl(f, interface, interface_name, attr)

        f.write("#endif\n")

    with open(output_c, "w") as f:
        gen.gen_interface_def(f, interface, interface_name, attr)

        f.write("\n")

    with open(output_srv_h, "w") as f:
        gen.gen_interface_server(f, interface, interface_name, attr)
else:
    output_hpp = os.path.join(output_dir, interface_name + '.gen.hpp')
    with open(output_hpp, "w") as f:
        gen_cpp.gen_interface(f, interface, interface_name, attr)
