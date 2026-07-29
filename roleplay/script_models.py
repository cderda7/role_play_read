"""
Data model for the branching role-play script: the checkpoint-based
narration structure that sits alongside (and reuses) the Q&A pipeline's
spoiler-gating machinery from gate.py and keyword_gate.py.

A scene's SceneScript is a sequence of ScriptBeat (plain narration, no
student input) and Checkpoint (a decision point) items, in the order the
student encounters them while playing through the scene as their assigned
character. See checkpoint_density.py for how many major/minor checkpoints a
given scene gets, and timing.py for how beat/checkpoint count maps to the
3-minute (standard) / 5-minute (complex) minimum playtime target.

RUNTIME vs. AUTHORING BOUNDARY -- read this before wiring this into an app:
everything in this file is AUTHORED CONTENT, produced offline by the
pipeline and reviewed by a human before it's used. Nothing here tracks a
particular student's live attempt state -- there's no "attempt count" or
"current position" in a SceneScript. That belongs to a future interactive
runtime, which will consume this content and drive it through per-student
session state:

  - Student reaches a Checkpoint, picks an option.
  - Canonical option picked -> continue to the next item in the script.
  - Non-canonical option picked, FIRST time at this checkpoint -> show that
    option's corrupted_narration (short, terminates quickly -- not a long
    divergent story), then the student restarts the scene.
  - Non-canonical option picked, SECOND time at the SAME checkpoint (i.e.
    the student restarted and got this exact checkpoint wrong again) -> skip
    the corrupted narration entirely, show the checkpoint's
    correct_explanation directly, then the student restarts.

This file only has to supply the pieces that runtime needs for both of those
branches; it doesn't implement the branching logic itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Union

from .models import GateResult, KeywordFlag


class CheckpointKind(str, Enum):
    MAJOR = "MAJOR"
    MINOR = "MINOR"


@dataclass(frozen=True)
class CheckpointOption:
    """One choice offered at a checkpoint."""

    label: str  # the choice text shown to the student, e.g. "Draw your
    # sword and join the fight" -- written in-character, describing an
    # action the role-played character could plausibly take at this moment.
    is_canonical: bool  # True for the one option that matches what the
    # character actually does in the play at this point.
    corrupted_narration: Optional[str] = None  # Required (non-None) on every
    # non-canonical option; must be None on the canonical option, since
    # there's nothing to corrupt when the student picks the path the play
    # actually takes. 2-5 sentences, spoiler-gated the same as a question
    # (see gate.evaluate_narration_for_spoilers) -- per the explicit design
    # decision that corrupted-branch narration needs the same spoiler gate
    # as questions.


@dataclass(frozen=True)
class Checkpoint:
    """A decision point in the script. Presented to the student as a short,
    in-character prompt plus a small set of options, exactly one of which is
    canonical."""

    checkpoint_id: str
    kind: CheckpointKind
    prompt: str  # what the student is asked to decide, framed in-character
    options: List[CheckpointOption]
    correct_explanation: str  # WHY the canonical option is correct, grounded
    # only in what's been established by the current chapter. Surfaced to
    # the student directly (not as a corrupted branch) the second time they
    # get this same checkpoint wrong -- the "terminate quickly, don't send
    # them down a second divergent story" design. Also spoiler-gated: an
    # explanation of "why" can just as easily leak a future detail as a
    # corrupted-branch narration can, so it goes through the same check even
    # though only the corrupted-branch case was explicitly specified.

    def canonical_option(self) -> CheckpointOption:
        canonical = [opt for opt in self.options if opt.is_canonical]
        if len(canonical) != 1:
            raise ValueError(
                f"Checkpoint {self.checkpoint_id!r} must have exactly one canonical option, "
                f"found {len(canonical)}."
            )
        return canonical[0]


@dataclass(frozen=True)
class ScriptBeat:
    """A stretch of plain narration between checkpoints -- 2-5 sentences,
    grounded in what actually happens in the scene, retold from the
    role-playing character's point of view. Not currently run through the
    spoiler gate individually -- see script_generator.py's module docstring
    for why, and for the known gap that leaves."""

    beat_id: str
    text: str


ScriptItem = Union[ScriptBeat, Checkpoint]


@dataclass(frozen=True)
class SceneScript:
    """The full ordered sequence of beats and checkpoints for one chapter +
    character. `items` preserves presentation order."""

    chapter_id: str
    character: str
    grade_level: int
    items: List[ScriptItem]

    def checkpoints(self) -> List[Checkpoint]:
        return [item for item in self.items if isinstance(item, Checkpoint)]

    def major_count(self) -> int:
        return sum(1 for cp in self.checkpoints() if cp.kind == CheckpointKind.MAJOR)

    def minor_count(self) -> int:
        return sum(1 for cp in self.checkpoints() if cp.kind == CheckpointKind.MINOR)


@dataclass
class NarrationReviewItem:
    """One piece of authored narration text -- a corrupted-branch narration
    or a correct-answer explanation -- run through the spoiler gate. Same
    review pattern as ReviewItem in models.py: needs_review is true if
    either the LLM gate or the deterministic keyword backstop flags it, and
    approved only ever flips true from a human review screen."""

    checkpoint_id: str
    kind: str  # "corrupted_branch" | "correct_explanation"
    option_label: Optional[str]  # set for "corrupted_branch" (which option's
    # consequence this is); None for "correct_explanation", which belongs to
    # the checkpoint as a whole rather than to one option.
    text: str
    gate_result: GateResult
    keyword_flag: Optional[KeywordFlag] = None
    needs_review: bool = False
    approved: bool = False


@dataclass
class ScriptReviewBundle:
    """What lands on the (future) script-review screen for one chapter +
    character: the authored script itself, every narration item that went
    through the spoiler gate, and a rough playtime estimate so a reviewer
    can see at a glance whether this script is likely to meet the 3-minute
    (standard) / 5-minute (complex) minimum before approving it."""

    script: SceneScript
    narration_reviews: List[NarrationReviewItem]
    estimated_minutes: float
    meets_timing_target: bool

    def flagged_narration(self) -> List[NarrationReviewItem]:
        return [item for item in self.narration_reviews if item.needs_review]
