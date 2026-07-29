"""
Role C, branching-script variant. Same role as generator.py (sees the full
play, writes content grounded in complete knowledge of it, and everything it
writes is untrusted until it clears role B) but produces a SceneScript --
narration beats interleaved with decision checkpoints -- instead of a flat
list of questions.

KNOWN GAP: only each checkpoint's corrupted_narration and correct_explanation
go through the spoiler gate (see orchestrator.orchestrate_scene_script) --
plain ScriptBeat text does not get an individual gate call. That's a
deliberate scoping choice, not an oversight: gating a beat properly would
need to know not just "what chapters has the reader finished" but "what has
this specific script already narrated before this beat", since a beat could
in principle spoil something that happens later in the very same scene, and
the existing chapter-level isolation machinery isn't built for that finer
grain. Flagging this here so it doesn't get mistaken for a full guarantee --
extend this if within-scene beat spoilers turn out to matter in practice.
"""

from __future__ import annotations

import json
from typing import List

from .checkpoint_density import CheckpointDensity
from .llm_client import LLMClient, LLMMessage
from .models import Chapter
from .script_models import Checkpoint, CheckpointKind, CheckpointOption, SceneScript, ScriptBeat
from .spoiler_policy import SPOILER_POLICY

# Number of options per checkpoint: exactly one canonical + this many
# non-canonical. Not something the user specified explicitly -- 2 wrong
# options keeps each checkpoint's authoring (and review) load reasonable
# while still giving the branching structure real texture. Revisit if a
# pilot script shows 2 feels thin or 3 feels padded.
WRONG_OPTIONS_PER_CHECKPOINT = 2

SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item_type": {"type": "string", "enum": ["beat", "checkpoint"]},
                    # -- beat fields --
                    "beat_text": {"type": ["string", "null"]},
                    # -- checkpoint fields --
                    "checkpoint_kind": {"type": ["string", "null"], "enum": ["MAJOR", "MINOR", None]},
                    "prompt": {"type": ["string", "null"]},
                    "options": {
                        "type": ["array", "null"],
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string"},
                                "is_canonical": {"type": "boolean"},
                                "corrupted_narration": {"type": ["string", "null"]},
                            },
                            "required": ["label", "is_canonical", "corrupted_narration"],
                        },
                    },
                    "correct_explanation": {"type": ["string", "null"]},
                },
                "required": [
                    "item_type",
                    "beat_text",
                    "checkpoint_kind",
                    "prompt",
                    "options",
                    "correct_explanation",
                ],
            },
        }
    },
    "required": ["items"],
}


def _system_prompt(full_play_text: str, character: str, grade_level: int, density: CheckpointDensity) -> str:
    return (
        "You are writing an interactive role-play script for a student "
        f"playing the character {character} in one scene of this play, with "
        "complete knowledge of the whole play:\n\n"
        f"{full_play_text}\n\n"
        f"{SPOILER_POLICY}\n\n"
        "The script is a sequence of two kinds of item, in the order the "
        "student experiences them:\n\n"
        "1. BEAT -- 2 to 5 sentences of plain narration, retelling what "
        f"actually happens in this scene from {character}'s point of view. "
        "Ground every beat in the scene's real events and dialogue -- do "
        "not invent plot that isn't in the text.\n\n"
        "2. CHECKPOINT -- a decision point. Give it a short, in-character "
        f"prompt describing a moment where {character} has to choose what "
        f"to do next, and exactly {1 + WRONG_OPTIONS_PER_CHECKPOINT} "
        "options: exactly ONE option must be marked is_canonical=true and "
        "must match what the character actually does in the play at this "
        f"moment. The other {WRONG_OPTIONS_PER_CHECKPOINT} options are "
        "plausible-but-wrong choices; each MUST have a corrupted_narration "
        "of 2-5 sentences describing the immediate, in-scene consequence of "
        "that wrong choice. This consequence should end quickly and clearly "
        "-- it is NOT the start of a long alternate story, just a short, "
        "self-contained note on why this path doesn't work, ending the "
        "attempt. The canonical option's corrupted_narration must be null. "
        "Every checkpoint also needs a correct_explanation: 2-4 sentences "
        "explaining WHY the canonical option is what the character actually "
        "does, grounded only in what this scene (and everything before it) "
        "has already established -- do not justify it using anything that "
        "happens later in the play.\n\n"
        f"Write exactly {density.major} MAJOR checkpoint(s) and at least "
        f"{density.minor_min} MINOR checkpoint(s), interleaved with beats so "
        "the script reads as continuous narration punctuated by decisions, "
        "never two checkpoints back to back with no beat between them. "
        "MAJOR checkpoints should be the scene's most consequential turning "
        "points; MINOR checkpoints are smaller, in-character choices along "
        "the way. Write enough beats and checkpoints that a student reading "
        "and deciding at a normal pace, choosing correctly every time, "
        "spends a meaningful amount of time in the scene -- don't pad with "
        "filler, but don't compress a scene's worth of action into two "
        "beats either.\n\n"
        f"The student is in grade {grade_level} (on a 7-12 scale). Calibrate "
        "vocabulary and sentence complexity to that grade the same way you "
        "would for a written passage -- concrete and directly textual for "
        "grade 7, more abstraction and ambiguity acceptable for grade 12.\n\n"
        "Respond only through the required tool call."
    )


def generate_scene_script(
    full_play_text: str,
    chapter: Chapter,
    character: str,
    grade_level: int,
    density: CheckpointDensity,
    client: LLMClient,
) -> SceneScript:
    user_message = f"Chapter: {chapter.chapter_id}\nWrite the script now."
    raw = client.complete(
        system=_system_prompt(full_play_text, character, grade_level, density),
        messages=[LLMMessage(role="user", content=user_message)],
        json_schema=SCRIPT_SCHEMA,
    )
    data = json.loads(raw)

    items: List = []
    for i, raw_item in enumerate(data["items"]):
        if raw_item["item_type"] == "beat":
            items.append(ScriptBeat(beat_id=f"{chapter.chapter_id}_beat{i}", text=raw_item["beat_text"]))
        else:
            options = [
                CheckpointOption(
                    label=opt["label"],
                    is_canonical=opt["is_canonical"],
                    corrupted_narration=opt.get("corrupted_narration"),
                )
                for opt in raw_item["options"]
            ]
            items.append(
                Checkpoint(
                    checkpoint_id=f"{chapter.chapter_id}_cp{i}",
                    kind=CheckpointKind(raw_item["checkpoint_kind"]),
                    prompt=raw_item["prompt"],
                    options=options,
                    correct_explanation=raw_item["correct_explanation"],
                )
            )

    return SceneScript(chapter_id=chapter.chapter_id, character=character, grade_level=grade_level, items=items)
