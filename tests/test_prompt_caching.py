"""
Regression coverage for the prompt-caching plumbing: split_cacheable()'s
pure splitting logic, and that generator.py / script_generator.py / gate.py
actually insert CACHE_BOUNDARY_MARKER where they're supposed to -- after the
expensive, call-invariant prefix (full play text for the generators; the
whole system prompt for the gate, since it never varies for a given
text_kind) and strictly before anything that varies per call (grade,
character, density, the bare question/narration being judged).

This doesn't require a live API key -- split_cacheable() is plain string
logic, and the "where's the marker" checks just inspect the prompt strings
the fake clients already receive in the other test files.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from roleplay.checkpoint_density import CheckpointDensity
from roleplay.gate import _system_prompt as gate_system_prompt
from roleplay.generator import _system_prompt as generator_system_prompt
from roleplay.llm_client import CACHE_BOUNDARY_MARKER, split_cacheable
from roleplay.period_voice import NO_SPECIAL_VOICE_GUIDANCE
from roleplay.script_generator import _system_prompt as script_system_prompt


def test_split_cacheable_without_marker_returns_a_single_plain_block():
    blocks = split_cacheable("just plain text, no marker here")
    assert blocks == [{"type": "text", "text": "just plain text, no marker here"}]


def test_split_cacheable_with_marker_splits_into_cached_prefix_and_plain_suffix():
    text = f"cacheable part{CACHE_BOUNDARY_MARKER}variable part"
    blocks = split_cacheable(text)
    assert len(blocks) == 2
    assert blocks[0] == {"type": "text", "text": "cacheable part", "cache_control": {"type": "ephemeral"}}
    assert blocks[1] == {"type": "text", "text": "variable part"}


def test_split_cacheable_with_marker_at_the_end_produces_no_suffix_block():
    text = f"all of this is cacheable{CACHE_BOUNDARY_MARKER}"
    blocks = split_cacheable(text)
    assert len(blocks) == 1
    assert blocks[0]["text"] == "all of this is cacheable"
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}


def test_split_cacheable_ttl_is_included_only_when_given():
    text = f"prefix{CACHE_BOUNDARY_MARKER}suffix"
    default_blocks = split_cacheable(text)
    assert "ttl" not in default_blocks[0]["cache_control"]

    hour_blocks = split_cacheable(text, ttl="1h")
    assert hour_blocks[0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}


def test_generator_prompt_puts_full_play_text_before_the_marker_and_grade_after():
    full_play_text = "UNIQUE_PLAY_TEXT_MARKER full play contents"
    prompt = generator_system_prompt(full_play_text, grade_level=11)
    assert CACHE_BOUNDARY_MARKER in prompt
    prefix, suffix = prompt.split(CACHE_BOUNDARY_MARKER)
    assert full_play_text in prefix
    assert "grade 11" in suffix
    assert "grade 11" not in prefix  # the variable part never leaks into the cacheable prefix


def test_script_generator_prompt_keeps_character_and_grade_out_of_the_cacheable_prefix():
    full_play_text = "UNIQUE_PLAY_TEXT_MARKER full play contents"
    density = CheckpointDensity(major=1, minor_min=3, is_complex=False)
    prompt = script_system_prompt(full_play_text, "Benvolio", 10, density, NO_SPECIAL_VOICE_GUIDANCE)
    assert CACHE_BOUNDARY_MARKER in prompt
    prefix, suffix = prompt.split(CACHE_BOUNDARY_MARKER)
    assert full_play_text in prefix
    assert "Benvolio" not in prefix
    assert "Benvolio" in suffix
    assert "grade 10" in suffix


def test_gate_prompt_is_entirely_cacheable_with_no_suffix():
    prompt = gate_system_prompt("question")
    assert CACHE_BOUNDARY_MARKER in prompt
    blocks = split_cacheable(prompt)
    assert len(blocks) == 1
    assert "cache_control" in blocks[0]
