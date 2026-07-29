"""
Regression coverage for checkpoint_runtime.py's traversal logic: pass
immediately on the canonical choice, corrupt-and-retry on a wrong choice
with that option removed from the menu, and the worst case (both wrong
options tried) before the canonical one is the only choice left.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from roleplay.checkpoint_runtime import (
    MAX_CORRUPTED_NARRATION_WORDS,
    CheckpointAttempt,
    CheckpointOutcome,
    exceeds_corrupted_narration_budget,
)
from roleplay.script_models import Checkpoint, CheckpointKind, CheckpointOption


def _checkpoint():
    return Checkpoint(
        checkpoint_id="act1_scene1_cp0",
        kind=CheckpointKind.MAJOR,
        prompt="The brawl breaks out. What do you do?",
        options=[
            CheckpointOption('Step in: "Part, fools! Put up your swords."', is_canonical=True),
            CheckpointOption(
                'Draw and join in: "Have at thee, coward!"',
                is_canonical=False,
                corrupted_narration="You wade in swinging instead of parting them.",
            ),
            CheckpointOption(
                'Turn away: "I\'ll not meddle in this."',
                is_canonical=False,
                corrupted_narration="You hang back, and the brawl drags on without you.",
            ),
        ],
        correct_explanation="Benvolio steps in to keep the peace, consistent with his role as peacemaker.",
    )


def test_choosing_canonical_option_passes_immediately():
    attempt = CheckpointAttempt(checkpoint=_checkpoint())
    result = attempt.choose('Step in: "Part, fools! Put up your swords."')
    assert result.outcome == CheckpointOutcome.PASSED
    assert result.checkpoint_complete is True
    assert result.narration == "Benvolio steps in to keep the peace, consistent with his role as peacemaker."


def test_choosing_a_wrong_option_corrupts_and_does_not_complete():
    attempt = CheckpointAttempt(checkpoint=_checkpoint())
    result = attempt.choose('Draw and join in: "Have at thee, coward!"')
    assert result.outcome == CheckpointOutcome.CORRUPTED
    assert result.checkpoint_complete is False
    assert result.narration == "You wade in swinging instead of parting them."


def test_a_tried_wrong_option_is_removed_from_remaining_options():
    attempt = CheckpointAttempt(checkpoint=_checkpoint())
    assert len(attempt.remaining_options()) == 3
    attempt.choose('Draw and join in: "Have at thee, coward!"')
    remaining_labels = {opt.label for opt in attempt.remaining_options()}
    assert 'Draw and join in: "Have at thee, coward!"' not in remaining_labels
    assert len(remaining_labels) == 2


def test_worst_case_both_wrong_options_before_the_canonical_one_remains():
    attempt = CheckpointAttempt(checkpoint=_checkpoint())
    r1 = attempt.choose('Draw and join in: "Have at thee, coward!"')
    assert r1.outcome == CheckpointOutcome.CORRUPTED
    r2 = attempt.choose('Turn away: "I\'ll not meddle in this."')
    assert r2.outcome == CheckpointOutcome.CORRUPTED

    # Only the canonical option is left standing.
    remaining = attempt.remaining_options()
    assert len(remaining) == 1
    assert remaining[0].is_canonical is True

    r3 = attempt.choose(remaining[0].label)
    assert r3.outcome == CheckpointOutcome.PASSED
    assert r3.checkpoint_complete is True


def test_choosing_an_already_exhausted_or_unknown_option_raises():
    attempt = CheckpointAttempt(checkpoint=_checkpoint())
    attempt.choose('Draw and join in: "Have at thee, coward!"')
    with pytest.raises(ValueError):
        attempt.choose('Draw and join in: "Have at thee, coward!"')  # already tried
    with pytest.raises(ValueError):
        attempt.choose("Something not offered at all")


def test_exceeds_corrupted_narration_budget():
    short_text = "You wade in swinging instead of parting them."
    long_text = " ".join(["word"] * (MAX_CORRUPTED_NARRATION_WORDS + 20))
    assert exceeds_corrupted_narration_budget(short_text) is False
    assert exceeds_corrupted_narration_budget(long_text) is True
