#!/usr/bin/env python3

from models.tactic_predictor import \
    (TacticPredictor, TacticContext, Prediction, embed_data,
     predictKTactics, predictKTacticsWithLoss,
     predictKTacticsWithLoss_batch)
from models.components import Embedding
from data import (Sentence, RawDataset,
                  normalizeSentenceLength)
from serapi_instance import get_stem

from typing import (List, Any, Tuple, NamedTuple, Dict, Sequence,
                    cast, Optional)

from dataclasses import dataclass
import threading
import argparse
import re
from argparse import Namespace

class RegexPredictor(TacticPredictor):
    def __init__(self) -> None:
        pass

    def getOptions(self) -> List[Tuple[str, str]]:
        pass

    def predictKTacticsWithLoss_batch(self,
                                      in_datas : List[TacticContext],
                                      k : int, correct : List[str]) -> \
                                      Tuple[List[List[Prediction]], float]:
        predictions = [self.predictKTactics(in_data, k) for in_data in in_datas]
        return predictions, 0.0
        pass
    def predictKTactics(self, in_data : TacticContext, k : int) -> List[Prediction]:
        if re.match(in_data.goal.strip(), "forall"):
            return [Prediction("intros.", 1.0),
                    Prediction("eauto.", 0.1)]
        else:
            return [Prediction("eauto.", 1.0),
                    Prediction("intros.", 0.1)]
        pass
    pass

def main(arg_list : List[str]) -> None:
    predictor = RegexPredictor()
    # predictor.train(arg_list)
