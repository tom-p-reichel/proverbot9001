

from typing import Any, List

class SVC:
    def __init__(self, gamma:Any='scale',kernel:str='rbf', probability: bool=False,
                 verbose:bool=False) \
        -> None:
        ...
    def fit(self, inputs : List[List[float]], outputs : List[int]) -> None:
        ...
    def score(self, inputs : List[List[float]], outputs : List[int]) -> float:
        ...
    ...
