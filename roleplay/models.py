"""
Data model for the character role-play question pipeline.

Three roles collaborate to produce a chapter's worth of role-play questions,
each an ISOLATED LLM call (see orchestrator.py's docstring for why isolation
-- not shared conversation state -- is what actually keeps the spoiler gate
honest):

  C (generator)    -- sees the full play text. Writes candidate questions for
                       a character at a given chapter, using complete
                       knowledge of the whole play to make them insightful.
  B (gate)         -- sees ONLY the text through the current chapter, plus a
                       bare candidate question. Judges whether answering it
                       would require knowledge the reader doesn't have yet.
                       Never sees C's prompt, C's reasoning, or the fact that
                       a generator produced the question at all.
  A (orchestrator) -- plain code, not an LLM call. Calls C, then calls B once
                       per candidate in a fresh, separate context, merges in
                       the deterministic keyword check, and decides what
                       needs a human's eyes before it ships.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class GateVerdict(str, Enum):
    CLEAR = "CLEAR"
    SPOILER = "SPOILER"
    UNCERTAIN = "UNCERTAIN"


@dataclass(frozen=True)
class Chapter:
    """One reading checkpoint. For this play that's an Act/Scene grouping,
    but the pipeline doesn't care what a "chapter" is for any given book --
    it just needs an id, its position in reading order, and its text."""

    chapter_id: str  # e.g. "act1_scene1"
    order: int  # position in reading order, 0-indexed
    text: str


@dataclass(frozen=True)
class CandidateQuestion:
    chapter_id: str
    character: str  # which character the student is role-playing
    question: str
    focus: str  # "plot" | "motivation" | "theme" | "motif" -- loosely typed
    # on purpose; tighten into a real enum once actual content shows which
    # buckets are worth distinguishing in the review screen.
    grade_level: int  # 7-12, from the teacher's thin UI -- carried on the
    # question itself (not just passed as a generation-time argument) so the
    # review screen can show what grade a question was actually calibrated
    # for, and so re-reviewing old content later doesn't require re-deriving
    # that context from elsewhere.


@dataclass(frozen=True)
class GateResult:
    verdict: GateVerdict
    flagged_phrase: Optional[str]  # the specific span B is objecting to, if any
    reasoning: str
    suggested_rephrase: Optional[str] = None  # populated only when verdict is
    # SPOILER/UNCERTAIN and B judges the question's underlying analytical
    # intent is sound but leans on specifics the reader doesn't have yet --
    # e.g. "how does X foreshadow Y" rephrased to "how might X be an example
    # of foreshadowing", with Y's specifics dropped rather than the whole
    # question discarded. B can make this call without needing any knowledge
    # it doesn't have: recognizing that a specific reference is doing work it
    # shouldn't, and generalizing it away, doesn't require knowing what the
    # reference actually points to.


@dataclass(frozen=True)
class KeywordFlag:
    matched_term: str


@dataclass
class ReviewItem:
    """What lands on the (future) question-review screen. One per candidate
    question. needs_review is the union of both independent checks -- the
    LLM gate and the deterministic keyword backstop -- so either one alone
    is enough to require a human look."""

    question: CandidateQuestion
    gate_result: GateResult
    keyword_flag: Optional[KeywordFlag]
    needs_review: bool
    rephrase_gate_result: Optional[GateResult] = None  # if gate_result carried
    # a suggested_rephrase, this is that rephrase run back through the SAME
    # gate call as a courtesy -- so the reviewer sees "yes, this fix actually
    # verifies clean" instead of having to re-check it themselves. Still
    # surfaced for human approval either way; this doesn't auto-ship anything.
    approved: bool = False  # only ever flips true from the human review
    # screen -- nothing in this pipeline sets it
