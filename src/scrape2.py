#!/usr/bin/env python3.7

import subprocess
import argparse
import multiprocessing
import tempfile
import functools
import random

from helper import *
import linearize_semicolons
import serapi_instance

from sexpdata import *
from traceback import *
from format import format_context, format_tactic

from typing import Dict, Any, TextIO

def percentage(num_str):
    num = float(num_str)
    if num < 0 or num > 1:
        raise argparse.ArgumentTypeError("%s is an invalid percentage. Must be between 0 and 1" % num_str)
    return num

def main():
    # Parse the command line arguments.
    parser = argparse.ArgumentParser(description="scrape a proof")
    parser.add_argument('-o', '--output', help="output data file name", default=None)
    parser.add_argument('-j', '--threads', default=1, type=int)
    parser.add_argument('--prelude', default=".")
    parser.add_argument('--debug', default=False, const=True, action='store_const')
    parser.add_argument('--skip-nochange-tac', default=False, const=True, action='store_const',
                    dest='skip_nochange_tac')
    parser.add_argument('--test-theorems-file', help="output test theorems file name", default=None,
                    dest='test_theorems_file')
    parser.add_argument('--test-percentage', default=0.1, type=percentage,
                    dest='test_percentage')
    parser.add_argument('inputs', nargs="+", help="proof file name(s) (*.v)")
    args = parser.parse_args()


    includes=subprocess.Popen(['make', '-C', args.prelude, 'print-includes'],
                              stdout=subprocess.PIPE).communicate()[0]\
                       .strip().decode('utf-8')

    thispath = os.path.dirname(os.path.abspath(__file__))
    # Set up the command which runs sertop.
    coqargs = ["{}/../coq-serapi/sertop.native".format(thispath),
               "--prelude={}/../coq".format(thispath)]

    with multiprocessing.Pool(args.threads) as pool:
        scrape_result_files = pool.imap_unordered(
            functools.partial(scrape_file, coqargs, args.skip_nochange_tac, args.debug, includes, args.prelude),
            args.inputs)
        with open(args.output or "scrape.txt", 'w') as out, \
            open(args.test_theorems_file or "test_theorems.txt", 'w') as test_theorems_file:
            for idx, scrape_result_file in enumerate(scrape_result_files, start=1):
                if scrape_result_file is None:
                    print("Failed file {} of {}".format(idx, len(args.inputs)))
                else:
                    print("Finished file {} of {}".format(idx, len(args.inputs)))
                    write_output_file(scrape_result_file, out, test_theorems_file, args.test_percentage)
                    # with open(scrape_result_file, 'r') as f:
                    #     for line in f:
                    #         out.write(line)

NEW_COMMAND_STR = "\n-----\n"
BEGIN_THEREOM_REGEX = "Theorem|Lemma|Remark|Fact|Corollary|Proposition|Definition|Example"

def write_output_file(scrape_result_file : str, out : TextIO, test_theorems_file : TextIO, test_percentage : float) -> None:
    filename = re.sub(".scrape", "", scrape_result_file)
    seen = set()
    test_theorems = set()
    new_command = False
    with open(scrape_result_file, 'r') as f:
        commands = f.read().split(NEW_COMMAND_STR)
        for command in commands:
            if re.match(BEGIN_THEREOM_REGEX, command):
                theorem_name = command.split()[1].strip()
                if theorem_name[-1] == ':': theorem_name[:-1]
                if theorem_name not in seen:
                    seen.add(theorem_name)
                    if random.random() < test_percentage:
                        test_theorems.add(theorem_name)

                if theorem_name in test_theorems:
                    continue
            out.write(command + NEW_COMMAND_STR)
    for theorem in test_theorems:
        test_theorems_file.write("{0}:{1}\n".format(filename, theorem))


def scrape_file(coqargs : List[str], skip_nochange_tac : bool, debug : bool, includes : str,
                prelude : str, filename : str) -> str:
    try:
        full_filename = prelude + "/" + filename
        commands = try_load_lin(full_filename)
        if not commands:
            commands = preprocess_file_commands(load_commands(full_filename),
                                                coqargs, includes, prelude,
                                                full_filename, skip_nochange_tac)
            save_lin(commands, full_filename)

        with serapi_instance.SerapiContext(coqargs, includes, prelude) as coq:
            result_file = full_filename + ".scrape"
            coq.debug = debug
            try:
                with open(result_file, 'w') as f:
                    for command in commands:
                        process_statement(coq, command, f)
            except serapi_instance.TimeoutError:
                print("Command in {} timed out.".format(filename))
            return result_file
    except Exception as e:
        print("FAILED: In file {}:".format(filename))
        print(e)

def process_statement(coq : serapi_instance.SerapiInstance, command : str,
                      result_file : TextIO) -> None:
    if coq.proof_context:
        prev_tactics = coq.prev_tactics
        prev_hyps = coq.get_hypothesis()
        prev_goal = coq.get_goals()
        result_file.write(format_context(prev_tactics, prev_hyps, prev_goal, ""))
        result_file.write(format_tactic(command))
    else:
        subbed_command = re.sub(r"\n", r"\\n", command)
        result_file.write(subbed_command+NEW_COMMAND_STR)

    coq.run_stmt(command)

# begin_thereom_regex = "Theorem|Lemma|Remark|Fact|Corollary|Proposition|Definition|Example"
# def split_dataset(prelude : str, files : str, test_percentage : float) -> None:
#     from collections import Counter
#     test_theorems_file = open("../data/test_theorems.txt", 'w')
#     for filename in files:
#         full_filename = prelude + "/" + filename
#         with open (full_filename, 'r') as f:
#             for line in f:
#                 if re.match(begin_thereom_regex, line):
#                     theorem_name = line.split()[1][:-1]
#                     if random.random() < test_percentage:
#                         test_theorems_file.write("{0}:{1}\n".format(filename, theorem_name))
#     test_theorems_file.close()

if __name__ == "__main__":
    main()
