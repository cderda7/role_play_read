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

from .llm_client import CACHE_BOUNDARY_MARKER, LLMClient, LLMMessage
from .models import CandidateQuestion, Chapter, GateResult, GateVerdict
from .spoiler_policy import SPOILER_POLICY

GATE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": [v.value for v in GateVerdict]},
        "flagged_phrase": {"type": ["string", "null"]},
        "reasoning": {"type": "string"},
        "suggested_rephrase": {"type": ["string", "null"]},
    },
    "required": ["verdict", "flagged_phrase", "reasoning", "suggested_rephrase"],
}


def _system_prompt(text_kind: str) -> str:
    """text_kind is "question" or "narration" -- the two shapes of text this
    gate is asked to judge. A question is something someone is about to ask
    the reader; a narration is something the reader is about to be shown as
    part of the story itself (e.g. a branching-script beat or a corrupted-
    path consequence). The underlying judgment is the same either way --
    does this text require knowledge the reader doesn't have yet -- but the
    framing has to match what's actually being evaluated, or the model ends
    up reasoning about the wrong thing."""
    if text_kind == "narration":
        task = (
            "You are a student who has read exactly the passage you're about "
            "to be shown, and nothing else in this story. You do not know "
            "how the story continues past that point. Someone is about to "
            "show you a short narration passage that continues the story. "
            "Decide whether that passage reveals or depends on knowing "
            "something that hasn't happened yet in what you've read."
        )
        rephrase_guidance = (
            "If your verdict is SPOILER or UNCERTAIN, consider whether the "
            "passage's dramatic point still lands if the specific future "
            "detail is removed or generalized -- for example, a passage "
            "describing the consequence of a choice can often be rewritten "
            "to describe the immediate, in-scene consequence without naming "
            "anything that happens later. If you can construct such a "
            "revision WITHOUT relying on anything you don't already know "
            "from the passage you were given, put it in suggested_rephrase. "
            "If it can't be salvaged that way, or if your verdict is CLEAR, "
            "leave suggested_rephrase null."
        )
    else:
        task = (
            "You are a student who has read exactly the passage you're about "
            "to be shown, and nothing else in this story. You do not know "
            "how the story continues past that point. Someone is going to "
            "ask you a question. Decide whether answering it would require "
            "knowing something that hasn't happened yet in what you've read."
        )
        rephrase_guidance = (
            "If your verdict is SPOILER or UNCERTAIN, consider whether the "
            "question's underlying analytical goal is still sound once the "
            "specific future reference is removed -- for example, a question "
            "asking how a moment 'foreshadows' a specific later event can "
            "often be generalized into an open-ended version that asks "
            "whether the moment is an example of foreshadowing at all, "
            "without naming what it foreshadows. If you can construct such a "
            "rephrasing WITHOUT relying on anything you don't already know "
            "from the passage you were given, put it in suggested_rephrase. "
            "If the question can't be salvaged that way, or if your verdict "
            "is CLEAR, leave suggested_rephrase null."
        )

    # This whole prompt is 100% identical across EVERY call this function
    # ever makes for a given text_kind -- it doesn't depend on chapter,
    # character, grade, or the text being judged. Marking it entirely
    # cacheable means every gate call after the first (for a given
    # text_kind, within the cache's TTL) skips paying full price for this
    # prompt -- see llm_client.py's module docstring.
    return (
        f"{task}\n\n{SPOILER_POLICY}\n\n{rephrase_guidance}\n\n"
        f"Respond only through the required tool call.{CACHE_BOUNDARY_MARKER}"
    )


def evaluate_text_for_spoilers(
    chapters_read_so_far: List[Chapter],
    text: str,
    text_kind: str,
    client: LLMClient,
) -> GateResult:
    """The general-purpose gate call underneath evaluate_question_for_spoilers
    and evaluate_narration_for_spoilers. The only inputs are the raw text
    read so far and the bare text being judged -- nothing about how that text
    was produced. This function's signature is itself part of the safety
    design: there is no parameter through which C's prompt or output could be
    passed into this call without changing the signature, which makes an
    accidental leak a visible code change rather than a silent one.

    text_kind must be "question" or "narration" -- it only changes the
    framing in the prompt (see _system_prompt), never what's included in the
    call."""
    if text_kind not in ("question", "narration"):
        raise ValueError(f"text_kind must be 'question' or 'narration', got {text_kind!r}")

    reader_text = "\n\n".join(ch.text for ch in chapters_read_so_far)
    label = "Question someone just asked you" if text_kind == "question" else "Passage someone is about to show you"
    # reader_text is identical across every gate call made within one
    # orchestrate_chapter/orchestrate_scene_script run (chapters_read_so_far
    # doesn't change mid-run), and by late chapters it can be nearly as large
    # as the whole play -- so it's marked cacheable the same way, with only
    # the bare question/narration text kept variable after the marker.
    user_message = f"What you've read so far:\n{reader_text}{CACHE_BOUNDARY_MARKER}\n\n{label}: {text}"

    raw = client.complete(
        system=_system_prompt(text_kind),
        messages=[LLMMessage(role="user", content=user_message)],
        json_schema=GATE_SCHEMA,
    )
    data = json.loads(raw)
    return GateResult(
        verdict=GateVerdict(data["verdict"]),
        flagged_phrase=data.get("flagged_phrase"),
        reasoning=data["reasoning"],
        suggested_rephrase=data.get("suggested_rephrase"),
    )


def evaluate_question_for_spoilers(
    chapters_read_so_far: List[Chapter],
    candidate: CandidateQuestion,
    client: LLMClient,
) -> GateResult:
    """Role B for a role-play question. Thin wrapper over
    evaluate_text_for_spoilers -- kept as its own function because it's the
    one most of this codebase (and its tests) already calls by name."""
    return evaluate_text_for_spoilers(chapters_read_so_far, candidate.question, "question", client)


def evaluate_narration_for_spoilers(
    chapters_read_so_far: List[Chapter],
    narration_text: str,
    client: LLMClient,
) -> GateResult:
    """Role B for a piece of authored narration -- a branching-script beat's
    corrupted-path consequence, or the explanation of why the canonical
    choice at a checkpoint is correct. Same isolation guarantee as
    evaluate_question_for_spoilers: only the text read so far and the bare
    narration text are passed in, nothing about the script or the checkpoint
    it belongs to."""
    return evaluate_text_for_spoilers(chapters_read_so_far, narration_text, "narration", client)
