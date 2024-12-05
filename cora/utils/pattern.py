import fnmatch
from typing import List


def match_all_patterns(s: str, patterns: List[str]):
    return all(fnmatch.fnmatch(s, p) for p in patterns)


def match_any_pattern(s: str, patterns: List[str]):
    return any(fnmatch.fnmatch(s, p) for p in patterns)


def match_no_patterns(s: str, patterns: List[str]):
    return all(not fnmatch.fnmatch(s, p) for p in patterns)
