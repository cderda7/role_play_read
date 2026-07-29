"""
Rough playtime estimate for a SceneScript, used to check it against the
3-minute (standard scene) / 5-minute (complex scene) minimum target for a
student who gets every checkpoint right on the first try.

This is deliberately a rough heuristic, not a precise prediction -- there's
no reliable way to know how long a real student will spend reading a beat or
weighing a decision. The two constants below are estimates, not measured
data (unlike checkpoint_density.py's word-count threshold, which was derived
from the real 24-scene distribution): a slower-than-silent-reading pace,
since this is read-aloud-paced interactive narration rather than silent
skimming, plus a flat per-checkpoint allowance for reading the options and
deciding. Treat this as a tripwire for "this script is clearly too short,
go back and add more" during content review, not as a guarantee students
will spend exactly this long.
"""

from __future__ import annotations

from .script_models import Checkpoint, SceneScript, ScriptBeat

# Words per minute for read-aloud-paced interactive narration -- slower than
# typical silent reading (~200-250 wpm) since the student is role-playing,
# not skimming.
NARRATION_WORDS_PER_MINUTE = 130

# Flat seconds allotted per checkpoint for reading the options and deciding,
# on top of the words in the prompt/options themselves.
SECONDS_PER_CHECKPOINT_DECISION = 25


def estimate_minutes(script: SceneScript) -> float:
    """A first-attempt, everything-right playthrough only ever sees: every
    ScriptBeat's text, and every Checkpoint's prompt plus canonical option's
    label (never a corrupted_narration or correct_explanation -- those are
    only shown on a wrong answer, which this estimate assumes doesn't
    happen)."""
    total_words = 0
    total_seconds = 0.0

    for item in script.items:
        if isinstance(item, ScriptBeat):
            total_words += len(item.text.split())
        elif isinstance(item, Checkpoint):
            total_words += len(item.prompt.split())
            total_words += len(item.canonical_option().label.split())
            total_seconds += SECONDS_PER_CHECKPOINT_DECISION

    total_seconds += (total_words / NARRATION_WORDS_PER_MINUTE) * 60
    return total_seconds / 60


def target_minutes(is_complex: bool) -> float:
    """The minimum-playtime target for a scene of this complexity, per the
    explicit 3-minute (standard: 1 major/3 minor) / 5-minute (complex: 2
    major/5 minor) targets."""
    return 5.0 if is_complex else 3.0


def meets_timing_target(script: SceneScript, is_complex: bool) -> bool:
    return estimate_minutes(script) >= target_minutes(is_complex)
