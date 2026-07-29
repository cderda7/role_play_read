"""
Confirms the voice/dialect guidance is a swappable, independent piece of
content (SRP): script_generator.py takes it as a plain string argument
rather than hardcoding Shakespeare-specific instructions, and
orchestrate_scene_script defaults to the Elizabethan voice only because
THIS project's text is Romeo & Juliet -- a caller adapting a different,
modern-English book can pass a different constant (or write a new one
following period_voice.py's shape) without touching script_generator.py or
orchestrator.py at all.
"""

import json
import os
import sys
from dataclasses import dataclass
from typing import List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from roleplay.checkpoint_density import CheckpointDensity
from roleplay.llm_client import LLMMessage
from roleplay.models import Chapter
from roleplay.orchestrator import orchestrate_scene_script
from roleplay.period_voice import ELIZABETHAN_VOICE_GUIDANCE, NO_SPECIAL_VOICE_GUIDANCE
from roleplay.script_generator import generate_scene_script


@dataclass
class RecordedCall:
    system: str
    messages: List[LLMMessage]
    json_schema: Optional[dict]


class RecordingClient:
    def __init__(self):
        self.calls: List[RecordedCall] = []

    def complete(self, system, messages, json_schema=None):
        self.calls.append(RecordedCall(system=system, messages=list(messages), json_schema=json_schema))
        if json_schema and "items" in json_schema.get("properties", {}):
            return json.dumps({"items": []})
        return json.dumps(
            {"verdict": "CLEAR", "flagged_phrase": None, "reasoning": "fine", "suggested_rephrase": None}
        )


def test_generate_scene_script_defaults_to_no_special_voice():
    client = RecordingClient()
    chapter = Chapter(chapter_id="ch1", order=0, text="Some scene text.")
    generate_scene_script(
        full_play_text="full text",
        chapter=chapter,
        character="Alex",
        grade_level=9,
        density=CheckpointDensity(major=1, minor_min=1, is_complex=False),
        client=client,
    )
    assert NO_SPECIAL_VOICE_GUIDANCE in client.calls[0].system
    assert ELIZABETHAN_VOICE_GUIDANCE not in client.calls[0].system


def test_generate_scene_script_accepts_a_different_voice_guidance():
    client = RecordingClient()
    chapter = Chapter(chapter_id="ch1", order=0, text="Some scene text.")
    custom_voice = "Every option should be written as a noir detective's clipped inner monologue."
    generate_scene_script(
        full_play_text="full text",
        chapter=chapter,
        character="Alex",
        grade_level=9,
        density=CheckpointDensity(major=1, minor_min=1, is_complex=False),
        client=client,
        voice_guidance=custom_voice,
    )
    assert custom_voice in client.calls[0].system
    assert NO_SPECIAL_VOICE_GUIDANCE not in client.calls[0].system


def test_orchestrate_scene_script_defaults_to_elizabethan_for_this_project():
    client = RecordingClient()
    chapters = [Chapter(chapter_id="act1_scene1", order=0, text="Two households, both alike in dignity...")]
    orchestrate_scene_script(
        full_play_text="ACT 1...ACT 5",
        chapters_read_so_far=chapters,
        character="Benvolio",
        grade_level=9,
        client=client,
    )
    generator_call = next(c for c in client.calls if "items" in (c.json_schema or {}).get("properties", {}))
    assert ELIZABETHAN_VOICE_GUIDANCE in generator_call.system


def test_orchestrate_scene_script_can_be_pointed_at_a_different_voice():
    client = RecordingClient()
    chapters = [Chapter(chapter_id="ch1", order=0, text="Some scene text.")]
    orchestrate_scene_script(
        full_play_text="full text",
        chapters_read_so_far=chapters,
        character="Alex",
        grade_level=9,
        client=client,
        voice_guidance=NO_SPECIAL_VOICE_GUIDANCE,
    )
    generator_call = next(c for c in client.calls if "items" in (c.json_schema or {}).get("properties", {}))
    assert NO_SPECIAL_VOICE_GUIDANCE in generator_call.system
    assert ELIZABETHAN_VOICE_GUIDANCE not in generator_call.system
