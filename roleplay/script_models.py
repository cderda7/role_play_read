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
"current position" in a SceneScript. See checkpoint_runtime.py for the
actual per-checkpoint traversal logic this content is authored for:

  - Student reaches a Checkpoint, picks an option.
  - Canonical option picked -> checkpoint PASSES immediately;
    correct_explanation is shown as reinforcement to every student who
    passes, then the script continues to the next item.
  - Non-canonical option picked -> that option's corrupted_narration is
    shown (short, self-contained, roughly 30 seconds of reading -- NOT a
    long divergent story), then the SAME checkpoint is presented again with
    that option no longer offered.
  - With only 3 options per checkpoint, the worst case is a student who
    tries both wrong options before the canonical one is the only choice
    left -- i.e. they go down both corrupted paths before finally landing
    on the correct one. A student who's right on the first or second try
    never sees the branch they didn't take.

This file only has to supply the pieces checkpoint_runtime.py needs: the
options, which one is canonical, each wrong option's corrupted_narration,
and the checkpoint's correct_explanation.
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

    label: str  # the choice text shown to the student -- a genuine
    # in-character line in the play's own Early Modern English voice (not a
    # modern paraphrase), e.g. 'Match his heat with your own: "Have at thee
    # then, and gladly."' True of the canonical option and every
    # non-canonical option alike.
    is_canonical: bool  # True for the one option that matches what the
    # character actually does in the play at this point.
    corrupted_narration: Optional[str] = None  # Required (non-None) on every
    # non-canonical option; must be None on the canonical option, since
    # there's nothing to corrupt when the student picks the path the play
    # actually takes. Capped at roughly
    # checkpoint_runtime.MAX_CORRUPTED_NARRATION_SECONDS of reading time --
    # shorter than a beat, since a wrong choice re-presents the same
    # checkpoint rather than ending the scene. Spoiler-gated the same as a
    # question (see gate.evaluate_narration_for_spoilers) -- per the
    # explicit design decision that corrupted-branch narration needs the
    # same spoiler gate as questions.


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
    # only in what's been established by the current chapter. Shown to EVERY
    # student who passes this checkpoint, as reinforcement -- not reserved
    # for a student who got it wrong first. Also spoiler-gated: an
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
    exceeds_time_budget: bool = False  # only meaningful for kind ==
    # "corrupted_branch" -- true if this narration is longer than
    # checkpoint_runtime.MAX_CORRUPTED_NARRATION_SECONDS would allow, folded
    # into needs_review the same way a keyword hit is.
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
