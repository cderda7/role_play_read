"""
Proves the branching-script pipeline (orchestrate_scene_script) holds the
same isolation guarantee as the question pipeline: role B's narration-gate
calls never receive the full play text or any hint that a generator
produced the text they're judging. Uses a fake client shaped like the real
Anthropic client, keyed off which schema is requested.
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


@dataclass
class RecordedCall:
    system: str
    messages: List[LLMMessage]
    json_schema: Optional[dict]


class FakeScriptClient:
    """Records every call. Returns a small, fixed 1-beat + 1-checkpoint
    script for the generator call, and a CLEAR verdict for every gate call
    -- enough to exercise the orchestration wiring without a real API key."""

    def __init__(self):
        self.calls: List[RecordedCall] = []

    def complete(self, system, messages, json_schema=None):
        self.calls.append(RecordedCall(system=system, messages=list(messages), json_schema=json_schema))

        if json_schema and "items" in json_schema.get("properties", {}):
            # Role C's (script) response shape.
            return json.dumps(
                {
                    "items": [
                        {
                            "item_type": "beat",
                            "beat_text": "Sampson and Gregory swagger through the square, itching for a fight.",
                            "checkpoint_kind": None,
                            "prompt": None,
                            "options": None,
                            "correct_explanation": None,
                        },
                        {
                            "item_type": "checkpoint",
                            "beat_text": None,
                            "checkpoint_kind": "MAJOR",
                            "prompt": "The brawl breaks out. What does Benvolio do?",
                            "options": [
                                {
                                    "label": "Draw your sword to part the fighters.",
                                    "is_canonical": True,
                                    "corrupted_narration": None,
                                },
                                {
                                    "label": "Walk away from the fight entirely.",
                                    "is_canonical": False,
                                    "corrupted_narration": "You turn and leave -- the brawl fizzles out with "
                                    "no one to keep it going, and the guard finds an empty street.",
                                },
                            ],
                            "correct_explanation": "Benvolio steps in to keep the peace, consistent with his "
                            "established role as a peacemaker among the Montagues.",
                        },
                    ]
                }
            )

        # Role B's (gate) response shape.
        return json.dumps(
            {
                "verdict": "CLEAR",
                "flagged_phrase": None,
                "reasoning": "Consistent with what's been read so far.",
                "suggested_rephrase": None,
            }
        )


def _generator_calls(client: FakeScriptClient):
    return [c for c in client.calls if "items" in (c.json_schema or {}).get("properties", {})]


def _gate_calls(client: FakeScriptClient):
    return [c for c in client.calls if "verdict" in (c.json_schema or {}).get("properties", {})]


def test_one_generator_call_and_one_gate_call_per_narration_item():
    full_play_text = "ACT 1... (full play would go here) ...ACT 5"
    chapters = [Chapter(chapter_id="act1_scene1", order=0, text="Two households, both alike in dignity...")]
    client = FakeScriptClient()

    bundle = orchestrate_scene_script(
        full_play_text=full_play_text,
        chapters_read_so_far=chapters,
        character="Benvolio",
        grade_level=9,
        client=client,
        density=CheckpointDensity(major=1, minor_min=0, is_complex=False),
    )

    assert len(_generator_calls(client)) == 1
    # 1 corrupted_narration + 1 correct_explanation = 2 gate calls.
    assert len(_gate_calls(client)) == 2
    assert len(bundle.narration_reviews) == 2
    assert bundle.script.major_count() == 1
    assert bundle.script.minor_count() == 0


def test_gate_calls_never_reference_the_full_play_or_the_generator():
    full_play_text = "ACT 1... (full play would go here) ...ACT 5"
    chapters = [Chapter(chapter_id="act1_scene1", order=0, text="Two households, both alike in dignity...")]
    client = FakeScriptClient()

    orchestrate_scene_script(
        full_play_text=full_play_text,
        chapters_read_so_far=chapters,
        character="Benvolio",
        grade_level=9,
        client=client,
    )

    gate_calls = _gate_calls(client)
    assert gate_calls, "expected at least one gate call"
    for call in gate_calls:
        combined = call.system + "".join(m.content for m in call.messages)
        assert full_play_text not in combined
        assert "generator" not in call.system.lower()


def test_gate_only_sees_text_through_the_current_chapter():
    chapters = [Chapter(chapter_id="act1_scene1", order=0, text="MONTAGUE OPENING TEXT MARKER")]
    later_only_marker = "TOMB SCENE TEXT MARKER"
    full_play_text = f"{chapters[0].text}\n...\n{later_only_marker}"

    client = FakeScriptClient()
    orchestrate_scene_script(
        full_play_text=full_play_text,
        chapters_read_so_far=chapters,
        character="Benvolio",
        grade_level=9,
        client=client,
    )

    for call in _gate_calls(client):
        combined = call.system + "".join(m.content for m in call.messages)
        assert later_only_marker not in combined
        assert "MONTAGUE OPENING TEXT MARKER" in combined


def test_needs_review_when_narration_gate_flags_spoiler():
    class SpoilerFlaggingClient(FakeScriptClient):
        def complete(self, system, messages, json_schema=None):
            self.calls.append(RecordedCall(system=system, messages=list(messages), json_schema=json_schema))
            if json_schema and "items" in json_schema.get("properties", {}):
                return json.dumps(
                    {
                        "items": [
                            {
                                "item_type": "checkpoint",
                                "beat_text": None,
                                "checkpoint_kind": "MINOR",
                                "prompt": "What does Benvolio do?",
                                "options": [
                                    {"label": "Step in.", "is_canonical": True, "corrupted_narration": None},
                                    {
                                        "label": "Walk away.",
                                        "is_canonical": False,
                                        "corrupted_narration": "This foreshadows how Friar Laurence's letter "
                                        "will later fail to reach Romeo.",
                                    },
                                ],
                                "correct_explanation": "Consistent with his peacemaking role.",
                            }
                        ]
                    }
                )
            combined = system + "".join(m.content for m in messages)
            # NOTE: SPOILER_POLICY's own text already contains the phrase
            # "Friar Laurence's letter" (as an example of what's off-limits),
            # so matching on that substring would false-positive on every
            # gate call regardless of which narration text is being judged.
            # Match on wording unique to the corrupted-branch text instead.
            if "will later fail to reach Romeo" in combined:
                return json.dumps(
                    {
                        "verdict": "SPOILER",
                        "flagged_phrase": "Friar Laurence's letter",
                        "reasoning": "The letter plan hasn't happened yet in what's been read.",
                        "suggested_rephrase": None,
                    }
                )
            return json.dumps(
                {
                    "verdict": "CLEAR",
                    "flagged_phrase": None,
                    "reasoning": "Consistent with what's been read so far.",
                    "suggested_rephrase": None,
                }
            )

    chapters = [Chapter(chapter_id="act1_scene1", order=0, text="Two households, both alike in dignity...")]
    client = SpoilerFlaggingClient()

    bundle = orchestrate_scene_script(
        full_play_text="ACT 1...ACT 5",
        chapters_read_so_far=chapters,
        character="Benvolio",
        grade_level=9,
        client=client,
    )

    flagged = bundle.flagged_narration()
    assert len(flagged) == 1
    assert flagged[0].kind == "corrupted_branch"
    assert flagged[0].needs_review is True
