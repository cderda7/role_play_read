"""
Role C, branching-script variant. Same role as generator.py (sees the full
play, writes content grounded in complete knowledge of it, and everything it
writes is untrusted until it clears role B) but produces a SceneScript --
narration beats interleaved with decision checkpoints -- instead of a flat
list of questions.

CHECKPOINT INTERACTION MODEL (see checkpoint_runtime.py for the actual
runtime logic this content is authored for): picking the canonical option
passes the checkpoint immediately, and correct_explanation is shown to
EVERY student who passes, as reinforcement -- not just as a consolation
prize after a second wrong attempt. Picking a non-canonical option shows
that option's corrupted_narration -- capped at roughly
checkpoint_runtime.MAX_CORRUPTED_NARRATION_SECONDS of reading time, shorter
than a full beat -- then re-presents the SAME checkpoint with that option no
longer offered. With only WRONG_OPTIONS_PER_CHECKPOINT + 1 options total,
the worst case is a student who tries both wrong options before the
canonical one is the only choice left -- i.e. they go down both corrupted
paths before finally landing on the correct one, exactly as intended; a
student who picks correctly on the first or second try never sees the
branch they didn't take.

VOICE/DIALECT (see period_voice.py): what register each option's quote is
written in -- Early Modern English for this play, plain contemporary
English for a different book -- is deliberately NOT decided in this file.
generate_scene_script() takes a voice_guidance string and drops it straight
into the prompt; period_voice.py is where the actual guidance text lives,
so adapting a different novel means picking (or writing) a different
constant there, not editing this module's prompt-building logic.

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
See TODO.md -- this is the explicitly-requested next item.
"""

from __future__ import annotations

from typing import List

from .checkpoint_density import CheckpointDensity
from .checkpoint_runtime import MAX_CORRUPTED_NARRATION_SECONDS, MAX_CORRUPTED_NARRATION_WORDS
from .llm_client import CACHE_BOUNDARY_MARKER, LLMClient, call_structured
from .models import Chapter
from .period_voice import NO_SPECIAL_VOICE_GUIDANCE
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


def _system_prompt(
    full_play_text: str, character: str, grade_level: int, density: CheckpointDensity, voice_guidance: str
) -> str:
    # Everything in cacheable_prefix is identical on EVERY call this
    # function ever makes for this play, regardless of character, chapter,
    # grade, or voice -- full_play_text (~45k tokens) dominates the cost of
    # every call, so this is exactly the prefix prompt caching (see
    # llm_client.py's module docstring) is for. Deliberately phrased without
    # naming the character, so the prefix stays byte-identical across every
    # character this play ever assigns a student to -- WRONG_OPTIONS_PER_CHECKPOINT
    # and the narration word/second budgets are fixed constants, not
    # per-call variables, so they're safe to leave in here too.
    cacheable_prefix = (
        "You are writing an interactive role-play script for a student's "
        "assigned character in one scene of a play, with complete knowledge "
        "of the whole play:\n\n"
        f"{full_play_text}\n\n"
        f"{SPOILER_POLICY}\n\n"
        "The script is a sequence of two kinds of item, in the order the "
        "student experiences them:\n\n"
        "1. BEAT -- 2 to 5 sentences of plain narration, retelling what "
        "actually happens in this scene from the assigned character's point "
        "of view. Ground every beat in the scene's real events and dialogue "
        "-- do not invent plot that isn't in the text.\n\n"
        "2. CHECKPOINT -- a decision point. Give it a short, in-character "
        "prompt describing a moment where the assigned character has to "
        f"choose what to do next, and exactly {1 + WRONG_OPTIONS_PER_CHECKPOINT} "
        "options: exactly ONE option must be marked is_canonical=true and "
        "must match what the character actually does in the play at this "
        f"moment. The other {WRONG_OPTIONS_PER_CHECKPOINT} options are "
        "plausible-but-wrong choices. Each non-canonical option MUST also "
        "have a corrupted_narration: a SHORT passage describing the "
        "immediate, in-scene consequence of that wrong choice, no more than "
        f"about {MAX_CORRUPTED_NARRATION_WORDS} words (roughly "
        f"{MAX_CORRUPTED_NARRATION_SECONDS} seconds read aloud -- shorter "
        "than a beat). This consequence should end quickly and clearly -- it "
        "is NOT the start of a long alternate story, just a short, "
        "self-contained note on why this path doesn't work, after which the "
        "same checkpoint is presented again without this option. The "
        "canonical option's corrupted_narration must be null. Every "
        "checkpoint also needs a correct_explanation: 2-4 sentences "
        "explaining WHY the canonical option is what the character actually "
        "does, grounded only in what this scene (and everything before it) "
        "has already established -- do not justify it using anything that "
        "happens later in the play. This is shown to every student who "
        "passes the checkpoint, as reinforcement, not just to one who got "
        "it wrong first."
    )
    # Everything below is genuinely different per call -- character,
    # density, voice, and grade -- and stays strictly after the marker so it
    # never contaminates the cached prefix above.
    variable_suffix = (
        f"You are writing this scene's script for {character}, a student at "
        f"grade {grade_level} (on a 7-12 scale). Calibrate vocabulary and "
        "sentence complexity to that grade the same way you would for a "
        "written passage -- concrete and directly textual for grade 7, more "
        "abstraction and ambiguity acceptable for grade 12.\n\n"
        f"{voice_guidance}\n\n"
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
        "Respond only through the required tool call."
    )
    return cacheable_prefix + CACHE_BOUNDARY_MARKER + variable_suffix


def generate_scene_script(
    full_play_text: str,
    chapter: Chapter,
    character: str,
    grade_level: int,
    density: CheckpointDensity,
    client: LLMClient,
    voice_guidance: str = NO_SPECIAL_VOICE_GUIDANCE,
) -> SceneScript:
    """voice_guidance defaults to plain contemporary English -- see
    period_voice.py. Pass period_voice.ELIZABETHAN_VOICE_GUIDANCE (or a new
    constant following that file's shape) for a book written in a
    distinctive historical or stylized register."""
    user_message = f"Chapter: {chapter.chapter_id}\nWrite the script now."
    data = call_structured(
        client, _system_prompt(full_play_text, character, grade_level, density, voice_guidance), user_message, SCRIPT_SCHEMA
    )

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
