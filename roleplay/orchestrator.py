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

from typing import List

from .generator import generate_candidate_questions
from .gate import evaluate_question_for_spoilers
from .keyword_gate import check_keyword_spoilers
from .llm_client import LLMClient
from .models import Chapter, GateVerdict, ReviewItem


def orchestrate_chapter(
    full_play_text: str,
    chapters_read_so_far: List[Chapter],
    character: str,
    client: LLMClient,
    question_count: int = 8,
) -> List[ReviewItem]:
    """Generates and gates one chapter's worth of role-play questions for one
    character. chapters_read_so_far must be ordered and include the current
    chapter as its last element -- that's what defines "what the reader
    knows so far" for role B."""
    current_chapter = chapters_read_so_far[-1]

    candidates = generate_candidate_questions(
        full_play_text=full_play_text,
        chapter=current_chapter,
        character=character,
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

        needs_review = gate_result.verdict != GateVerdict.CLEAR or keyword_flag is not None
        review_items.append(
            ReviewItem(
                question=candidate,
                gate_result=gate_result,
                keyword_flag=keyword_flag,
                needs_review=needs_review,
            )
        )

    return review_items
