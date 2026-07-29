"""
Thin LLM client interface, deliberately swappable so the orchestrator and
gate logic can be tested (see tests/test_isolation.py) without a real API
call, and so the underlying model/provider is a one-file change if that ever
needs to happen.

PROMPT CACHING: this pipeline resends the ~45k-token full play text on every
single role-C call, and role B's system prompt is 100% identical across
every gate call for a given text_kind ("question" vs "narration") -- the
kind of repeated, static prefix Anthropic's prompt caching exists for (see
https://docs.claude.com/en/docs/build-with-claude/prompt-caching). Rather
than thread cache_control structure through every call site, callers mark
where the STATIC, REPEATED part of a system prompt or message ends by
inserting CACHE_BOUNDARY_MARKER as a plain substring -- generator.py,
script_generator.py, and gate.py all do this. AnthropicClient splits on that
marker and applies cache_control only to the prefix; everything before the
marker must be byte-identical across calls for a cache hit, so callers need
to put genuinely-variable content (character name, grade level, chapter-
specific counts) strictly AFTER the marker. If a string doesn't contain the
marker at all, it's sent as a single, uncached block -- caching is opt-in
per call site, nothing breaks by omitting it.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol

# Insert this literal substring into a system prompt or message content
# string to mark the end of its cacheable prefix. Never appears in real
# content, so its presence never changes what a reader (or a test's
# substring assertion) sees the text as saying -- it's pure plumbing.
CACHE_BOUNDARY_MARKER = "\n\n<<END_CACHEABLE_PREFIX>>\n\n"


def split_cacheable(text: str, ttl: Optional[str] = None) -> List[Dict]:
    """Splits `text` into Anthropic content blocks, marking everything
    before CACHE_BOUNDARY_MARKER as cacheable. If the marker isn't present,
    returns a single plain block -- this is deliberately a no-op for any
    caller that hasn't opted in.

    ttl controls the cache lifetime: None/omitted uses the default 5-minute
    cache (cheaper to write, 1.25x base input price); pass "1h" for the
    extended 1-hour cache (2x base input price to write) if calls in a
    pilot session are likely to be spaced more than 5 minutes apart -- e.g.
    a human actually reading each chapter's output before running the next
    one. Either way, a cache HIT is priced at 0.1x base input price, so the
    write premium pays for itself after just one reuse."""
    if CACHE_BOUNDARY_MARKER not in text:
        return [{"type": "text", "text": text}]

    prefix, _, suffix = text.partition(CACHE_BOUNDARY_MARKER)
    cache_control = {"type": "ephemeral"}
    if ttl:
        cache_control["ttl"] = ttl

    blocks = [{"type": "text", "text": prefix, "cache_control": cache_control}]
    if suffix:
        blocks.append({"type": "text", "text": suffix})
    return blocks


@dataclass(frozen=True)
class LLMMessage:
    role: str  # "user" | "assistant"
    content: str


class LLMClient(Protocol):
    def complete(
        self,
        system: str,
        messages: List[LLMMessage],
        json_schema: Optional[dict] = None,
    ) -> str:
        """Returns the model's raw text response. If json_schema is given,
        the implementation is responsible for forcing/validating structured
        output against it (e.g. via tool-use) and returning the resulting
        JSON as a string."""
        ...


class AnthropicClient:
    """Real implementation, backed by the Anthropic API. Requires
    ANTHROPIC_API_KEY in the environment. Not yet exercised against a live
    key in this codebase -- treat as unverified until it's actually been run
    for real, the same way everything else here gets a build/test pass
    before being trusted.

    cache_ttl is passed straight to split_cacheable() for both the system
    prompt and every message -- None for the default 5-minute cache, "1h"
    for the extended cache. See this module's docstring and
    split_cacheable()'s for the mechanics and the CACHE_BOUNDARY_MARKER
    convention call sites use to mark what's cacheable.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-5",
        api_key: Optional[str] = None,
        cache_ttl: Optional[str] = None,
    ):
        import anthropic  # local import: keeps this dependency optional for
        # callers that only use FakeLLMClient in tests

        self._client = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
        self._model = model
        self._cache_ttl = cache_ttl

    def complete(
        self,
        system: str,
        messages: List[LLMMessage],
        json_schema: Optional[dict] = None,
    ) -> str:
        kwargs = {}
        tool_name = "respond"
        if json_schema is not None:
            kwargs["tools"] = [
                {
                    "name": tool_name,
                    "description": "Respond with the required structured output.",
                    "input_schema": json_schema,
                }
            ]
            kwargs["tool_choice"] = {"type": "tool", "name": tool_name}

        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=split_cacheable(system, ttl=self._cache_ttl),
            messages=[
                {"role": m.role, "content": split_cacheable(m.content, ttl=self._cache_ttl)} for m in messages
            ],
            **kwargs,
        )

        if json_schema is not None:
            for block in response.content:
                if block.type == "tool_use" and block.name == tool_name:
                    return json.dumps(block.input)
            raise RuntimeError("Model did not return the expected tool call")

        return "".join(block.text for block in response.content if block.type == "text")
