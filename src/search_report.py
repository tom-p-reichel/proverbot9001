#!/usr/bin/env python3.7

import argparse
import subprocess
import os
import sys
import multiprocessing
import re
import datetime
import time
import functools
import shutil

from models.tactic_predictor import TacticPredictor, TacticContext
from predict_tactic import (static_predictors, loadPredictorByFile,
                            loadPredictorByName)
import serapi_instance
from serapi_instance import FullContext, Subgoal
import linearize_semicolons
import syntax
from format import format_goal
from util import *

from typing import List, Tuple, NamedTuple, Optional, Sequence, Dict

import search_file

index_css = ["report.css"]
index_js = ["report.js"]
extra_files = index_css + index_js + ["logo.png"]

from tqdm import tqdm

def main(arg_list : List[str]) -> None:
    parser = argparse.ArgumentParser(
        description=
        "Produce an index file from attempting to complete proofs using Proverbot9001.")
    parser.add_argument("-j", "--threads", dest="num_threads", default=16, type=int)
    parser.add_argument("--output", "-o", help="output data folder name",
                        default="search-report")
    parser.add_argument('--weightsfile', default=None)
    parser.add_argument('--predictor', choices=list(static_predictors.keys()),
                        default=None)
    parser.add_argument('filenames', nargs="+", help="proof file name (*.v)")
    args, unknown_args = parser.parse_known_args(arg_list)
    commit, date = get_metadata()
    base = os.path.dirname(os.path.abspath(__file__)) + "/.."

    if not os.path.exists(args.output):
        os.makedirs(args.output)

    with multiprocessing.pool.ThreadPool(args.num_threads) as pool:
        pool.starmap(functools.partial(run_search, unknown_args, args.output,
                                       args.predictor, args.weightsfile),
                     enumerate(args.filenames))
    file_results = [read_stats_from_csv(args.output, filename)
                    for filename in args.filenames]

    tqdm.write("Writing summary with {} file outputs.".format(len(file_results)))
    predictorOptions = get_predictor(parser, args).getOptions()
    write_summary(args, predictorOptions +
                  [("report type", "search"),
                   ("search width", args.search_width),
                   ("search depth", args.search_depth)],
                  commit, date, file_results)
def run_search(argslist : List[str],
               outdir : str,
               predictor : Optional[str],
               weightsfile : Optional[str],
               file_idx : int,
               filename : str) -> None:
    augmented_argslist = argslist + ["-o", outdir]
    if predictor:
        augmented_argslist += ["--predictor", predictor]
    if weightsfile:
        augmented_argslist += ["--weightsfile", weightsfile]
    augmented_argslist += [filename]
    search_file.main(augmented_argslist , bar_idx = file_idx)

class ReportStats(NamedTuple):
    filename : str
    num_proofs : int
    num_proofs_failed : int
    num_proofs_completed : int

from enum import Enum, auto
from typing import Union
class SearchStatus(Enum):
    SUCCESS = auto()
    INCOMPLETE = auto()
    FAILURE = auto()

def get_metadata() -> Tuple[str, datetime.datetime]:
    cur_commit = subprocess.check_output(["git show --oneline | head -n 1"],
                                         shell=True).decode('utf-8').strip()
    cur_date = datetime.datetime.now()
    return cur_commit, cur_date

from yattag import Doc
Tag = Callable[..., Doc.Tag]
Text = Callable[..., None]
Line = Callable[..., None]

def html_header(tag : Tag, doc : Doc, text : Text, css : List[str],
                javascript : List[str], title : str) -> None:
    with tag('head'):
        for filename in css:
            doc.stag('link', href=filename, rel='stylesheet')
        for filename in javascript:
            with tag('script', type='text/javascript',
                     src=filename):
                pass
        with tag('title'):
            text(title)

def write_summary_html(filename : str,
                       options : Sequence[Tuple[str, str]],
                       cur_commit : str, cur_date : datetime.datetime,
                       individual_stats : List[ReportStats],
                       combined_stats : ReportStats) -> None:
    def report_header(tag : Any, doc : Doc, text : Text) -> None:
        html_header(tag, doc, text,index_css, index_js,
                    "Proverbot Report")
    doc, tag, text, line = Doc().ttl()
    with tag('html'):
        report_header(tag, doc, text)
        with tag('body'):
            with tag('h4'):
                text("{} files processed".format(len(individual_stats)))
            with tag('h5'):
                text("Commit: {}".format(cur_commit))
            with tag('h5'):
                text("Run on {}".format(cur_date.strftime("%Y-%m-%d %H:%M:%S.%f")))
            with tag('img',
                     ('src', 'logo.png'),
                     ('id', 'logo')):
                pass
            with tag('h2'):
                text("Proofs Completed: {}% ({}/{})"
                     .format(stringified_percent(combined_stats.num_proofs_completed,
                                                 combined_stats.num_proofs),
                             combined_stats.num_proofs_completed,
                             combined_stats.num_proofs))
            with tag('ul'):
                for k, v in options:
                    if k == 'filenames':
                        continue
                    elif not v:
                        continue
                    with tag('li'):
                        text("{}: {}".format(k, v))

            with tag('table'):
                with tag('tr', klass="header"):
                    line('th', 'Filename')
                    line('th', 'Number of Proofs in File')
                    line('th', '% Proofs Completed')
                    line('th', '% Proofs Incomplete')
                    line('th', '% Proofs Failed')
                    line('th', 'Details')
                sorted_rows = sorted(individual_stats,
                                     key=lambda fresult:fresult.num_proofs,
                                     reverse=True)
                for fresult in sorted_rows:
                    if fresult.num_proofs == 0:
                        continue
                    with tag('tr'):
                        line('td', fresult.filename)
                        line('td', str(fresult.num_proofs))
                        line('td', stringified_percent(fresult.num_proofs_completed,
                                                       fresult.num_proofs))
                        line('td', stringified_percent(fresult.num_proofs -
                                                       (fresult.num_proofs_completed +
                                                        fresult.num_proofs_failed),
                                                       fresult.num_proofs))
                        line('td', stringified_percent(fresult.num_proofs_failed,
                                                       fresult.num_proofs))
                        with tag('td'):
                            with tag('a',
                                     href=escape_filename(fresult.filename) + ".html"):
                                text("Details")
                with tag('tr'):
                    line('td', "Total");
                    line('td', str(combined_stats.num_proofs))
                    line('td', stringified_percent(combined_stats.num_proofs_completed,
                                                   combined_stats.num_proofs))
                    line('td', stringified_percent(combined_stats.num_proofs -
                                                   (combined_stats.num_proofs_completed +
                                                    combined_stats.num_proofs_failed),
                                                   combined_stats.num_proofs))
                    line('td', stringified_percent(combined_stats.num_proofs_failed,
                                                   combined_stats.num_proofs))
    with open(filename, "w") as fout:
        fout.write(doc.getvalue())

import csv
def write_summary_csv(filename : str, combined_stats : ReportStats,
                      options : Sequence[Tuple[str, str]]):
    with open(filename, 'w', newline='') as csvfile:
        for k, v in options:
            csvfile.write("# {}: {}\n".format(k, v))
        rowwriter = csv.writer(csvfile, lineterminator=os.linesep)
        rowwriter.writerow([combined_stats.num_proofs,
                            combined_stats.num_proofs_failed,
                            combined_stats.num_proofs_completed])

def write_summary(args : argparse.Namespace, options : Sequence[Tuple[str, str]],
                  cur_commit : str, cur_date : datetime.datetime,
                  individual_stats : List[ReportStats]) -> None:
    combined_stats = combine_file_results(individual_stats)
    write_summary_html("{}/report.html".format(args.output),
                       options, cur_commit, cur_date, individual_stats, combined_stats)
    write_summary_csv("{}/report.csv".format(args.output), combined_stats, options)
    write_proof_summary_csv(args.output, [s.filename for s in individual_stats])
    for filename in extra_files:
        shutil.copy(os.path.dirname(os.path.abspath(__file__)) + "/../reports/" + filename,
                    args.output + "/" + filename)
def write_proof_summary_csv(output_dir : str, filenames : List[str]):
    with open('{}/proofs.csv'.format(output_dir), 'w') as fout:
        fout.write("lemma, status, prooflength\n")
        for filename in filenames:
            with open("{}/{}.csv".format(output_dir, escape_filename(filename)), 'r') \
                 as fin:
                fout.writelines(fin)

def read_csv_options(f : Iterable[str]) -> Tuple[argparse.Namespace, Iterable[str]]:
    params : Dict[str, str] = {}
    f_iter = iter(f)
    final_line = ""
    for line in f_iter:
        param_match = re.match("# (.*): (.*)", line)
        if param_match:
            params[param_match.group(1)] = param_match.group(2)
        else:
            final_line = line
            break
    rest_iter : Iterable[str]
    if final_line == "":
        rest_iter = iter([])
    else:
        rest_iter = itertools.chain([final_line], f_iter)
    return argparse.Namespace(**params), rest_iter

def read_stats_from_csv(output_dir : str, vfilename : str) -> ReportStats:
    num_proofs = 0
    num_proofs_failed = 0
    num_proofs_completed = 0
    with open("{}/{}.csv".format(output_dir, escape_filename(vfilename)),
              'r', newline='') as csvfile:
        saved_args, rest_iter = read_csv_options(csvfile)
        rowreader = csv.reader(rest_iter, lineterminator=os.linesep)
        for row in rowreader:
            num_proofs += 1
            if row[1] == "SearchStatus.SUCCESS":
                num_proofs_completed += 1
            elif row[1] == "SearchStatus.FAILURE":
                num_proofs_failed += 1
            else:
                assert row[1] == "SearchStatus.INCOMPLETE"
    return ReportStats(vfilename, num_proofs, num_proofs_failed, num_proofs_completed)

def combine_file_results(stats : List[ReportStats]) -> ReportStats:
    return ReportStats("",
                       sum([s.num_proofs for s in stats]),
                       sum([s.num_proofs_failed for s in stats]),
                       sum([s.num_proofs_completed for s in stats]))

def get_predictor(parser : argparse.ArgumentParser,
                  args : argparse.Namespace) -> TacticPredictor:
    predictor : TacticPredictor
    if args.weightsfile:
        predictor = loadPredictorByFile(args.weightsfile)
        if args.predictor:
            eprint("Ignoring --predictor because --weightsfile takes precedence")
    elif args.predictor:
        predictor = loadPredictorByName(args.predictor)
    else:
        eprint("You must specify either --weightsfile or --predictor!")
        parser.print_help()
        sys.exit(1)
    return predictor
