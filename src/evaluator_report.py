
from evaluate_state import static_evaluators, loadEvaluatorByFile, loadEvaluatorByName
from models.state_evaluator import StateEvaluator
import serapi_instance
from context_filter import get_context_filter
from format import (TacticContext, ScrapedCommand, ScrapedTactic,
                    strip_scraped_output)
from data import read_all_text_data

from pathlib_revised import Path2
from dataclasses import dataclass
import argparse
import os
from yattag import Doc

from typing import (List, Union, Tuple, Iterable, Callable)

Tag = Callable[..., Doc.Tag]
Text = Callable[..., None]
Line = Callable[..., None]

details_css = ["details.css"]
details_javascript = ["eval-details.js"]
report_css = ["report.css"]
report_js = ["report.js"]
extra_files = details_css + details_javascript + report_css + report_js + ["logo.png"]

@dataclass
class FileSummary:
    correct : int
    total : int
    num_proofs : int

def main(arg_list : List[str]) -> None:

    args = parse_arguments(arg_list)
    evaluator = get_evaluator(args)

    file_summary_results = []

    if not args.output.exists():
        args.output.makedirs()

    for idx, filename in enumerate(args.filenames):
        file_summary_results.append(generate_evaluation_details(args, idx, filename, evaluator))

    if args.generate_index:
        generate_evaluation_index(file_summary_results)

def parse_arguments(arg_list : List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=
        "A report testing the ability of state evaluators")
    parser.add_argument("--prelude", default=".", type=Path2)
    parser.add_argument("--context-filter", default="default")
    parser.add_argument("--no-generate-index", dest="generate_index", action='store_false')
    parser.add_argument("--output", "-o", required="true", type=Path2)
    evaluator_group = parser.add_mutually_exclusive_group(required="true")
    evaluator_group.add_argument('--weightsfile', default=None, type=Path2)
    evaluator_group.add_argument('--evaluator', choices=list(static_evaluators.keys()),
                        default=None)
    parser.add_argument('filenames', nargs="+", help="proof file name (*.v)", type=Path2)
    return parser.parse_args(arg_list)

def get_evaluator(args) -> StateEvaluator:
    evaluator : StateEvaluator
    if args.weightsfile:
        evaluator = loadEvaluatorByFile(args.weightsfile)
    else:
        evaluator = loadEvaluatorByName(args.evaluator)

    return evaluator

@dataclass
class TacticInteraction:
    tactic : str
    context_before : TacticContext

@dataclass
class VernacBlock:
    commands : List[str]

@dataclass
class ProofBlock:
    lemma_statement : str
    proof_interactions : List[TacticInteraction]

def get_blocks(interactions : List[ScrapedCommand]) -> List[Union[VernacBlock, ProofBlock]]:
    def generate() -> Iterable[Union[VernacBlock, ProofBlock]]:
        in_proof = False
        cur_lemma = ""
        interaction_buffer = []
        for interaction in interactions:
            if isinstance(interaction, ScrapedTactic):
                if not in_proof:
                    yield VernacBlock(interaction_buffer[:-1])
                    cur_lemma = interaction_buffer[-1]
                    interaction_buffer = []
                    in_proof = True
            else:
                assert isinstance(interaction, str)
                if in_proof:
                    yield ProofBlock(cur_lemma, interaction_buffer[:-1])
                    interaction_buffer = [interaction_buffer[-1].tactic]
                    in_proof = False
            interaction_buffer.append(interaction)
    return list(generate())

def generate_evaluation_details(args : argparse.Namespace, idx : int,
                                filename : str, evaluator : StateEvaluator) -> FileSummary:
    scrape_path = args.prelude / filename.with_suffix(".v.scrape")
    interactions = list(read_all_text_data(scrape_path))
    context_filter = get_context_filter(args.context_filter)

    num_points = 0
    num_correct = 0
    num_proofs = 0

    def write_vernac(block : VernacBlock):
        nonlocal tag
        nonlocal text
        nonlocal doc
        for command in block.commands:
            with tag('code', klass='plaincommand'):
                text(command.strip("\n"))
            doc.stag('br')

    def generate_proof_evaluation_details(block : ProofBlock, region_idx : int):
        nonlocal num_proofs
        num_proofs += 1

        nonlocal num_points
        proof_length = len(block.proof_interactions)
        num_points += proof_length

        with tag('div', klass='region'):
            nonlocal evaluator
            for idx, interaction in enumerate(block.proof_interactions):
                if interaction.tactic.strip() == "Proof.":
                    with tag('code', klass='plaincommand'):
                        text(interaction.tactic.strip("\n"))
                    doc.stag('br')
                else:
                    distance_from_end = proof_length - idx
                    predicted_distance_from_end = evaluator.scoreState(strip_scraped_output(interaction))
                    grade = grade_prediction(distance_from_end, predicted_distance_from_end)
                    with tag('span',
                             ('data-hyps', "\n".join(interaction.hypotheses)),
                             ('data-goal', interaction.goal),
                             ('data-actual-distance', str(distance_from_end)),
                             ('data-predicted-distance', str(predicted_distance_from_end)),
                             ('data-region', region_idx),
                             ('data-index', idx),
                             klass='tactic'), \
                             tag('code', klass=grade):
                        text(interaction.tactic)


    def write_lemma_button(lemma_statement : str, region_idx : int):
        nonlocal tag
        nonlocal text
        lemma_name = \
            serapi_instance.lemma_name_from_statement(lemma_statement)
        with tag('button', klass='collapsible', id=f'collapsible-{region_idx}'):
            with tag('code', klass='buttontext'):
                text(lemma_statement.strip())

    def grade_prediction(correct_number : int, predicted_number : float) -> str:
        distance = abs(correct_number - predicted_number)
        if distance < 1:
            return "goodcommand"
        elif distance < 5:
            return "okaycommand"
        else:
            return "badcommand"

    doc, tag, text, line = Doc().ttl()
    with tag('html'):
        header(tag, doc, text, details_css, details_javascript, "Proverbot9001 Report")
        with tag('body', onload='init()'), tag('pre'):
            for idx, block in enumerate(get_blocks(interactions)):
                if isinstance(block, VernacBlock):
                    write_vernac(block)
                else:
                    assert isinstance(block, ProofBlock)
                    write_lemma_button(block.lemma_statement, idx)
                    generate_proof_evaluation_details(block, idx)

    base = Path2(os.path.dirname(os.path.abspath(__file__)))
    for extra_filename in extra_files:
        (base.parent / "reports" / extra_filename).copyfile(args.output / extra_filename)

    with (args.output / filename.with_suffix(".html").name).open(mode='w') as fout:
        fout.write(doc.getvalue())

def header(tag : Tag, doc : Doc, text : Text, css : List[str],
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