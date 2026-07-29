"""
Role C -- the question generator. Sees the full play, writes questions
grounded in complete knowledge of it. Its output is treated as untrusted
input by the rest of the pipeline: every question it writes still has to
clear role B before a human ever sees it, precisely because C is the one
role in this system that's allowed to know things the reader shouldn't yet.
"""

from __future__ import annotations

from typing import List

from .llm_client import CACHE_BOUNDARY_MARKER, LLMClient, call_structured
from .models import CandidateQuestion, Chapter
from .spoiler_policy import SPOILER_POLICY

GENERATE_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "focus": {
                        "type": "string",
                        "enum": ["plot", "motivation", "theme", "motif"],
                    },
                },
                "required": ["question", "focus"],
            },
        }
    },
    "required": ["questions"],
}


GRADE_MIN = 7
GRADE_MAX = 12


def _system_prompt(full_play_text: str, grade_level: int) -> str:
    # Everything up through the CACHE_BOUNDARY_MARKER is identical on EVERY
    # call this function ever makes for this play, regardless of character,
    # chapter, or grade -- full_play_text is ~45k tokens and dominates the
    # cost of every generator call, so this is exactly the prefix Anthropic's
    # prompt caching (see llm_client.py's module docstring) is for. Only
    # grade_level varies, and it's kept strictly after the marker.
    cacheable_prefix = (
        "You are a literary-analysis question writer with complete "
        "knowledge of this play:\n\n"
        f"{full_play_text}\n\n"
        f"{SPOILER_POLICY}\n\n"
        "Write questions a student role-playing as a given character could "
        "be asked at a given point in the story, covering plot "
        "comprehension, character motivation, theme, and motif. Phrase them "
        "for a reader who has only reached that point in the story -- do "
        "not assume they know what happens later, except for the "
        "broadly-known outcome described above."
    )
    variable_suffix = (
        f"The student is in grade {grade_level} (on a 7-12 scale). Calibrate "
        "vocabulary, sentence complexity, and how much scaffolding the "
        "question itself provides to that grade -- a grade 7 question should "
        "still be genuinely analytical, not simplified into a factual-recall "
        "question, but it should lean on more concrete, directly-textual "
        "language; a grade 12 question can carry more abstraction, ambiguity, "
        "and open-endedness. Don't flatten every grade to the same phrasing.\n\n"
        "Respond only through the required tool call."
    )
    return cacheable_prefix + CACHE_BOUNDARY_MARKER + variable_suffix


def generate_candidate_questions(
    full_play_text: str,
    chapter: Chapter,
    character: str,
    grade_level: int,
    client: LLMClient,
    count: int = 8,
) -> List[CandidateQuestion]:
    if not GRADE_MIN <= grade_level <= GRADE_MAX:
        raise ValueError(f"grade_level must be between {GRADE_MIN} and {GRADE_MAX}, got {grade_level}")

    user_message = (
        f"Chapter: {chapter.chapter_id}\n"
        f"Character the student is role-playing: {character}\n"
        f"Write {count} questions."
    )
    data = call_structured(client, _system_prompt(full_play_text, grade_level), user_message, GENERATE_SCHEMA)
    return [
        CandidateQuestion(
            chapter_id=chapter.chapter_id,
            character=character,
            question=item["question"],
            focus=item["focus"],
            grade_level=grade_level,
        )
        for item in data["questions"]
    ]
