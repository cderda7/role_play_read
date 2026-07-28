"""
Role C -- the question generator. Sees the full play, writes questions
grounded in complete knowledge of it. Its output is treated as untrusted
input by the rest of the pipeline: every question it writes still has to
clear role B before a human ever sees it, precisely because C is the one
role in this system that's allowed to know things the reader shouldn't yet.
"""

from __future__ import annotations

import json
from typing import List

from .llm_client import LLMClient, LLMMessage
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


def _system_prompt(full_play_text: str) -> str:
    return (
        "You are a literary-analysis question writer with complete "
        "knowledge of this play:\n\n"
        f"{full_play_text}\n\n"
        f"{SPOILER_POLICY}\n\n"
        "Write questions a student role-playing as a given character could "
        "be asked at a given point in the story, covering plot "
        "comprehension, character motivation, theme, and motif. Phrase them "
        "for a reader who has only reached that point in the story -- do "
        "not assume they know what happens later, except for the "
        "broadly-known outcome described above. Respond only through the "
        "required tool call."
    )


def generate_candidate_questions(
    full_play_text: str,
    chapter: Chapter,
    character: str,
    client: LLMClient,
    count: int = 8,
) -> List[CandidateQuestion]:
    user_message = (
        f"Chapter: {chapter.chapter_id}\n"
        f"Character the student is role-playing: {character}\n"
        f"Write {count} questions."
    )
    raw = client.complete(
        system=_system_prompt(full_play_text),
        messages=[LLMMessage(role="user", content=user_message)],
        json_schema=GENERATE_SCHEMA,
    )
    data = json.loads(raw)
    return [
        CandidateQuestion(
            chapter_id=chapter.chapter_id,
            character=character,
            question=item["question"],
            focus=item["focus"],
        )
        for item in data["questions"]
    ]
