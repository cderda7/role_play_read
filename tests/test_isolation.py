"""
Proves the one property this whole design depends on: role B's calls never
receive anything from role C's call -- not the full play text, not C's
system prompt, not even a hint that a generator exists. Uses a fake client
that records exactly what each call received, so this is checked
structurally against real call contents, not just trusted from a comment.
"""

import json
import os
import sys
from dataclasses import dataclass
from typing import List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from roleplay.llm_client import LLMMessage
from roleplay.models import Chapter, GateVerdict
from roleplay.orchestrator import orchestrate_chapter


@dataclass
class RecordedCall:
    system: str
    messages: List[LLMMessage]
    json_schema: Optional[dict]


class FakeLLMClient:
    """Records every call it receives. Returns canned responses shaped like
    the real Anthropic client would, keyed off which schema is requested --
    good enough to exercise the orchestration logic without a real API key."""

    def __init__(self):
        self.calls: List[RecordedCall] = []

    def complete(self, system, messages, json_schema=None):
        self.calls.append(RecordedCall(system=system, messages=list(messages), json_schema=json_schema))

        if json_schema and "questions" in json_schema.get("properties", {}):
            # Role C's response shape.
            return json.dumps(
                {
                    "questions": [
                        {
                            "question": "Why does the Nurse deliver this message the way she does?",
                            "focus": "motivation",
                        },
                        {
                            "question": "How does Friar Laurence's letter failing to arrive change everything?",
                            "focus": "plot",
                        },
                    ]
                }
            )

        # Role B's response shape.
        return json.dumps(
            {
                "verdict": GateVerdict.CLEAR.value,
                "flagged_phrase": None,
                "reasoning": "Answerable from the text provided.",
            }
        )


def _split_calls(client: FakeLLMClient):
    generator_calls = [c for c in client.calls if "questions" in (c.json_schema or {}).get("properties", {})]
    gate_calls = [c for c in client.calls if "verdict" in (c.json_schema or {}).get("properties", {})]
    return generator_calls, gate_calls


def test_one_generator_call_and_one_gate_call_per_candidate():
    full_play_text = "ACT 1... (full play would go here) ...ACT 5"
    chapters = [Chapter(chapter_id="act1_scene1", order=0, text="Two households, both alike in dignity...")]
    client = FakeLLMClient()

    review_items = orchestrate_chapter(
        full_play_text=full_play_text,
        chapters_read_so_far=chapters,
        character="Juliet",
        client=client,
    )

    generator_calls, gate_calls = _split_calls(client)
    assert len(generator_calls) == 1
    assert len(gate_calls) == 2  # the fake generator always returns 2 questions
    assert len(review_items) == 2


def test_gate_calls_never_reference_the_full_play_or_the_generator():
    full_play_text = "ACT 1... (full play would go here) ...ACT 5"
    chapters = [Chapter(chapter_id="act1_scene1", order=0, text="Two households, both alike in dignity...")]
    client = FakeLLMClient()

    orchestrate_chapter(
        full_play_text=full_play_text,
        chapters_read_so_far=chapters,
        character="Juliet",
        client=client,
    )

    _, gate_calls = _split_calls(client)
    assert gate_calls, "expected at least one gate call"

    for call in gate_calls:
        combined = call.system + "".join(m.content for m in call.messages)
        assert full_play_text not in combined
        assert "question writer" not in call.system.lower()
        assert "generator" not in call.system.lower()


def test_gate_only_sees_text_through_the_current_chapter():
    """A gate call's input should contain exactly the chapters passed in --
    and nothing that looks like it came from a later, unread part of the
    play."""
    chapters = [Chapter(chapter_id="act1_scene1", order=0, text="MONTAGUE OPENING TEXT MARKER")]
    later_only_marker = "TOMB SCENE TEXT MARKER"  # stand-in for spoiler-only content
    full_play_text = f"{chapters[0].text}\n...\n{later_only_marker}"

    client = FakeLLMClient()
    orchestrate_chapter(
        full_play_text=full_play_text,
        chapters_read_so_far=chapters,
        character="Romeo",
        client=client,
    )

    _, gate_calls = _split_calls(client)
    for call in gate_calls:
        combined = call.system + "".join(m.content for m in call.messages)
        assert later_only_marker not in combined
        assert "MONTAGUE OPENING TEXT MARKER" in combined


def test_needs_review_when_gate_flags_spoiler():
    class SpoilerFlaggingClient(FakeLLMClient):
        def complete(self, system, messages, json_schema=None):
            self.calls.append(RecordedCall(system=system, messages=list(messages), json_schema=json_schema))
            if json_schema and "questions" in json_schema.get("properties", {}):
                return json.dumps({"questions": [{"question": "Why does Juliet fake her death?", "focus": "plot"}]})
            return json.dumps(
                {
                    "verdict": GateVerdict.SPOILER.value,
                    "flagged_phrase": "fake her death",
                    "reasoning": "The potion plan hasn't happened yet in what's been read.",
                }
            )

    chapters = [Chapter(chapter_id="act1_scene1", order=0, text="Two households, both alike in dignity...")]
    client = SpoilerFlaggingClient()

    review_items = orchestrate_chapter(
        full_play_text="ACT 1...ACT 5",
        chapters_read_so_far=chapters,
        character="Juliet",
        client=client,
    )

    assert len(review_items) == 1
    assert review_items[0].needs_review is True
    assert review_items[0].gate_result.verdict == GateVerdict.SPOILER
