"""Generation of the custom operator from existing python code"""

import subprocess
import re

import madflow.wavefunctions_flow
import madflow.makefile_template as mf_tmp

import madflow.op_aux_functions as op_af
import madflow.op_generation as op_gen
import madflow.op_global_constants as op_gc
import madflow.op_write_templates as op_wt
import madflow.op_syntax as op_sy
import madflow.op_parser as op_pa
import madflow.op_read as op_re


folder_name = "prov/"

temp = ""
devices = ["cpu", "gpu"]


def translate(destination):
    """Translates Python code into a C++/CUDA Custom Operator
    destination: directory of madflow output"""

    file_sources = [madflow.wavefunctions_flow.__file__]  # path to wavefunctions_flow.py

    # Create the directory for the Op source code and create the makefile

    destination_gpu = destination / "gpu"
    destination_gpu.mkdir(parents=True, exist_ok=True)
    mf_tmp.write_makefile(destination)

    # Generate sign functions
    auxiliary_functions = []
    function_list_ = []
    auxiliary_functions, function_list_ = op_af.generate_auxiliary_functions(
        auxiliary_functions, function_list_
    )

    # Read wavefunctions_flow.py
    for file_source in file_sources:
        signatures_ = []
        signature_variables_ = []

        signatures_, signature_variables_ = op_re.read_signatures(
            signatures_, signature_variables_, file_source
        )

        signature_variables_ = op_pa.convert_signatures(signatures_, signature_variables_)

        function_list_ = op_re.read_file_from_source(
            function_list_, file_source, signatures_, signature_variables_
        )

    for subprocess_file_name in destination.glob("matrix_1_*"):

        constants = []  # global_constants

        for e in op_gc.global_constants:
            constants.append(e)

        process_name = re.sub("matrix_1_", "", subprocess_file_name.stem)

        matrix_source = subprocess_file_name
        process_source = subprocess_file_name.parent / (
            re.sub("matrix_1_", "aloha_1_", subprocess_file_name.stem) + subprocess_file_name.suffix
        )

        signatures = signatures_
        signature_variables = signature_variables_
        function_list = []
        for f in function_list_:
            function_list.append(f)
        headers = []
        for h in op_gc.headers_:
            headers.append(h)
        headers.append("matrix_" + process_name + ".h")

        custom_op_list = []

        signatures, signature_variables = op_re.read_signatures(
            signatures, signature_variables, process_source
        )

        signature_variables = op_pa.convert_signatures(signatures, signature_variables)

        function_list = op_re.read_file_from_source(
            function_list, process_source, signatures, signature_variables
        )

        matrix_name = subprocess_file_name.name

        signatures, signature_variables = op_re.read_signatures(
            signatures, signature_variables, matrix_source
        )
        signature_variables = op_pa.convert_signatures(signatures, signature_variables)

        function_list = op_re.extract_matrix_from_file(
            function_list, matrix_source, signatures, signature_variables
        )

        for i in range(len(function_list)):
            function_list = op_sy.check_variables(i, function_list)

        for i in range(len(function_list)):
            function_list = op_sy.check_lines(i, function_list)
        for i in range(len(function_list)):
            function_list = op_sy.check_variables(i, function_list)

        function_list[-1] = op_gen.serialize_function(function_list[-1])

        custom_op_list.append(op_gen.define_custom_op(function_list[-1]))

        function_list[-1], constants = op_gen.extract_constants(function_list[-1], constants)

        function_list[-1] = op_gen.remove_real_ret(function_list[-1])

        # write the Op for both CPU and GPU
        for device in devices:
            op_wt.write_custom_op(
                headers,
                op_gc.namespace,
                op_gc.defined,
                constants,
                op_gc.cpu_constants,
                function_list,
                custom_op_list,
                destination_gpu,
                process_name,
                device,
            )

        # write matrix_xxxxx.h
        temp = ""
        for c in custom_op_list:
            temp += op_wt.write_header_file(c, function_list[-1])
        (destination_gpu / ("matrix_" + process_name + ".h")).write_text(temp)

        # write matrix_1_xxxxx.py
        temp = ""
        temp = op_gen.modify_matrix(matrix_source, process_name, destination)
        (destination / matrix_name).write_text(temp)

        # --------------------------------------------------------------------------------------


def compile_op(destination):
    """Compiles the Custom Operator
    destination: directory of madflow output"""
    subprocess.run("make", cwd=destination, check=True)


if __name__ == "__main__":
    translate(folder_name)
