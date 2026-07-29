"""
How many decision checkpoints a scene's branching script should get, scaled
by scene length as a proxy for complexity. Word count is a rough proxy --
not a measure of dramatic complexity -- but it's computable and consistent,
same trade-off as character_selector.py's turn-count heuristic.

COMPLEXITY_WORD_THRESHOLD = 1400 was picked by looking at the actual
distribution across all 24 scenes in data/chapters.json: word counts range
247-2703, and 1400 sits in a gap between two loose clusters (13 scenes
below it, 11 above), rather than being an arbitrary round number or a strict
median split (the median, ~938, sits inside the lower cluster and would
misclassify several mid-length scenes as complex). Revisit this if the
source text changes or if the resulting major/minor counts don't feel right
once applied to real scenes.
"""

from __future__ import annotations

from dataclasses import dataclass

COMPLEXITY_WORD_THRESHOLD = 1400

STANDARD_MAJOR = 1
STANDARD_MINOR_MIN = 3

COMPLEX_MAJOR = 2
COMPLEX_MINOR_MIN = 5


@dataclass(frozen=True)
class CheckpointDensity:
    major: int
    minor_min: int
    is_complex: bool


def checkpoint_density(chapter_text: str) -> CheckpointDensity:
    word_count = len(chapter_text.split())
    is_complex = word_count >= COMPLEXITY_WORD_THRESHOLD
    if is_complex:
        return CheckpointDensity(major=COMPLEX_MAJOR, minor_min=COMPLEX_MINOR_MIN, is_complex=True)
    return CheckpointDensity(major=STANDARD_MAJOR, minor_min=STANDARD_MINOR_MIN, is_complex=False)
