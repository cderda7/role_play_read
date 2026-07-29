"""
Regression coverage for timing.py's playtime estimate against the explicit
3-minute (standard scene) / 5-minute (complex scene) minimum targets.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from roleplay.script_models import Checkpoint, CheckpointKind, CheckpointOption, SceneScript, ScriptBeat
from roleplay.timing import estimate_minutes, meets_timing_target, target_minutes


def _beat(i, words):
    return ScriptBeat(beat_id=f"b{i}", text=" ".join(["word"] * words))


def _checkpoint(i, kind):
    return Checkpoint(
        checkpoint_id=f"cp{i}",
        kind=kind,
        prompt="What do you do?",
        options=[
            CheckpointOption(label="Do the canonical thing.", is_canonical=True),
            CheckpointOption(label="Do something else.", is_canonical=False, corrupted_narration="It goes badly."),
        ],
        correct_explanation="Because that's what happens in the play.",
    )


def test_target_minutes_matches_standard_and_complex_thresholds():
    assert target_minutes(is_complex=False) == 3.0
    assert target_minutes(is_complex=True) == 5.0


def test_a_short_script_does_not_meet_the_standard_target():
    script = SceneScript(
        chapter_id="act5_scene2",
        character="Friar John",
        grade_level=9,
        items=[_beat(0, 20), _checkpoint(0, CheckpointKind.MINOR)],
    )
    assert estimate_minutes(script) < target_minutes(is_complex=False)
    assert meets_timing_target(script, is_complex=False) is False


def test_a_long_enough_script_meets_the_standard_target():
    # ~130 wpm target -> a few hundred words of narration plus a couple of
    # checkpoints' decision time comfortably clears 3 minutes.
    items = [_beat(i, 120) for i in range(4)]
    items.insert(2, _checkpoint(0, CheckpointKind.MAJOR))
    items.append(_checkpoint(1, CheckpointKind.MINOR))
    script = SceneScript(chapter_id="act1_scene1", character="Benvolio", grade_level=9, items=items)
    assert meets_timing_target(script, is_complex=False) is True


def test_estimate_only_counts_canonical_path_text_not_corrupted_narration():
    """A first-attempt, everything-right playthrough never sees a
    corrupted_narration or correct_explanation -- padding those shouldn't
    inflate the estimate."""
    short_options_script = SceneScript(
        chapter_id="act5_scene2",
        character="Friar John",
        grade_level=9,
        items=[_checkpoint(0, CheckpointKind.MINOR)],
    )
    baseline = estimate_minutes(short_options_script)

    padded_checkpoint = Checkpoint(
        checkpoint_id="cp0",
        kind=CheckpointKind.MINOR,
        prompt="What do you do?",
        options=[
            CheckpointOption(label="Do the canonical thing.", is_canonical=True),
            CheckpointOption(
                label="Do something else.",
                is_canonical=False,
                corrupted_narration=" ".join(["padding"] * 500),
            ),
        ],
        correct_explanation=" ".join(["padding"] * 500),
    )
    padded_script = SceneScript(
        chapter_id="act5_scene2", character="Friar John", grade_level=9, items=[padded_checkpoint]
    )
    assert estimate_minutes(padded_script) == baseline
