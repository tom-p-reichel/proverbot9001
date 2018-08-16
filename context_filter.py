#!/usr/bin/env python3

from typing import Dict, Callable
import re

ContextFilter = Callable[[Dict[str, str], str,
                          Dict[str, str]], bool]

def no_compound_or_bullets(in_data : Dict[str, str], tactic : str,
                           next_in_data : Dict[str, str]) -> bool:
    return (not re.match("[\{\}\+\-\*].*", tactic) and
            not re.match(".*;.*", tactic))

def goal_changed(in_data : Dict[str, str], tactic : str,
                 next_in_data : Dict[str, str]) -> bool:
    return (in_data["goal"] != next_in_data["goal"] and
            no_compound_or_bullets(in_data, tactic, next_in_data))

context_filters : Dict[str, ContextFilter] = {
    "default": no_compound_or_bullets,
    "all": lambda *args: True,
    "goal-changes": goal_changed,
}