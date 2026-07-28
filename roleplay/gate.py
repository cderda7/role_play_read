"""
Role B -- the spoiler gate. See models.py's module docstring for the role
breakdown. The one rule this file exists to enforce: B is constructed fresh,
per question, and is given ONLY the chapter text through the current
checkpoint plus the bare question string. It must never receive C's system
prompt, C's reasoning, or any indication that a generator exists at all --
if that ever leaks in, the isolation this whole design depends on is gone.

Restricting the CONTEXT this way does not make the model actually ignorant
of how the play ends -- it's the same underlying model as C, trained on the
same data, and this play in particular is about as widely-known as text
gets. What this buys is a model instructed and framed to behave as if
constrained, which is a real mitigation (see the module docstring in
orchestrator.py for how it's meant to be used -- as one signal among
several, feeding human review, not a standalone guarantee).
"""

from __future__ import annotations

import json
from typing import List

from .llm_client import LLMClient, LLMMessage
from .models import CandidateQuestion, Chapter, GateResult, GateVerdict
from .spoiler_policy import SPOILER_POLICY

GATE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": [v.value for v in GateVerdict]},
        "flagged_phrase": {"type": ["string", "null"]},
        "reasoning": {"type": "string"},
    },
    "required": ["verdict", "flagged_phrase", "reasoning"],
}


def _system_prompt() -> str:
    return (
        "You are a student who has read exactly the passage you're about to "
        "be shown, and nothing else in this story. You do not know how the "
        "story continues past that point. Someone is going to ask you a "
        "question. Decide whether answering it would require knowing "
        "something that hasn't happened yet in what you've read.\n\n"
        f"{SPOILER_POLICY}\n\n"
        "Respond only through the required tool call."
    )


def evaluate_question_for_spoilers(
    chapters_read_so_far: List[Chapter],
    candidate: CandidateQuestion,
    client: LLMClient,
) -> GateResult:
    """The only inputs are the raw text read so far and the bare question --
    nothing about how the question was produced. This function's signature
    is itself part of the safety design: there is no parameter through which
    C's prompt or output could be passed into this call without changing the
    signature, which makes an accidental leak a visible code change rather
    than a silent one."""
    reader_text = "\n\n".join(ch.text for ch in chapters_read_so_far)
    user_message = (
        f"What you've read so far:\n{reader_text}\n\n"
        f"Question someone just asked you: {candidate.question}"
    )

    raw = client.complete(
        system=_system_prompt(),
        messages=[LLMMessage(role="user", content=user_message)],
        json_schema=GATE_SCHEMA,
    )
    data = json.loads(raw)
    return GateResult(
        verdict=GateVerdict(data["verdict"]),
        flagged_phrase=data.get("flagged_phrase"),
        reasoning=data["reasoning"],
    )
