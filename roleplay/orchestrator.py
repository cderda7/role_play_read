"""
Role A -- plain orchestration code, not an LLM call. Wires C and B together
while keeping them in separate, non-communicating contexts.

That separation is the actual safety mechanism, not a formality: every LLM
API call is stateless by default, so "three roles in one LLM" doesn't mean
one continuous conversation juggling three personas -- it means three
independent calls, each starting from a blank slate, each seeing only what
this file explicitly puts in front of it. generate_candidate_questions()
(role C) is the only function anywhere in this package that full_play_text
is passed into. evaluate_question_for_spoilers() (role B) never receives it,
never receives C's system prompt, and never receives any indication that a
generator produced the question it's evaluating -- see tests/test_isolation
for this checked structurally, not just asserted in a comment.
"""

from __future__ import annotations

from typing import List, Optional

from .checkpoint_density import CheckpointDensity, checkpoint_density
from .generator import generate_candidate_questions
from .gate import evaluate_narration_for_spoilers, evaluate_question_for_spoilers
from .keyword_gate import check_keyword_spoilers, check_keyword_spoilers_in_text
from .llm_client import LLMClient
from .models import CandidateQuestion, Chapter, GateVerdict, ReviewItem
from .script_generator import generate_scene_script
from .script_models import NarrationReviewItem, ScriptReviewBundle
from .timing import estimate_minutes, meets_timing_target


def orchestrate_chapter(
    full_play_text: str,
    chapters_read_so_far: List[Chapter],
    character: str,
    grade_level: int,
    client: LLMClient,
    question_count: int = 8,
) -> List[ReviewItem]:
    """Generates and gates one chapter's worth of role-play questions for one
    character at one grade level (7-12, from the teacher's thin UI).
    chapters_read_so_far must be ordered and include the current chapter as
    its last element -- that's what defines "what the reader knows so far"
    for role B. grade_level only affects role C's phrasing (see generator.py)
    -- role B's spoiler judgment doesn't depend on the student's grade, so
    it's deliberately not threaded into gate.py."""
    current_chapter = chapters_read_so_far[-1]

    candidates = generate_candidate_questions(
        full_play_text=full_play_text,
        chapter=current_chapter,
        character=character,
        grade_level=grade_level,
        client=client,
        count=question_count,
    )

    review_items: List[ReviewItem] = []
    for candidate in candidates:
        gate_result = evaluate_question_for_spoilers(
            chapters_read_so_far=chapters_read_so_far,
            candidate=candidate,
            client=client,
        )
        keyword_flag = check_keyword_spoilers(candidate)

        # If B offered a rephrase, verify it as a courtesy -- a fresh,
        # separate gate call, same isolation properties as the original.
        # This doesn't skip human review; it just means the reviewer sees
        # "this fix already checks out" instead of having to re-verify it
        # themselves.
        rephrase_gate_result = None
        if gate_result.suggested_rephrase is not None:
            rephrased_candidate = CandidateQuestion(
                chapter_id=candidate.chapter_id,
                character=candidate.character,
                question=gate_result.suggested_rephrase,
                focus=candidate.focus,
                grade_level=candidate.grade_level,
            )
            rephrase_gate_result = evaluate_question_for_spoilers(
                chapters_read_so_far=chapters_read_so_far,
                candidate=rephrased_candidate,
                client=client,
            )

        needs_review = gate_result.verdict != GateVerdict.CLEAR or keyword_flag is not None
        review_items.append(
            ReviewItem(
                question=candidate,
                gate_result=gate_result,
                keyword_flag=keyword_flag,
                needs_review=needs_review,
                rephrase_gate_result=rephrase_gate_result,
            )
        )

    return review_items


def orchestrate_scene_script(
    full_play_text: str,
    chapters_read_so_far: List[Chapter],
    character: str,
    grade_level: int,
    client: LLMClient,
    density: Optional[CheckpointDensity] = None,
) -> ScriptReviewBundle:
    """Generates one chapter's branching role-play script (role C) and gates
    every piece of authored narration that could leak a spoiler (role B),
    same isolation guarantee as orchestrate_chapter: role B's calls here go
    through evaluate_narration_for_spoilers, which -- like
    evaluate_question_for_spoilers -- never receives the full play text or
    any indication a generator produced the text it's judging.

    What gets gated, and why: every non-canonical CheckpointOption's
    corrupted_narration (explicitly required per the "corrupted-branch
    narration needs spoiler gate" design decision), and every Checkpoint's
    correct_explanation (not explicitly specified, but gated for the same
    reason -- an explanation of "why" can leak a future detail just as
    easily as a corrupted-branch narration can). Plain ScriptBeat text is
    NOT individually gated -- see script_generator.py's module docstring for
    why that's a deliberate, documented gap rather than an oversight.

    density defaults to checkpoint_density(current_chapter.text) if not
    given -- pass it explicitly if a caller has already computed it and
    wants to avoid recomputing."""
    current_chapter = chapters_read_so_far[-1]
    if density is None:
        density = checkpoint_density(current_chapter.text)

    script = generate_scene_script(
        full_play_text=full_play_text,
        chapter=current_chapter,
        character=character,
        grade_level=grade_level,
        density=density,
        client=client,
    )

    narration_reviews: List[NarrationReviewItem] = []
    for checkpoint in script.checkpoints():
        for option in checkpoint.options:
            if option.corrupted_narration is None:
                continue
            gate_result = evaluate_narration_for_spoilers(
                chapters_read_so_far=chapters_read_so_far,
                narration_text=option.corrupted_narration,
                client=client,
            )
            keyword_flag = check_keyword_spoilers_in_text(current_chapter.chapter_id, option.corrupted_narration)
            narration_reviews.append(
                NarrationReviewItem(
                    checkpoint_id=checkpoint.checkpoint_id,
                    kind="corrupted_branch",
                    option_label=option.label,
                    text=option.corrupted_narration,
                    gate_result=gate_result,
                    keyword_flag=keyword_flag,
                    needs_review=gate_result.verdict != GateVerdict.CLEAR or keyword_flag is not None,
                )
            )

        explanation_gate_result = evaluate_narration_for_spoilers(
            chapters_read_so_far=chapters_read_so_far,
            narration_text=checkpoint.correct_explanation,
            client=client,
        )
        explanation_keyword_flag = check_keyword_spoilers_in_text(
            current_chapter.chapter_id, checkpoint.correct_explanation
        )
        narration_reviews.append(
            NarrationReviewItem(
                checkpoint_id=checkpoint.checkpoint_id,
                kind="correct_explanation",
                option_label=None,
                text=checkpoint.correct_explanation,
                gate_result=explanation_gate_result,
                keyword_flag=explanation_keyword_flag,
                needs_review=explanation_gate_result.verdict != GateVerdict.CLEAR or explanation_keyword_flag is not None,
            )
        )

    return ScriptReviewBundle(
        script=script,
        narration_reviews=narration_reviews,
        estimated_minutes=estimate_minutes(script),
        meets_timing_target=meets_timing_target(script, density.is_complex),
    )
