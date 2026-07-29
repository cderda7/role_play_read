"""
Runtime logic for how a student moves through a single Checkpoint once it's
presented. Unlike everything else in this package, this isn't about
deciding what content to author -- it's about deciding what happens as a
student makes choices against ALREADY AUTHORED content. It doesn't call an
LLM and doesn't need a live app to exist to be tested; it's included here
(rather than deferred entirely to "a future interactive app") because the
decision logic itself is simple, pure, and worth getting right and testing
now, even though the actual chat surface that will drive it doesn't exist
yet.

DESIGN (supersedes the earlier "corrupted path grows until the student
restarts the whole scene" model):

  - A checkpoint has exactly one canonical option and (currently) two
    non-canonical options, each with a short corrupted_narration capped at
    roughly MAX_CORRUPTED_NARRATION_SECONDS of reading time.
  - Picking the canonical option PASSES the checkpoint immediately.
    correct_explanation is shown as reinforcement to every student who
    passes -- not reserved for a student who got it wrong first.
  - Picking a non-canonical option shows that option's corrupted_narration
    (a brief, self-contained consequence -- NOT a long divergent story),
    then the SAME checkpoint is re-presented with that option removed from
    the menu, so the student can't repeat the identical wrong choice.
  - With only 3 options total, the worst case is a student who picks both
    wrong options before the canonical one is the only choice left -- i.e.
    they go down both corrupted paths before finally landing on the correct
    one. A student who gets it right on the first or second try never sees
    the branch they didn't take forced on them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List

from .script_models import Checkpoint, CheckpointOption
from .timing import NARRATION_WORDS_PER_MINUTE

# How long a corrupted-branch narration should take to read aloud. Shorter
# than a beat on purpose -- a wrong choice should cost the student a brief,
# self-contained detour, not a scene's worth of extra reading.
MAX_CORRUPTED_NARRATION_SECONDS = 30

# Word budget implied by MAX_CORRUPTED_NARRATION_SECONDS at the same
# read-aloud pace timing.py uses for the whole-scene estimate -- kept in
# sync deliberately rather than picking an independent pace for this one
# piece of content.
MAX_CORRUPTED_NARRATION_WORDS = int(MAX_CORRUPTED_NARRATION_SECONDS / 60 * NARRATION_WORDS_PER_MINUTE)


def corrupted_narration_seconds(text: str) -> float:
    return (len(text.split()) / NARRATION_WORDS_PER_MINUTE) * 60


def exceeds_corrupted_narration_budget(text: str) -> bool:
    """True if this corrupted_narration is longer than the ~30-second
    target -- a signal for the (future) review screen to flag it for
    trimming, same spirit as timing.meets_timing_target() for the whole
    scene."""
    return corrupted_narration_seconds(text) > MAX_CORRUPTED_NARRATION_SECONDS


class CheckpointOutcome(str, Enum):
    PASSED = "PASSED"  # canonical option chosen -- checkpoint is done
    CORRUPTED = "CORRUPTED"  # wrong option chosen -- show its narration,
    # then re-present the checkpoint with that option no longer offered


@dataclass(frozen=True)
class CheckpointResult:
    outcome: CheckpointOutcome
    narration: str  # correct_explanation on PASSED, corrupted_narration on CORRUPTED
    checkpoint_complete: bool


@dataclass
class CheckpointAttempt:
    """Tracks one student's live progress through a single Checkpoint.
    Nothing here is authored content -- it's the mutable state a runtime
    app would hold for the duration of one checkpoint, discarded once the
    checkpoint is passed."""

    checkpoint: Checkpoint
    exhausted_option_labels: List[str] = field(default_factory=list)

    def remaining_options(self) -> List[CheckpointOption]:
        """Options the student hasn't already tried (and been corrupted by)
        at this checkpoint -- what a runtime UI should actually offer."""
        return [opt for opt in self.checkpoint.options if opt.label not in self.exhausted_option_labels]

    def choose(self, option_label: str) -> CheckpointResult:
        """Record a student's choice at this checkpoint. Raises ValueError
        if option_label isn't currently offered -- callers should only ever
        present remaining_options() to the student, so this indicates a
        caller bug (stale option list) rather than a normal wrong answer."""
        remaining = {opt.label: opt for opt in self.remaining_options()}
        if option_label not in remaining:
            raise ValueError(
                f"{option_label!r} is not an available choice at this checkpoint "
                f"(already tried, or not a recognized option). Available: "
                f"{sorted(remaining)}"
            )

        option = remaining[option_label]
        if option.is_canonical:
            return CheckpointResult(
                outcome=CheckpointOutcome.PASSED,
                narration=self.checkpoint.correct_explanation,
                checkpoint_complete=True,
            )

        self.exhausted_option_labels.append(option_label)
        return CheckpointResult(
            outcome=CheckpointOutcome.CORRUPTED,
            narration=option.corrupted_narration,
            checkpoint_complete=False,
        )
